"""Redis client with automatic fallback to in-memory cache.

If Redis is available, uses it. Otherwise falls back to memory_cache.
This means the app works with or without Redis installed.
"""

import os
import logging

logger = logging.getLogger(__name__)

_pool = None
_use_memory = None


async def get_redis():
    global _pool, _use_memory

    # First call: try Redis, fall back to memory
    if _use_memory is None:
        if os.environ.get("USE_MEMORY_CACHE", "").lower() in ("1", "true", "yes"):
            _use_memory = True
        else:
            try:
                import redis.asyncio as redis
                from config import settings
                _pool = redis.from_url(settings.redis_url, decode_responses=True)
                await _pool.ping()
                _use_memory = False
                logger.info("Connected to Redis at %s", settings.redis_url)
            except Exception as e:
                logger.warning("Redis unavailable (%s), using in-memory cache", e)
                _use_memory = True
                _pool = None

    if _use_memory:
        from memory_cache import get_redis as get_memory
        return await get_memory()

    return _pool


async def close_redis():
    global _pool, _use_memory
    if _use_memory:
        from memory_cache import close_redis as close_memory
        await close_memory()
    elif _pool:
        await _pool.aclose()
        _pool = None
