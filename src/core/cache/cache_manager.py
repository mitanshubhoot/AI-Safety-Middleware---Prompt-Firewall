"""Advanced multi-level caching manager."""
import asyncio
import hashlib
import pickle
from typing import Any, Optional

from cachetools import TTLCache

from src.core.cache.redis_client import RedisClient, get_redis_client
from src.utils.logging import get_logger
from src.utils.metrics import cache_operations_total

logger = get_logger(__name__)


class CacheManager:
    """Multi-level cache manager with L1 (memory) and L2 (Redis)."""

    def __init__(
        self,
        memory_maxsize: int = 1000,
        memory_ttl: int = 300,
        redis_ttl: int = 3600,
    ):
        """Initialize cache manager.

        Args:
            memory_maxsize: Maximum size of L1 memory cache
            memory_ttl: TTL for L1 cache in seconds
            redis_ttl: TTL for L2 Redis cache in seconds
        """
        # L1 Cache: In-memory (fast, local to worker)
        self.memory_cache = TTLCache(maxsize=memory_maxsize, ttl=memory_ttl)
        self.memory_ttl = memory_ttl
        
        # L2 Cache: Redis (distributed, shared across workers)
        self._redis_client: Optional[RedisClient] = None
        self.redis_ttl = redis_ttl
        
        # Cache statistics
        self.stats = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
        }
        
        logger.info(
            "cache_manager_initialized",
            l1_maxsize=memory_maxsize,
            l1_ttl=memory_ttl,
            l2_ttl=redis_ttl,
        )

    async def _get_redis(self) -> RedisClient:
        """Get or create Redis client."""
        if self._redis_client is None:
            self._redis_client = await get_redis_client()
        return self._redis_client

    def _make_key(self, namespace: str, key: str) -> str:
        """Create namespaced cache key.

        Args:
            namespace: Cache namespace
            key: Cache key

        Returns:
            Namespaced key
        """
        return f"cache:{namespace}:{key}"

    async def get(
        self,
        namespace: str,
        key: str,
        fallback_fn: Optional[callable] = None,
    ) -> Optional[Any]:
        """Get value from cache with multi-level lookup.

        Args:
            namespace: Cache namespace
            key: Cache key
            fallback_fn: Optional async function to call if cache miss

        Returns:
            Cached value or result of fallback_fn
        """
        cache_key = self._make_key(namespace, key)
        
        # Try L1 (memory) cache first
        if cache_key in self.memory_cache:
            self.stats["l1_hits"] += 1
            cache_operations_total.labels(operation="get", status="l1_hit").inc()
            logger.debug("l1_cache_hit", namespace=namespace, key=key)
            return self.memory_cache[cache_key]
        
        # Try L2 (Redis) cache
        try:
            redis = await self._get_redis()
            redis_value = await redis.get(cache_key)
            
            if redis_value:
                # Deserialize and promote to L1
                value = pickle.loads(redis_value.encode('latin1'))
                self.memory_cache[cache_key] = value
                self.stats["l2_hits"] += 1
                cache_operations_total.labels(operation="get", status="l2_hit").inc()
                logger.debug("l2_cache_hit", namespace=namespace, key=key)
                return value
        
        except Exception as e:
            logger.error("redis_cache_error", error=str(e))
        
        # Cache miss - use fallback if provided
        self.stats["misses"] += 1
        cache_operations_total.labels(operation="get", status="miss").inc()
        logger.debug("cache_miss", namespace=namespace, key=key)
        
        if fallback_fn:
            value = await fallback_fn()
            if value is not None:
                await self.set(namespace, key, value)
            return value
        
        return None

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Set value in both L1 and L2 cache.

        Args:
            namespace: Cache namespace
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override (uses default if None)

        Returns:
            True if set successfully
        """
        cache_key = self._make_key(namespace, key)
        
        # Set in L1 (memory)
        self.memory_cache[cache_key] = value
        
        # Set in L2 (Redis)
        try:
            redis = await self._get_redis()
            redis_ttl = ttl or self.redis_ttl
            
            # Serialize value
            serialized = pickle.dumps(value).decode('latin1')
            
            await redis.set(cache_key, serialized, ttl=redis_ttl)
            
            cache_operations_total.labels(operation="set", status="success").inc()
            logger.debug("cache_set", namespace=namespace, key=key, ttl=redis_ttl)
            return True
        
        except Exception as e:
            logger.error("cache_set_error", error=str(e), namespace=namespace, key=key)
            cache_operations_total.labels(operation="set", status="error").inc()
            return False

    async def delete(self, namespace: str, key: str) -> bool:
        """Delete value from both caches.

        Args:
            namespace: Cache namespace
            key: Cache key

        Returns:
            True if deleted successfully
        """
        cache_key = self._make_key(namespace, key)
        
        # Delete from L1
        self.memory_cache.pop(cache_key, None)
        
        # Delete from L2
        try:
            redis = await self._get_redis()
            await redis.delete(cache_key)
            
            cache_operations_total.labels(operation="delete", status="success").inc()
            logger.debug("cache_deleted", namespace=namespace, key=key)
            return True
        
        except Exception as e:
            logger.error("cache_delete_error", error=str(e))
            cache_operations_total.labels(operation="delete", status="error").inc()
            return False

    async def invalidate_namespace(self, namespace: str) -> int:
        """Invalidate all keys in a namespace.

        Args:
            namespace: Namespace to invalidate

        Returns:
            Number of keys invalidated
        """
        pattern = f"cache:{namespace}:*"
        
        # Clear L1 cache
        keys_to_remove = [k for k in self.memory_cache.keys() if k.startswith(f"cache:{namespace}:")]
        for key in keys_to_remove:
            del self.memory_cache[key]
        
        # Clear L2 cache
        try:
            redis = await self._get_redis()
            count = await redis.invalidate_cache(pattern)
            
            logger.info("namespace_invalidated", namespace=namespace, count=count)
            return count
        
        except Exception as e:
            logger.error("namespace_invalidation_error", error=str(e), namespace=namespace)
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_requests = sum(self.stats.values())
        
        return {
            **self.stats,
            "l1_hit_rate": self.stats["l1_hits"] / total_requests if total_requests > 0 else 0,
            "l2_hit_rate": self.stats["l2_hits"] / total_requests if total_requests > 0 else 0,
            "overall_hit_rate": (self.stats["l1_hits"] + self.stats["l2_hits"]) / total_requests if total_requests > 0 else 0,
            "l1_size": len(self.memory_cache),
            "l1_maxsize": self.memory_cache.maxsize,
        }

    async def warm_cache(self, warm_data: dict[str, dict[str, Any]]) -> None:
        """Warm cache with frequently accessed data.

        Args:
            warm_data: Dictionary of {namespace: {key: value}}
        """
        logger.info("warming_cache", namespaces=list(warm_data.keys()))
        
        tasks = []
        for namespace, items in warm_data.items():
            for key, value in items.items():
                tasks.append(self.set(namespace, key, value))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("cache_warmed", items_count=len(tasks))


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


async def get_cache_manager() -> CacheManager:
    """Get or create global cache manager instance.

    Returns:
        CacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
