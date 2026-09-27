"""Distributed request limiting with a development-only local fallback."""

from __future__ import annotations

import os
import time
import hashlib
from collections import defaultdict


class RateLimiter:
    def __init__(self):
        self.redis = None
        self.local: dict[str, list[float]] = defaultdict(list)

    async def connect(self) -> bool:
        redis_url = os.getenv("REDIS_URL", "")
        if not redis_url:
            return False
        try:
            from redis.asyncio import Redis

            self.redis = Redis.from_url(redis_url, decode_responses=True)
            await self.redis.ping()
            return True
        except Exception:
            self.redis = None
            return False

    async def close(self):
        if self.redis is not None:
            await self.redis.aclose()

    async def allow(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        if self.redis is not None:
            safe_key = hashlib.sha256(key.encode()).hexdigest()
            bucket = f"ecoquery:ratelimit:{window_seconds}:{safe_key}:{int(time.time() // window_seconds)}"
            count = await self.redis.incr(bucket)
            if count == 1:
                await self.redis.expire(bucket, window_seconds + 1)
            return count <= limit, max(0, limit - count)

        now = time.time()
        window = self.local[key]
        window[:] = [timestamp for timestamp in window if now - timestamp < window_seconds]
        if len(window) >= limit:
            return False, 0
        window.append(now)
        return True, max(0, limit - len(window))


rate_limiter = RateLimiter()
