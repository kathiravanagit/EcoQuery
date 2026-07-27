"""
Carbon intensity cache with optional Redis backend.
Falls back to in-memory dict if Redis is unavailable.
"""

import os
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("EcoQuery.cache")

REDIS_URL = os.getenv("REDIS_URL", "")
_cache_client = None
_memory_cache: dict = {}


def _get_redis():
    global _cache_client
    if _cache_client is not None:
        return _cache_client
    if not REDIS_URL:
        return None
    try:
        import redis
        _cache_client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=2)
        _cache_client.ping()
        logger.info("Connected to Redis cache")
        return _cache_client
    except Exception as e:
        logger.warning(f"Redis unavailable ({e}), using in-memory cache")
        _cache_client = None
        return None


def cache_get(key: str) -> Optional[dict]:
    r = _get_redis()
    if r:
        try:
            data = r.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
    return _memory_cache.get(key)


def cache_set(key: str, value: dict, ttl: int = 600):
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl, json.dumps(value))
            return
        except Exception:
            pass
    _memory_cache[key] = value


def cache_clear():
    r = _get_redis()
    if r:
        try:
            r.flushdb()
        except Exception:
            pass
    _memory_cache.clear()
