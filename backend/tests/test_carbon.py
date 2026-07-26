import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from carbon import _mock_region, REGIONS

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
