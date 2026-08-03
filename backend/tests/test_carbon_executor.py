"""
Tests for region_scorer (used by ollama routing).
"""

import pytest
from region_scorer import scorer, RegionScorer, RegionScore, CARBON_THRESHOLDS


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

    def test_ranking_prefers_green(self):
        green = scorer.score_region("stockholm", 13, {"nuclear": 40, "hydro": 60})
        dirty = scorer.score_region("mumbai", 700, {"coal": 55, "gas": 25})
        assert green.total_score < dirty.total_score
        assert green.is_green is True
        assert dirty.is_green is False
