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


async def _mixed_feed(code, zone, api_key):
    """Stockholm lost its live fetch; Tokyo answered live but is dirtier.

    Stockholm therefore wins the lowest-intensity sort while carrying only an
    IEA annual baseline -- the exact shape the payload must not call "live".
    """
    if code == "eu-north-1":
        return (10.0, "iea-static-baselines")
    if code == "ap-northeast-1":
        return (500.0, "electricity-maps-api")
    return (300.0, "iea-static-baselines")


class TestProvenanceFollowsTheChosenZone:
    """Regression: `is_live` used to be `live_zones > 0`.

    A single zone answering Electricity Maps labelled the entire payload live,
    including the recommended region when that region had silently fallen back
    to an IEA annual baseline -- and it stamped `fetched_at` onto year-old data.
    """

    def test_winner_from_a_static_baseline_is_not_reported_live(self, monkeypatch):
        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_multi_source", _mixed_feed)
        cache.cache_clear()

        payload = asyncio.run(carbon.get_carbon_optimal_region())

        assert payload["region"] == "eu-north-1"
        assert payload["is_live"] is False
        assert payload["method"] == "iea-static-baselines"
        assert payload["data_source"] == "IEA 2024"
        # An annual average has no grid timestamp. Publishing fetched_at here
        # is what made year-old data look freshly observed.
        assert payload["grid_timestamp"] is None
        assert payload["last_updated"] is None
        # ...even though a different zone did answer live.
        assert payload["live_zones"] == 1

    def test_every_zone_live_still_reports_live(self, monkeypatch):
        async def _live(code, zone, api_key):
            return (50.0, "electricity-maps-api")

        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_multi_source", _live)
        cache.cache_clear()

        payload = asyncio.run(carbon.get_carbon_optimal_region())

        assert payload["is_live"] is True
        assert payload["method"] == "electricity-maps-api"
        assert payload["data_source"] == "Electricity Maps"
        assert payload["grid_timestamp"] is not None

    def test_each_zone_records_its_own_feed(self, monkeypatch):
        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_multi_source", _mixed_feed)
        cache.cache_clear()

        payload = asyncio.run(carbon.get_carbon_optimal_region())
        zones = payload["all_regions"]

        assert zones["eu-north-1"]["is_live"] is False
        assert zones["eu-north-1"]["data_source"] == "IEA 2024"
        assert zones["ap-northeast-1"]["is_live"] is True
        assert zones["ap-northeast-1"]["data_source"] == "Electricity Maps"
        # "source" is the energy-mix estimate and must stay that -- it was the
        # only per-zone field before and is easy to mistake for provenance.
        assert zones["eu-north-1"]["source"] in {
            "Hydro/Wind/Solar", "Mixed Renewables", "Natural Gas Mix", "Coal Grid Baseline",
        }

    def test_last_good_is_kept_even_when_the_winner_is_static(self, monkeypatch):
        """The snapshot still holds live observations, so it stays replay-worthy."""
        monkeypatch.setenv("ELECTRICITY_MAPS_API_KEY", "em_bogus")
        monkeypatch.setattr(carbon, "_fetch_multi_source", _mixed_feed)
        cache.cache_clear()

        asyncio.run(carbon.get_carbon_optimal_region())

        replay = cache.cache_get(carbon.CARBON_LAST_GOOD_KEY)
        assert isinstance(replay, dict), "live observations were thrown away"
        assert replay["all_regions"]


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
