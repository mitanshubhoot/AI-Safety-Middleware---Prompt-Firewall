"""Redis client for caching."""
import hashlib
import json
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.config import get_settings
from src.utils.exceptions import CacheException
from src.utils.logging import get_logger
from src.utils.metrics import cache_operations_total

logger = get_logger(__name__)
settings = get_settings()


class RedisClient:
    """Async Redis client for caching operations."""

    def __init__(self) -> None:
        """Initialize Redis client."""
        self._client: Optional[Redis] = None
        self._url = settings.REDIS_URL
        self._ttl = settings.REDIS_TTL_SECONDS

    async def connect(self) -> None:
        """Connect to Redis server."""
        try:
            self._client = await aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
            await self._client.ping()
            logger.info("redis_connected", url=self._url)
        except RedisError as e:
            logger.error("redis_connection_failed", error=str(e))
            raise CacheException("Failed to connect to Redis", {"error": str(e)})

    async def disconnect(self) -> None:
        """Disconnect from Redis server."""
        if self._client:
            await self._client.close()
            logger.info("redis_disconnected")

    @property
    def client(self) -> Redis:
        """Get Redis client instance."""
        if self._client is None:
            raise CacheException("Redis client not initialized")
        return self._client

    def _generate_cache_key(self, prefix: str, data: str) -> str:
        """Generate cache key from data.

        Args:
            prefix: Key prefix
            data: Data to hash

        Returns:
            Cache key string
        """
        content_hash = hashlib.sha256(data.encode()).hexdigest()
        return f"{prefix}:{content_hash}"

    async def get_cached_validation(self, prompt: str, policy_id: str) -> Optional[dict[str, Any]]:
        """Get cached validation result.

        Args:
            prompt: The prompt text
            policy_id: Policy ID used for validation

        Returns:
            Cached validation result or None if not found
        """
        try:
            key = self._generate_cache_key(f"validation:{policy_id}", prompt)
            result = await self.client.get(key)

            if result:
                cache_operations_total.labels(operation="get", status="hit").inc()
                logger.debug("cache_hit", key=key)
                return json.loads(result)
            else:
                cache_operations_total.labels(operation="get", status="miss").inc()
                logger.debug("cache_miss", key=key)
                return None

        except RedisError as e:
            cache_operations_total.labels(operation="get", status="error").inc()
            logger.error("cache_get_error", error=str(e))
            return None

    async def cache_validation(
        self,
        prompt: str,
        policy_id: str,
        result: dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache validation result.

        Args:
            prompt: The prompt text
            policy_id: Policy ID used for validation
            result: Validation result to cache
            ttl: Time to live in seconds (optional)

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            key = self._generate_cache_key(f"validation:{policy_id}", prompt)
            ttl_seconds = ttl or self._ttl

            await self.client.setex(
                key,
                ttl_seconds,
                json.dumps(result, default=str),
            )

            cache_operations_total.labels(operation="set", status="success").inc()
            logger.debug("cache_set", key=key, ttl=ttl_seconds)
            return True

        except RedisError as e:
            cache_operations_total.labels(operation="set", status="error").inc()
            logger.error("cache_set_error", error=str(e))
            return False

    async def invalidate_cache(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern.

        Args:
            pattern: Redis key pattern

        Returns:
            Number of keys deleted
        """
        try:
            keys = []
            async for key in self.client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                deleted = await self.client.delete(*keys)
                cache_operations_total.labels(operation="delete", status="success").inc(deleted)
                logger.info("cache_invalidated", pattern=pattern, count=deleted)
                return deleted
            return 0

        except RedisError as e:
            cache_operations_total.labels(operation="delete", status="error").inc()
            logger.error("cache_invalidate_error", error=str(e), pattern=pattern)
            return 0

    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis.

        Args:
            key: Redis key

        Returns:
            Value or None if not found
        """
        try:
            return await self.client.get(key)
        except RedisError as e:
            logger.error("redis_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set value in Redis.

        Args:
            key: Redis key
            value: Value to set
            ttl: Time to live in seconds (optional)

        Returns:
            True if set successfully, False otherwise
        """
        try:
            if ttl:
                await self.client.setex(key, ttl, value)
            else:
                await self.client.set(key, value)
            return True
        except RedisError as e:
            logger.error("redis_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from Redis.

        Args:
            key: Redis key

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            await self.client.delete(key)
            return True
        except RedisError as e:
            logger.error("redis_delete_error", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis.

        Args:
            key: Redis key

        Returns:
            True if key exists, False otherwise
        """
        try:
            return bool(await self.client.exists(key))
        except RedisError as e:
            logger.error("redis_exists_error", key=key, error=str(e))
            return False


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get or create global Redis client instance.

    Returns:
        RedisClient instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
        await _redis_client.connect()
    return _redis_client


async def close_redis_client() -> None:
    """Close global Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None
