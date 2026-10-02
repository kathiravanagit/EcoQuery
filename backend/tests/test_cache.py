"""
TTL behaviour of the cache, and specifically of the in-memory fallback.

Redis honours expiry through SETEX. The dict fallback used to store bare
values, so without Redis every entry lived forever -- which is how a stale
carbon payload could be replayed well past its freshness window.
"""

import time

import pytest

import cache


@pytest.fixture(autouse=True)
def memory_only(monkeypatch):
    """Exercise the in-memory path, which is what runs when Redis is absent."""
    monkeypatch.setattr(cache, "REDIS_URL", "")
    monkeypatch.setattr(cache, "_cache_client", None)
    cache.cache_clear()
    yield
    cache.cache_clear()


def test_fresh_entry_is_served():
    cache.cache_set("carbon", {"region": "eu-north-1"}, ttl=600)
    assert cache.cache_get("carbon") == {"region": "eu-north-1"}


def test_missing_key_is_none():
    assert cache.cache_get("nope") is None


def test_entry_expires_after_its_ttl():
    cache.cache_set("carbon", {"stale": True}, ttl=1)
    assert cache.cache_get("carbon") == {"stale": True}

    time.sleep(1.1)

    assert cache.cache_get("carbon") is None, "TTL was ignored by the memory cache"


def test_expired_entry_is_evicted_not_just_hidden():
    cache.cache_set("carbon", {"stale": True}, ttl=1)
    time.sleep(1.1)

    cache.cache_get("carbon")

    assert "carbon" not in cache._memory_cache, "expired entries were never reclaimed"


def test_zero_ttl_expires_immediately():
    cache.cache_set("volatile", {"v": 1}, ttl=0)
    assert cache.cache_get("volatile") is None


def test_cache_clear_removes_everything():
    cache.cache_set("a", {"v": 1}, ttl=600)
    cache.cache_set("b", {"v": 2}, ttl=600)

    cache.cache_clear()

    assert cache.cache_get("a") is None
    assert cache.cache_get("b") is None
    assert cache._memory_cache == {}
