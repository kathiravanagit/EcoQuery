import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from carbon import _mock_region, REGIONS, _estimate_source, _estimate_savings, STATIC_REGIONAL_INTENSITY, ENERGY_SOURCE_PROFILES


def test_mock_region_has_required_keys():
    result = _mock_region()
    assert "region" in result
    assert "energy_source" in result
    assert "carbon_intensity_g_kwh" in result
    assert "estimated_savings_g_co2" in result
    assert "method" in result
    assert result["method"] == "mock-fallback"


def test_regions_defined():
    assert len(REGIONS) > 0
    for code, info in REGIONS.items():
        assert "name" in info
        assert "zone" in info


def test_all_regions_have_static_intensity():
    for code in REGIONS:
        assert code in STATIC_REGIONAL_INTENSITY, f"Missing static intensity for {code}"


def test_all_regions_have_energy_profile():
    for code in REGIONS:
        if code != "us-east-1":
            assert code in ENERGY_SOURCE_PROFILES, f"Missing energy profile for {code}"


def test_estimate_source_hydro():
    assert _estimate_source(10) == "Hydro/Wind/Solar"
    assert _estimate_source(49) == "Hydro/Wind/Solar"


def test_estimate_source_mixed():
    assert _estimate_source(50) == "Mixed Renewables"
    assert _estimate_source(199) == "Mixed Renewables"


def test_estimate_source_gas():
    assert _estimate_source(200) == "Natural Gas Mix"
    assert _estimate_source(399) == "Natural Gas Mix"


def test_estimate_source_coal():
    assert _estimate_source(400) == "Coal Grid Baseline"
    assert _estimate_source(999) == "Coal Grid Baseline"


def test_estimate_savings_zero_for_high_intensity():
    savings = _estimate_savings(475.0)
    assert savings == 0.0


def test_estimate_savings_positive_for_low_intensity():
    savings = _estimate_savings(100.0)
    assert savings > 0


def test_estimate_savings_formula():
    savings = _estimate_savings(200.0)
    expected = round((475.0 - 200.0) * 0.005, 3)
    assert savings == expected