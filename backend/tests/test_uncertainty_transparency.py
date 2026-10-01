"""
Uncertainty transparency contract.

Every CO₂ figure the API emits must carry the calibrated band that
`router.compute_savings` derives, on *both* chat surfaces — the streaming
endpoint is what the two chat UIs actually call, so a field present only in the
JSON response would silently never reach a user.
"""

import json
import math

import pytest
from fastapi.testclient import TestClient

from calibration import combined_relative_uncertainty, aggregate_uncertainty_pct
from router import compute_savings


PROMPT = "Explain quantum entanglement in 200 words please"


@pytest.fixture
def client():
    from main import app
    with TestClient(app) as c:
        yield c


class TestComputeSavingsBand:
    def test_exposes_relative_band(self):
        savings = compute_savings(1, 13.0)
        assert isinstance(savings["uncertainty_relative"], float)
        assert savings["uncertainty_relative"] > 0

    def test_relative_band_is_root_sum_square_of_components(self):
        savings = compute_savings(1, 13.0)
        components = savings["uncertainty_components"]
        expected = math.sqrt(sum(v ** 2 for v in components.values()))
        assert savings["uncertainty_relative"] == round(expected, 4)

    def test_absolute_range_is_symmetric_around_the_estimate(self):
        savings = compute_savings(1, 13.0)
        value = savings["estimated_co2_g"]
        band = savings["uncertainty_range_g"]
        r = savings["uncertainty_relative"]
        assert band["min"] == round(max(0.0, value * (1 - r)), 4)
        assert band["max"] == round(value * (1 + r), 4)
        assert band["min"] <= value <= band["max"]

    def test_band_is_never_claimed_as_zero_for_a_real_estimate(self):
        savings = compute_savings(1, 13.0, prompt_length=400)
        assert savings["uncertainty_range_g"]["max"] > savings["uncertainty_range_g"]["min"]

    def test_relative_band_survives_when_the_absolute_range_rounds_away(self):
        # Very short prompts on a clean grid round `estimated_co2_g` to 0 at the
        # stored 4 dp. The relative band must still be reported so the UI can
        # say "<0.001 g ±62%" instead of implying zero emissions.
        savings = compute_savings(1, 13.0, prompt_length=50)
        assert savings["uncertainty_relative"] > 0
        if savings["estimated_co2_g"] == 0:
            assert savings["uncertainty_range_g"] == {"min": 0, "max": 0}


class TestAggregateBand:
    def test_stats_reports_a_percentage(self):
        pct = aggregate_uncertainty_pct()
        assert pct == round(combined_relative_uncertainty() * 100, 1)
        assert 0 < pct <= 100

    def test_aggregate_treats_systematic_error_as_correlated(self):
        # Summing N readings must not shrink a systematic band by 1/sqrt(N):
        # the calibration error applies identically to every row.
        assert aggregate_uncertainty_pct() == round(
            combined_relative_uncertainty() * 100, 1
        )


def test_stats_endpoint_carries_the_band(client):
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "co2_uncertainty_pct" in data
    assert data["co2_uncertainty_pct"] > 0


def test_json_chat_metadata_carries_the_band(client):
    resp = client.post("/api/chat", json={"message": PROMPT})
    assert resp.status_code == 200
    meta = resp.json().get("metadata") or resp.json()
    assert "uncertainty_range_g" in meta
    assert "uncertainty_components" in meta
    assert "uncertainty_relative" in meta
    if meta.get("llm_used"):
        assert meta["uncertainty_relative"] > 0


def test_streaming_metadata_carries_the_band(client):
    """Regression: both chat UIs consume /api/chat/stream, not /api/chat."""
    with client.stream(
        "POST", "/api/chat/stream", json={"message": PROMPT}
    ) as resp:
        assert resp.status_code == 200
        final_metadata = {}
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = json.loads(line[6:])
            if payload.get("done") and payload.get("metadata"):
                final_metadata = payload["metadata"]

    assert final_metadata, "stream ended without a terminal metadata frame"
    assert "uncertainty_range_g" in final_metadata
    assert "uncertainty_components" in final_metadata
    assert "uncertainty_relative" in final_metadata
