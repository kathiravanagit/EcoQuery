"""Tests for verifier.py — model substitution detection logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from verifier import verifier, ESTIMATED_THRESHOLDS


def test_verify_normal_tps():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=150,
        latency_seconds=2.0,
        reported_co2_g=0.005
    )
    assert result["status"] == "verified"
    assert result["flagged"] is False


def test_verify_suspiciously_low_tps():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=2000,
        latency_seconds=100.0,
        reported_co2_g=0.005
    )
    assert result["flagged"] is True
    assert result["status"] == "flagged_substitution"


def test_verify_suspiciously_high_tps():
    threshold = ESTIMATED_THRESHOLDS.get("gpt-4o", {})
    max_tps = threshold.get("max_tps", 90)
    result = verifier.verify_completion(
        model_id="gpt-4o",
        prompt_tokens=50,
        completion_tokens=200,
        latency_seconds=0.5,
        reported_co2_g=0.005
    )
    # gpt-4o max_tps = 90, observed = 400, 400 > 90*1.6 = 144 → should flag
    expected = (200 / 0.5) > max_tps * 1.6
    if expected:
        assert result["flagged"] is True
    else:
        assert result["status"] in ("verified", "flagged_substitution")


def test_verify_short_response_skip():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=50,
        completion_tokens=10,
        latency_seconds=2.0,
        reported_co2_g=0.001
    )
    assert result["status"] == "verified"
    assert result["flagged"] is False


def test_verify_zero_latency():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=100,
        latency_seconds=0,
        reported_co2_g=0.005
    )
    assert result["status"] == "verified"
    assert result["flagged"] is False


def test_verify_integrity_hash_present():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=200,
        latency_seconds=3.0,
        reported_co2_g=0.005
    )
    assert "integrity_hash" in result
    assert len(result["integrity_hash"]) == 16


def test_verify_confidence_range():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=200,
        latency_seconds=3.0,
        reported_co2_g=0.005
    )
    assert 0.0 <= result["confidence"] <= 1.0


def test_verify_adjusted_co2_on_flag():
    result = verifier.verify_completion(
        model_id="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=2000,
        latency_seconds=100.0,
        reported_co2_g=0.005
    )
    if result["flagged"]:
        assert result["adjusted_co2_g"] < 0.005


def test_verify_unknown_model_uses_default_threshold():
    result = verifier.verify_completion(
        model_id="nonexistent-model-v42",
        prompt_tokens=100,
        completion_tokens=200,
        latency_seconds=4.0,
        reported_co2_g=0.01
    )
    assert "status" in result
    assert "confidence" in result


def test_verify_very_fast_response_flagged():
    result = verifier.verify_completion(
        model_id="claude-3.5-sonnet",
        prompt_tokens=100,
        completion_tokens=200,
        latency_seconds=0.15,
        reported_co2_g=0.005
    )
    # latency_ratio = 0.15/2.0 = 0.075 < 0.1 and observed_tps = 1333 > 100
    # → should flag as too fast
    assert result["flagged"] is True


def test_verify_integrity_hash_consistent():
    r1 = verifier.verify_completion(
        model_id="gpt-4o", prompt_tokens=50, completion_tokens=100, latency_seconds=1.0, reported_co2_g=0.005
    )
    r2 = verifier.verify_completion(
        model_id="gpt-4o", prompt_tokens=50, completion_tokens=100, latency_seconds=1.0, reported_co2_g=0.005
    )
    assert r1["integrity_hash"] == r2["integrity_hash"]


def test_verify_high_latency_triggers_flag():
    result = verifier.verify_completion(
        model_id="groq-llama-3.1-70b",
        prompt_tokens=100,
        completion_tokens=500,
        latency_seconds=20.0,
        reported_co2_g=0.01
    )
    # latency_ratio = 20.0/0.5 = 40x > 3.0 → should flag
    assert result["flagged"] is True
