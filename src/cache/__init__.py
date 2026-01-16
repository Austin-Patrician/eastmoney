"""
Cache module - supports Redis and in-memory fallback.
"""
from .cache_manager import CacheManager, cache_manager

__all__ = ['CacheManager', 'cache_manager']
