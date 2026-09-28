"""
Tests for the carbon-aware routing module:
carbon_collector (used by green_provider)
"""

from carbon_collector import CarbonDataCollector, IEA_BASELINES, ENERGY_SOURCES


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
