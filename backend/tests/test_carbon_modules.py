"""
Tests for carbon-aware routing modules:
carbon_collector, region_scorer, smart_router, temporal_shifter
"""

import pytest
from unittest.mock import patch, MagicMock
from carbon_collector import CarbonDataCollector, IEA_BASELINES, ENERGY_SOURCES
from region_scorer import RegionScorer, RegionScore, CARBON_THRESHOLDS
from temporal_shifter import TemporalShifter


# ── Carbon Collector Tests ────────────────────────────────────────────────────

class TestCarbonCollector:
    def setup_method(self):
        self.collector = CarbonDataCollector()

    def test_iea_baseline_known_zone(self):
        result = self.collector._get_iea_baseline("stockholm")
        assert result["source"] == "iea_2024_baseline"
        assert result["intensity"] == 13

    def test_iea_baseline_partial_match(self):
        result = self.collector._get_iea_baseline("eu-north-1-stockholm")
        assert result["source"] == "iea_2024_baseline"

    def test_iea_baseline_unknown_zone(self):
        result = self.collector._get_iea_baseline("unknown-zone")
        assert result["source"] == "default_fallback"
        assert result["intensity"] == 400

    def test_energy_source_lookup(self):
        source = self.collector.get_energy_source("frankfurt")
        assert source in ["wind", "coal", "gas", "nuclear", "solar"]

    def test_green_hours_hydro(self):
        hours = self.collector.get_green_hours("seattle")
        assert len(hours) > 0
        assert all(0 <= h <= 23 for h in hours)

    def test_green_hours_solar(self):
        hours = self.collector.get_green_hours("frankfurt")
        assert 12 in hours  # Solar peak

    def test_get_intensity_returns_valid(self):
        result = self.collector._get_iea_baseline("stockholm")
        assert "intensity" in result
        assert "source" in result
        assert isinstance(result["intensity"], (int, float))

    def test_all_regions_have_baselines(self):
        for region in ["seattle", "stockholm", "paris", "frankfurt", "amsterdam",
                        "london", "virginia", "tokyo", "mumbai", "singapore"]:
            assert region in IEA_BASELINES
            assert IEA_BASELINES[region] >= 0

    def test_all_regions_have_energy_sources(self):
        for region in ["seattle", "stockholm", "paris", "frankfurt", "amsterdam",
                        "london", "virginia", "tokyo", "mumbai"]:
            assert region in ENERGY_SOURCES
            assert len(ENERGY_SOURCES[region]) > 0


# ── Region Scorer Tests ──────────────────────────────────────────────────────

class TestRegionScorer:
    def setup_method(self):
        self.scorer = RegionScorer()

    def test_score_carbon_ultra_low(self):
        assert self.scorer.score_carbon(30) == 1

    def test_score_carbon_low(self):
        assert self.scorer.score_carbon(150) == 2

    def test_score_carbon_medium(self):
        assert self.scorer.score_carbon(300) == 5

    def test_score_carbon_high(self):
        assert self.scorer.score_carbon(500) == 7

    def test_score_carbon_very_high(self):
        assert self.scorer.score_carbon(700) == 9

    def test_score_carbon_extreme(self):
        assert self.scorer.score_carbon(900) == 10

    def test_score_energy_clean(self):
        score = self.scorer.score_energy({"hydro": 90, "nuclear": 10})
        assert score <= 3

    def test_score_energy_dirty(self):
        score = self.scorer.score_energy({"coal": 80, "gas": 20})
        assert score >= 7

    def test_score_energy_unknown(self):
        assert self.scorer.score_energy({}) == 5

    def test_score_region_green(self):
        result = self.scorer.score_region("stockholm", 13, {"nuclear": 40, "hydro": 60})
        assert result.is_green is True
        assert result.carbon_score <= 2

    def test_score_region_dirty(self):
        result = self.scorer.score_region("mumbai", 700, {"coal": 55, "gas": 25})
        assert result.is_green is False
        assert result.carbon_score >= 9

    def test_rank_regions(self):
        regions = [
            {"region": "mumbai", "intensity": 700},
            {"region": "stockholm", "intensity": 13},
            {"region": "frankfurt", "intensity": 180},
        ]
        ranked = self.scorer.rank_regions(regions)
        assert ranked[0].region == "stockholm"
        assert ranked[-1].region == "mumbai"

    def test_get_greenest(self):
        regions = [
            {"region": "virginia", "intensity": 350},
            {"region": "paris", "intensity": 55},
            {"region": "stockholm", "intensity": 13},
        ]
        greenest = self.scorer.get_greenest(regions)
        assert greenest.region == "stockholm"

    def test_get_color_green(self):
        assert self.scorer.get_color(30) == "#22c55e"

    def test_get_color_red(self):
        assert self.scorer.get_color(700) == "#ef4444"

    def test_is_green_true(self):
        assert self.scorer.is_green(100) is True

    def test_is_green_false(self):
        assert self.scorer.is_green(400) is False

    def test_total_score_range(self):
        result = self.scorer.score_region("test", 200, {"gas": 50, "wind": 50})
        assert 1 <= result.total_score <= 10


# ── Temporal Shifter Tests ───────────────────────────────────────────────────

class TestTemporalShifter:
    def setup_method(self):
        self.shifter = TemporalShifter()

    def test_green_hours_defined(self):
        assert len(self.shifter.green_hours) > 0
        assert all(0 <= h <= 23 for h in self.shifter.green_hours)

    def test_should_delay_low_intensity(self):
        assert self.shifter.should_delay("stockholm", 50) is False

    def test_should_delay_high_intensity(self):
        # Force a specific hour for testing
        with patch("temporal_shifter.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 20  # Evening — not green
            mock_dt.now.return_value = MagicMock()
            mock_dt.now.return_value.hour = 20
            result = self.shifter.should_delay("mumbai", 700)
            assert result is True

    def test_get_carbon_schedule_length(self):
        schedule = self.shifter.get_carbon_schedule("stockholm", 24)
        assert len(schedule) == 24

    def test_get_carbon_schedule_fields(self):
        schedule = self.shifter.get_carbon_schedule("stockholm", 1)
        assert len(schedule) == 1
        assert "hour" in schedule[0]
        assert "is_green_window" in schedule[0]
        assert "recommendation" in schedule[0]

    def test_estimate_savings_green_region(self):
        result = self.shifter.estimate_savings("eu-north-1", 100)
        assert result["savings_per_hour"] >= 0
        assert 0 <= result["savings_percentage"] <= 100

    def test_estimate_savings_dirty_region(self):
        result = self.shifter.estimate_savings("mumbai", 700)
        assert result["savings_per_hour"] > 0
        assert result["savings_percentage"] > 0

    def test_max_delay_configurable(self):
        assert self.shifter.max_delay_minutes == 120

    def test_delay_threshold_configurable(self):
        assert self.shifter.delay_threshold == 300


# ── Integration Tests ────────────────────────────────────────────────────────

class TestIntegration:
    def setup_method(self):
        self.collector = CarbonDataCollector()
        self.scorer = RegionScorer()

    def test_collect_and_score(self):
        """Test full pipeline: collect → score."""
        intensity = self.collector._get_iea_baseline("stockholm")
        score = self.scorer.score_region(
            "stockholm",
            intensity["intensity"],
            intensity.get("energy"),
        )
        assert score.region == "stockholm"
        assert score.is_green is True

    def test_rank_multiple_regions(self):
        """Test ranking multiple regions with real data."""
        regions_data = []
        for zone in ["stockholm", "frankfurt", "virginia", "mumbai"]:
            intensity = self.collector._get_iea_baseline(zone)
            regions_data.append({
                "region": zone,
                "intensity": intensity["intensity"],
                "energy_mix": intensity.get("energy"),
            })

        ranked = self.scorer.rank_regions(regions_data)
        assert ranked[0].region == "stockholm"
        assert ranked[-1].region == "mumbai"

    def test_score_matches_intensity(self):
        """Higher intensity should give higher carbon score."""
        low = self.scorer.score_carbon(50)
        high = self.scorer.score_carbon(700)
        assert low < high
