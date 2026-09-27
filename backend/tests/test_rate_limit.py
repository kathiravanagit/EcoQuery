import asyncio

from rate_limit import RateLimiter


def test_local_rate_limiter_enforces_window():
    limiter = RateLimiter()

    async def run():
        assert (await limiter.allow("user", 1, 60))[0] is True
        assert (await limiter.allow("user", 1, 60))[0] is False

    asyncio.run(run())
