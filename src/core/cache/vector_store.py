"""Vector store using Redis with RediSearch for semantic similarity."""
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.commands.search.field import NumericField, TagField, TextField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redis.exceptions import RedisError

from src.config import get_settings
from src.utils.exceptions import CacheException
from src.utils.logging import get_logger
from src.utils.metrics import redis_vector_search_duration_seconds

logger = get_logger(__name__)
settings = get_settings()


class VectorStore:
    """Vector store for semantic similarity search using Redis."""

    def __init__(self) -> None:
        """Initialize vector store."""
        self._client: Optional[Redis] = None
        self._url = settings.REDIS_URL
        self._index_name = settings.REDIS_VECTOR_INDEX
        self._dimension = settings.EMBEDDING_DIMENSION
        self._prefix = "embedding:"

    async def connect(self) -> None:
        """Connect to Redis and create index if needed."""
        try:
            self._client = await aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=False,  # Important for binary data
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
            await self._client.ping()
            await self._create_index()
            logger.info("vector_store_connected", index=self._index_name)
        except RedisError as e:
            logger.error("vector_store_connection_failed", error=str(e))
            raise CacheException("Failed to connect to vector store", {"error": str(e)})

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            logger.info("vector_store_disconnected")

    @property
    def client(self) -> Redis:
        """Get Redis client instance."""
        if self._client is None:
            raise CacheException("Vector store client not initialized")
        return self._client

    async def _create_index(self) -> None:
        """Create RediSearch index for vector similarity if it doesn't exist."""
        try:
            # Check if index exists
            try:
                await self.client.ft(self._index_name).info()
                logger.info("vector_index_exists", index=self._index_name)
                return
            except RedisError:
                # Index doesn't exist, create it
                pass

            # Define schema
            schema = (
                TextField("pattern_text"),
                TagField("category"),
                TagField("severity"),
                VectorField(
                    "embedding",
                    "FLAT",
                    {
                        "TYPE": "FLOAT32",
                        "DIM": self._dimension,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
                NumericField("created_at"),
            )

            # Create index
            await self.client.ft(self._index_name).create_index(
                fields=schema,
                definition=IndexDefinition(
                    prefix=[self._prefix],
                    index_type=IndexType.HASH,
                ),
            )

            logger.info(
                "vector_index_created",
                index=self._index_name,
                dimension=self._dimension,
            )

        except RedisError as e:
            logger.error("vector_index_creation_failed", error=str(e))
            # Don't raise exception, continue without index
            logger.warning("continuing_without_vector_index")

    async def store_embedding(
        self,
        pattern_id: str,
        embedding: np.ndarray,
        pattern_text: str,
        category: str,
        severity: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store embedding in Redis.

        Args:
            pattern_id: Unique pattern identifier
            embedding: Embedding vector
            pattern_text: Original pattern text
            category: Pattern category
            severity: Severity level
            metadata: Additional metadata

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Convert embedding to bytes
            embedding_bytes = embedding.astype(np.float32).tobytes()

            # Create key
            key = f"{self._prefix}{pattern_id}"

            # Store in Redis hash
            data = {
                "pattern_text": pattern_text,
                "category": category,
                "severity": severity,
                "embedding": embedding_bytes,
                "metadata": json.dumps(metadata or {}, default=str),
                "created_at": int(np.datetime64("now").astype(int)),
            }

            await self.client.hset(key, mapping=data)  # type: ignore
            logger.debug("embedding_stored", pattern_id=pattern_id, category=category)
            return True

        except Exception as e:
            logger.error("embedding_store_error", pattern_id=pattern_id, error=str(e))
            return False

    async def search_similar(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        threshold: Optional[float] = None,
        category_filter: Optional[str] = None,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar embeddings.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            threshold: Minimum similarity threshold (0-1)
            category_filter: Filter by category (optional)

        Returns:
            List of (pattern_id, similarity_score, metadata) tuples
        """
        import time

        start_time = time.time()

        try:
            # Convert embedding to bytes
            query_bytes = query_embedding.astype(np.float32).tobytes()

            # Build query
            query_str = "*"
            if category_filter:
                query_str = f"@category:{{{category_filter}}}"

            # Create KNN query
            query = (
                Query(query_str)
                .return_fields("pattern_text", "category", "severity", "metadata")
                .sort_by("__embedding_score")
                .dialect(2)
            )

            # Perform vector search
            params = {
                "embedding": query_bytes,
            }

            results = await self.client.ft(self._index_name).search(
                query,
                query_params=params,
            )

            # Parse results
            matches: List[Tuple[str, float, Dict[str, Any]]] = []
            for doc in results.docs[:top_k]:
                # Calculate similarity from distance
                distance = float(doc.__dict__.get("__embedding_score", 1.0))
                similarity = 1.0 - distance  # Cosine distance to similarity

                # Apply threshold filter
                if threshold and similarity < threshold:
                    continue

                pattern_id = doc.id.replace(self._prefix, "")
                metadata = {
                    "pattern_text": doc.pattern_text,
                    "category": doc.category,
                    "severity": doc.severity,
                    "metadata": json.loads(doc.metadata) if hasattr(doc, "metadata") else {},
                }

                matches.append((pattern_id, similarity, metadata))

            duration = time.time() - start_time
            redis_vector_search_duration_seconds.observe(duration)

            logger.debug(
                "vector_search_completed",
                results=len(matches),
                duration=duration,
                threshold=threshold,
            )

            return matches

        except Exception as e:
            logger.error("vector_search_error", error=str(e))
            return []

    async def delete_embedding(self, pattern_id: str) -> bool:
        """Delete embedding from store.

        Args:
            pattern_id: Pattern identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            key = f"{self._prefix}{pattern_id}"
            await self.client.delete(key)
            logger.debug("embedding_deleted", pattern_id=pattern_id)
            return True
        except RedisError as e:
            logger.error("embedding_delete_error", pattern_id=pattern_id, error=str(e))
            return False

    async def count_embeddings(self) -> int:
        """Count total number of embeddings in store.

        Returns:
            Number of embeddings
        """
        try:
            count = 0
            async for _ in self.client.scan_iter(match=f"{self._prefix}*"):
                count += 1
            return count
        except RedisError as e:
            logger.error("count_embeddings_error", error=str(e))
            return 0


# Global vector store instance
_vector_store: Optional[VectorStore] = None


async def get_vector_store() -> VectorStore:
    """Get or create global vector store instance.

    Returns:
        VectorStore instance
    """
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        await _vector_store.connect()
    return _vector_store


async def close_vector_store() -> None:
    """Close global vector store."""
    global _vector_store
    if _vector_store:
        await _vector_store.disconnect()
        _vector_store = None
