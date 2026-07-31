"""Tests for router.py — model selection and carbon savings logic."""

import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from router import route_query, compute_savings


def _route_sync(tier: str):
    return asyncio.run(route_query(tier, 50))


def test_route_query_simple():
    result = _route_sync("simple")
    assert result is not None
    assert "model" in result
    assert "region" in result
    assert "savings" in result
    assert isinstance(result["model"]["tier"], str)


def test_route_query_complex():
    result = _route_sync("complex")
    assert result is not None
    assert "model" in result
    assert "region" in result
    assert result["region"]["carbon_intensity_g_kwh"] > 0


def test_route_query_medium():
    result = _route_sync("medium")
    assert result is not None
    assert "model" in result
    assert isinstance(result["model"]["tier"], str)


def test_route_query_all_tiers():
    for tier in ("simple", "medium", "complex"):
        result = _route_sync(tier)
        assert result is not None
        assert "model" in result
        assert "region" in result
        assert "savings" in result
        assert isinstance(result["model"]["tier"], str)


def test_compute_savings_green():
    savings = compute_savings(1, 13.0)
    assert savings is not None
    assert "estimated_co2_g" in savings
    assert "saved_vs_baseline_g" in savings
    assert savings["saved_vs_baseline_g"] > 0


def test_compute_savings_coal_region():
    savings = compute_savings(9, 475.0)
    assert savings is not None
    assert savings["saved_vs_baseline_g"] >= 0


def test_compute_savings_low_intensity():
    savings = compute_savings(1, 13.0)
    assert savings is not None
    assert savings["estimated_co2_g"] < 0.01


def test_compute_savings_high_intensity():
    savings = compute_savings(9, 710.0)
    assert savings is not None
    assert savings["estimated_co2_g"] > 0.001


def test_compute_savings_exact_values():
    savings = compute_savings(3, 475.0)
    assert savings["estimated_tokens"] == 31
    assert "estimated_co2_g" in savings
    assert "baseline_g" in savings


def test_compute_savings_min_tokens():
    savings = compute_savings(1, 200.0, prompt_length=1)
    assert savings["estimated_tokens"] >= 10


def test_compute_savings_zero_score():
    savings = compute_savings(0, 200.0)
    assert savings["estimated_co2_g"] >= 0


def test_route_query_unknown_tier_fallback():
    result = _route_sync("unknown_tier_xyz")
    assert result is not None
    assert "model" in result
    assert "region" in result


def test_route_query_returns_display():
    result = _route_sync("simple")
    assert "display" in result
    assert "via" in result["display"]


def test_compute_savings_baseline_constant():
    savings_default = compute_savings(3, 475.0)
    savings_different = compute_savings(3, 475.0, prompt_length=100)
    assert savings_default["baseline_g"] != savings_different["baseline_g"]


def test_compute_savings_carbon_score_zero():
    savings = compute_savings(0, 100.0)
    assert savings["estimated_co2_g"] == 0.0
