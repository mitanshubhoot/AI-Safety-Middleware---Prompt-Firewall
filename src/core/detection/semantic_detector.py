"""Semantic detector using embeddings and vector similarity search."""
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from src.config import get_settings
from src.core.cache.vector_store import VectorStore, get_vector_store
from src.core.models.enums import DetectionType, Severity
from src.core.models.schemas import Detection
from src.utils.exceptions import EmbeddingException
from src.utils.logging import get_logger
from src.utils.metrics import embedding_generation_duration_seconds, semantic_detections_total

logger = get_logger(__name__)
settings = get_settings()


class SemanticDetector:
    """Detector for sensitive data using semantic similarity."""

    def __init__(self, model_name: Optional[str] = None, vector_store: Optional[VectorStore] = None):
        """Initialize semantic detector.

        Args:
            model_name: Name of sentence transformer model (optional)
            vector_store: Vector store instance (optional)
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.threshold = settings.SEMANTIC_THRESHOLD
        self._model: Optional[SentenceTransformer] = None
        self._vector_store = vector_store
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the semantic detector (load model and connect to vector store)."""
        if self._initialized:
            return

        try:
            # Load embedding model
            import time

            start_time = time.time()
            logger.info("loading_embedding_model", model=self.model_name)

            self._model = SentenceTransformer(self.model_name)

            load_time = time.time() - start_time
            logger.info(
                "embedding_model_loaded",
                model=self.model_name,
                load_time=load_time,
            )

            # Connect to vector store if not provided
            if self._vector_store is None:
                self._vector_store = await get_vector_store()

            self._initialized = True

        except Exception as e:
            logger.error("failed_to_initialize_semantic_detector", error=str(e))
            raise EmbeddingException(
                "Failed to initialize semantic detector",
                {"model": self.model_name, "error": str(e)},
            )

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as numpy array

        Raises:
            EmbeddingException: If embedding generation fails
        """
        import time

        if self._model is None:
            raise EmbeddingException("Model not initialized")

        try:
            start_time = time.time()
            embedding = self._model.encode(text, convert_to_numpy=True)
            duration = time.time() - start_time

            embedding_generation_duration_seconds.observe(duration)

            logger.debug(
                "embedding_generated",
                text_length=len(text),
                duration=duration,
            )

            return embedding

        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            raise EmbeddingException(
                "Failed to generate embedding",
                {"text_length": len(text), "error": str(e)},
            )

    async def check(self, prompt: str) -> List[Detection]:
        """Check prompt for sensitive data using semantic similarity.

        Args:
            prompt: The prompt text to check

        Returns:
            List of Detection objects for any matches found
        """
        if not self._initialized:
            await self.initialize()

        detections: List[Detection] = []

        try:
            # Generate embedding for prompt
            prompt_embedding = self._generate_embedding(prompt)

            # Search for similar patterns in vector store
            if self._vector_store is None:
                logger.warning("vector_store_not_available")
                return detections

            similar_patterns = await self._vector_store.search_similar(
                query_embedding=prompt_embedding,
                top_k=10,
                threshold=self.threshold,
            )

            # Create detections for matches above threshold
            for pattern_id, similarity, metadata in similar_patterns:
                # Determine confidence bucket for metrics
                if similarity >= 0.95:
                    bucket = "very_high"
                elif similarity >= 0.90:
                    bucket = "high"
                elif similarity >= 0.85:
                    bucket = "medium"
                else:
                    bucket = "low"

                semantic_detections_total.labels(confidence_bucket=bucket).inc()

                detection = Detection(
                    detection_type=DetectionType.SEMANTIC,
                    matched_pattern=pattern_id,
                    confidence_score=float(similarity),
                    severity=Severity(metadata.get("severity", "medium")),
                    category=metadata.get("category", "unknown"),
                    metadata={
                        "pattern_text": metadata.get("pattern_text", ""),
                        "similarity_score": float(similarity),
                        "threshold": self.threshold,
                        **metadata.get("metadata", {}),
                    },
                )
                detections.append(detection)

                logger.debug(
                    "semantic_match_found",
                    pattern_id=pattern_id,
                    similarity=similarity,
                    category=metadata.get("category"),
                )

        except Exception as e:
            logger.error("semantic_detection_failed", error=str(e))
            # Don't raise exception, return empty detections
            # This allows the system to continue with other detectors

        return detections

    async def add_sensitive_pattern(
        self,
        pattern_id: str,
        pattern_text: str,
        category: str,
        severity: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Add a sensitive pattern to the vector store.

        Args:
            pattern_id: Unique pattern identifier
            pattern_text: Pattern text to generate embedding for
            category: Pattern category
            severity: Severity level
            metadata: Additional metadata

        Returns:
            True if added successfully, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Generate embedding
            embedding = self._generate_embedding(pattern_text)

            # Store in vector store
            if self._vector_store is None:
                logger.error("vector_store_not_available")
                return False

            success = await self._vector_store.store_embedding(
                pattern_id=pattern_id,
                embedding=embedding,
                pattern_text=pattern_text,
                category=category,
                severity=severity,
                metadata=metadata,
            )

            if success:
                logger.info(
                    "sensitive_pattern_added",
                    pattern_id=pattern_id,
                    category=category,
                )

            return success

        except Exception as e:
            logger.error(
                "failed_to_add_sensitive_pattern",
                pattern_id=pattern_id,
                error=str(e),
            )
            return False

    async def remove_sensitive_pattern(self, pattern_id: str) -> bool:
        """Remove a sensitive pattern from the vector store.

        Args:
            pattern_id: Pattern identifier to remove

        Returns:
            True if removed successfully, False otherwise
        """
        if self._vector_store is None:
            logger.error("vector_store_not_available")
            return False

        return await self._vector_store.delete_embedding(pattern_id)

    def set_threshold(self, threshold: float) -> None:
        """Update similarity threshold.

        Args:
            threshold: New threshold value (0-1)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0 and 1")

        self.threshold = threshold
        logger.info("semantic_threshold_updated", threshold=threshold)

    async def get_embedding_count(self) -> int:
        """Get total number of embeddings in vector store.

        Returns:
            Number of embeddings
        """
        if self._vector_store is None:
            return 0
        return await self._vector_store.count_embeddings()
