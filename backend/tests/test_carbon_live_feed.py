"""
Live-feed reliability for carbon intensity.

Covers the guarantees the UI depends on:
  * every Electricity Maps call is hard-capped at 3 seconds
  * a configured-but-failing feed never reports itself as real-time
  * an outage replays the last observed value with a staleness marker
  * degraded responses are cached briefly so the fan-out is not re-run per request
  * the payload always carries last_updated / is_live / stale
"""

import asyncio
import time

import carbon
import cache


LIVE_VALUE = 41.0


def _region_result(**overrides):
    """A payload as produced by a successful live read."""
    base = {
        "region": "eu-north-1",
        "method": "electricity-maps-api",
        "data_source": "Electricity Maps",
        "grid_timestamp": "2026-09-30T09:00:00+00:00",
        "last_updated": "2026-09-30T09:00:00+00:00",
        "is_live": True,
        "stale": False,
        "carbon_intensity_g_kwh": LIVE_VALUE,
        "all_regions": {"eu-north-1": {"intensity": LIVE_VALUE, "name": "Stockholm"}},
        "total_regions_covered": 1,
    }
    base.update(overrides)
    return base


class TestLiveFeedContract:
    def test_payload_always_exposes_staleness_fields(self, monkeypatch):
        monkeypatch.delenv("ELECTRICITY_MAPS_API_KEY", raising=False)
        cache.cache_clear()
        payload = asyncio.run(carbon.get_carbon_optimal_region())
        for field in ("last_updated", "is_live", "stale", "method", "data_source"):
            assert field in payload, f"frontend contract field {field!r} missing"

    def test_no_api_key_reports_static_baselines_not_live(self, monkeypatch):
        monkeypatch.delenv("ELECTRICITY_MAPS_API_KEY", raising=False)
        cache.cache_clear()
        payload = asyncio.run(carbon.get_carbon_optimal_region())
        assert payload["method"] == "iea-static-baselines"
        assert payload["is_live"] is False
        assert payload["stale"] is False
        # An annual average is not time-varying, so it must not claim a timestamp.
        assert payload["last_updated"] is None

    def test_multi_source_distinguishes_live_from_static(self):
        loop = asyncio.new_event_loop()
        try:
            # No key → static, and the source must say so rather than implying live.
            _, source = loop.run_until_complete(
                carbon._fetch_multi_source("eu-north-1", "SE", api_key="")
            )
            assert source == "iea-static-baselines"
        finally:
            loop.close()


class TestFeedFailureDegradesHonestly:
    def test_configured_key_with_failing_feed_does_not_claim_realtime(self, monkeypatch):
        """Regression: method used to be derived from key presence alone."""
        async def _fail(zone, api_key):
            return None

        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_electricity_maps", _fail)
        cache.cache_clear()

        payload = asyncio.run(carbon.get_carbon_optimal_region())
        assert payload["method"] == "iea-static-baselines"
        assert payload["is_live"] is False
        assert payload["total_regions_covered"] > 0

    def test_stale_value_is_replayed_with_timestamp(self, monkeypatch):
        async def _fail(zone, api_key):
            return None

        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_electricity_maps", _fail)
        cache.cache_clear()
        cache.cache_set(carbon.CARBON_LAST_GOOD_KEY, _region_result(), 600)

        payload = asyncio.run(carbon.get_carbon_optimal_region())
        assert payload["method"] == "stale-cache"
        assert payload["stale"] is True
        assert payload["is_live"] is False
        assert payload["stale_reason"] == "live_feed_unavailable"
        # The UI renders "Cached · <age>" from this, so it must survive replay.
        assert payload["last_updated"] == "2026-09-30T09:00:00+00:00"
        assert payload["carbon_intensity_g_kwh"] == LIVE_VALUE

    def test_degraded_response_is_cached_so_fanout_is_not_repeated(self, monkeypatch):
        calls = {"n": 0}

        async def _fail(zone, api_key):
            calls["n"] += 1
            return None

        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_electricity_maps", _fail)
        cache.cache_clear()
        cache.cache_set(carbon.CARBON_LAST_GOOD_KEY, _region_result(), 600)

        asyncio.run(carbon.get_carbon_optimal_region())
        after_first = calls["n"]
        assert after_first > 0, "first call should attempt the live feed"

        started = time.perf_counter()
        second = asyncio.run(carbon.get_carbon_optimal_region())
        elapsed = time.perf_counter() - started

        # One call fans out to every region, so compare against the count rather
        # than an absolute number of HTTP requests.
        assert calls["n"] == after_first, "second call must be served from the degraded cache"
        assert elapsed < 0.5, f"degraded cache miss cost {elapsed:.2f}s"
        assert second["stale"] is True

    def test_fresh_cache_is_never_marked_stale(self, monkeypatch):
        monkeypatch.delenv("ELECTRICITY_MAPS_API_KEY", raising=False)
        cache.cache_clear()
        cache.cache_set(carbon.CARBON_CACHE_KEY, _region_result(stale=True), 600)
        payload = asyncio.run(carbon.get_carbon_optimal_region())
        # A stale entry in the hot cache must not be served as if it were fresh.
        assert payload["method"] in {"iea-static-baselines", "mock-fallback"}


class TestHardTimeout:
    def test_electricity_maps_call_is_capped_at_three_seconds(self, monkeypatch):
        """A feed slower than the budget must yield None instead of blocking."""
        import httpx

        async def _slow_get(self, *args, **kwargs):
            await asyncio.sleep(30)
            return httpx.Response(200, json={"carbonIntensity": 1})

        monkeypatch.setattr(httpx.AsyncClient, "get", _slow_get)

        started = time.perf_counter()
        result = asyncio.run(carbon._fetch_electricity_maps("SE", "em_key"))
        elapsed = time.perf_counter() - started

        assert result is None
        assert elapsed < 4.0, f"timeout took {elapsed:.2f}s, expected <= 3s + teardown"

    def test_timeout_constant_is_three_seconds(self):
        assert carbon.ELECTRICITY_MAPS_TIMEOUT <= 3.0
