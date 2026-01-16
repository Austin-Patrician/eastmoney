"""
Cache Manager - Provides unified caching interface with Redis and in-memory fallback.
"""
import json
import time
import threading
from typing import Any, Optional, Dict
from datetime import datetime

# Try to import redis, but don't fail if not installed
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class InMemoryCache:
    """Thread-safe in-memory cache with TTL support."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache, returns None if expired or not found."""
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if entry['expires_at'] and time.time() > entry['expires_at']:
                del self._cache[key]
                return None

            return entry['value']

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value with optional TTL in seconds."""
        with self._lock:
            expires_at = time.time() + ttl if ttl else None
            self._cache[key] = {
                'value': value,
                'expires_at': expires_at,
                'created_at': time.time()
            }
            return True

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    def clear(self) -> bool:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            return True

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed entries."""
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._cache.items()
                if v['expires_at'] and now > v['expires_at']
            ]
            for k in expired_keys:
                del self._cache[k]
            return len(expired_keys)

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        with self._lock:
            return {
                'type': 'in_memory',
                'total_keys': len(self._cache),
                'memory_usage': 'N/A'
            }


class RedisCache:
    """Redis-based cache implementation."""

    def __init__(self, redis_url: str):
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "valpha:"  # Key prefix for namespacing

    def _key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        try:
            value = self._client.get(self._key(key))
            if value is None:
                return None
            return json.loads(value)
        except (redis.RedisError, json.JSONDecodeError) as e:
            print(f"Redis GET error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value with optional TTL in seconds."""
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            if ttl:
                self._client.setex(self._key(key), ttl, serialized)
            else:
                self._client.set(self._key(key), serialized)
            return True
        except (redis.RedisError, TypeError) as e:
            print(f"Redis SET error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        try:
            return bool(self._client.delete(self._key(key)))
        except redis.RedisError as e:
            print(f"Redis DELETE error for {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            return bool(self._client.exists(self._key(key)))
        except redis.RedisError:
            return False

    def clear(self) -> bool:
        """Clear all keys with our prefix."""
        try:
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match=f"{self._prefix}*", count=100)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
            return True
        except redis.RedisError as e:
            print(f"Redis CLEAR error: {e}")
            return False

    def get_stats(self) -> Dict:
        """Get Redis statistics."""
        try:
            info = self._client.info('memory')
            return {
                'type': 'redis',
                'total_keys': self._client.dbsize(),
                'memory_usage': info.get('used_memory_human', 'N/A')
            }
        except redis.RedisError:
            return {'type': 'redis', 'error': 'unable to get stats'}


class CacheManager:
    """
    Unified cache manager that uses Redis if available, falls back to in-memory.

    Usage:
        from src.cache import cache_manager

        # Set with TTL (5 minutes)
        cache_manager.set('my_key', {'data': 'value'}, ttl=300)

        # Get
        data = cache_manager.get('my_key')

        # Delete
        cache_manager.delete('my_key')
    """

    def __init__(self, redis_url: str = None):
        self._backend = None
        self._redis_url = redis_url
        self._initialized = False

    def _init_backend(self):
        """Lazy initialization of cache backend."""
        if self._initialized:
            return

        # Try to get Redis URL from settings if not provided
        if not self._redis_url:
            try:
                from config.settings import REDIS_URL
                self._redis_url = REDIS_URL
            except ImportError:
                pass

        # Try Redis first
        if self._redis_url and REDIS_AVAILABLE:
            try:
                self._backend = RedisCache(self._redis_url)
                # Test connection
                self._backend._client.ping()
                print(f"✓ Cache: Using Redis ({self._redis_url[:30]}...)")
            except Exception as e:
                print(f"✗ Redis connection failed: {e}, falling back to in-memory cache")
                self._backend = InMemoryCache()
        else:
            if not REDIS_AVAILABLE and self._redis_url:
                print("✗ Redis package not installed, using in-memory cache")
            else:
                print("✓ Cache: Using in-memory cache (no Redis URL configured)")
            self._backend = InMemoryCache()

        self._initialized = True

    @property
    def backend(self):
        """Get the cache backend, initializing if needed."""
        if not self._initialized:
            self._init_backend()
        return self._backend

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        return self.backend.get(key)

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value with optional TTL in seconds."""
        return self.backend.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        return self.backend.delete(key)

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        return self.backend.exists(key)

    def clear(self) -> bool:
        """Clear all cache entries."""
        return self.backend.clear()

    def get_or_set(self, key: str, factory_func, ttl: int = None) -> Any:
        """
        Get value from cache, or compute and cache it if not found.

        Args:
            key: Cache key
            factory_func: Callable that returns the value to cache
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value

        value = factory_func()
        if value is not None:
            self.set(key, value, ttl)
        return value

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        return self.backend.get_stats()

    def is_redis(self) -> bool:
        """Check if using Redis backend."""
        return isinstance(self.backend, RedisCache)


# Global singleton instance
cache_manager = CacheManager()
