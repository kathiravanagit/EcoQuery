"""
Item: fallback carbon accounting -- price the route that ran, not the plan.

CO2 is model-carbon-score x grid intensity. The grid half was chosen at
routing time from the carbon-optimal region, but the provider router can hand
the call to someone else entirely. These tests pin three things: the grid is
re-derived when we hold data for the serving provider, it is explicitly
labelled when we do not, and the cached carbon payload is never mutated.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import providers as providers_mod
from main import app
from router import compute_savings
from routers.chat import (
    CARBON_BASIS_FINAL_PROVIDER,
    CARBON_BASIS_SELECTED_REGION,
    _final_provider_region,
    _reconcile_final_route,
)

PLANNED = {
    "region": "eu-north-1",
    "energy_source": "Hydro",
    "carbon_intensity_g_kwh": 30.0,
    "method": "electricity-maps-api",
}
PROMPT_LEN = 100


def _model(carbon_score=50):
    return {
        "model": "some-model",
        "provider": "OpenRouter",
        "carbon_score": carbon_score,
        "tier": "green",
    }


# ── Which provider regions we actually hold ─────────────────────────────────

@pytest.mark.parametrize("provider", ["google", "anthropic", "GOOGLE"])
def test_known_providers_have_final_region_data(provider):
    assert _final_provider_region(provider) is not None


@pytest.mark.parametrize("provider", ["openrouter", "grok", "openai", "groq", None, ""])
def test_unknown_providers_yield_no_region(provider):
    """Most traffic goes through gateways we hold no region data for."""
    assert _final_provider_region(provider) is None


def test_derived_region_uses_the_providers_own_grid_mix():
    derived = _final_provider_region("google")
    # gcp-europe-west1 is a Wind grid; GRID_ESTIMATES says 100 g/kWh.
    assert derived["region"] == "gcp-europe-west1"
    assert derived["energy_source"] == "Wind"
    assert derived["carbon_intensity_g_kwh"] == 100
    assert derived["method"] == "final-provider-region"


# ── Reconciliation ──────────────────────────────────────────────────────────

def test_known_provider_reprices_the_grid_and_the_savings():
    planned = compute_savings(50, 30.0, prompt_length=PROMPT_LEN)

    region, savings = _reconcile_final_route(
        dict(PLANNED), _model(), planned, {"final_provider": "google"}, PROMPT_LEN,
    )

    assert region["carbon_basis"] == CARBON_BASIS_FINAL_PROVIDER
    assert region["region"] == "gcp-europe-west1"
    assert region["carbon_intensity_g_kwh"] == 100
    # A dirtier grid means a larger estimate and a smaller claimed saving.
    assert savings["estimated_co2_g"] == compute_savings(50, 100.0, prompt_length=PROMPT_LEN)["estimated_co2_g"]
    assert savings["estimated_co2_g"] > planned["estimated_co2_g"]
    assert savings["saved_vs_baseline_g"] <= planned["saved_vs_baseline_g"]


def test_unknown_provider_keeps_the_planned_grid_and_says_so():
    planned = compute_savings(50, 30.0, prompt_length=PROMPT_LEN)

    region, savings = _reconcile_final_route(
        dict(PLANNED), _model(), planned, {"final_provider": "openrouter"}, PROMPT_LEN,
    )

    assert region["carbon_basis"] == CARBON_BASIS_SELECTED_REGION
    assert region["region"] == "eu-north-1"
    assert region["carbon_intensity_g_kwh"] == 30.0
    assert savings is planned


def test_missing_lineage_is_labelled_not_left_blank():
    region, _ = _reconcile_final_route(dict(PLANNED), _model(), {}, None, PROMPT_LEN)
    assert region["carbon_basis"] == CARBON_BASIS_SELECTED_REGION


def test_cached_carbon_payload_is_never_mutated():
    """`get_carbon_optimal_region` may hand back the cached dict itself.

    Writing `carbon_basis` into it would rewrite the shared cache and mislabel
    every later request.
    """
    cached = dict(PLANNED)
    snapshot = dict(cached)

    _reconcile_final_route(cached, _model(), {"estimated_co2_g": 1.0},
                           {"final_provider": "google"}, PROMPT_LEN)

    assert cached == snapshot
    assert "carbon_basis" not in cached


def test_metadata_reports_whichever_basis_was_used():
    from routers.chat import _build_metadata

    # Build the region exactly as the endpoint does after a Google fallback,
    # so the intensity and the basis cannot drift apart in the fixture.
    region, savings = _reconcile_final_route(
        dict(PLANNED), _model(), compute_savings(50, 30.0, prompt_length=PROMPT_LEN),
        {"final_provider": "google"}, PROMPT_LEN,
    )
    v_result = {"status": "verified", "confidence": 0.9,
                "reason": "throughput within band", "observed_tps": 14.2}

    meta = _build_metadata(
        {"tier": "simple", "confidence": 0.9, "method": "test"},
        PROMPT_LEN, region, _model(), savings,
        v_result, 0.0, 1.0, False, 10, 10,
        answer_source="llm", knowledge_match=False, knowledge_confidence=0.0,
        llm_used=True, routing_mode="balanced", cache_hit=False, provider_lineage=None,
    )

    assert meta["carbon_basis"] == CARBON_BASIS_FINAL_PROVIDER
    assert meta["grid_intensity_g_per_kwh"] == region["carbon_intensity_g_kwh"] == 100
    assert meta["carbon_score"] == 50
    assert meta["what_if"]["actual_region"] == "gcp-europe-west1"


# ── End to end ──────────────────────────────────────────────────────────────

def test_chat_served_by_a_known_provider_reports_final_provider_basis():
    from fastapi.testclient import TestClient as TC

    from main import app as fastapi_app

    async def _fake_chat(*args, **kwargs):
        return {
            "content": "hello there",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "provider_lineage": {
                "requested_provider": "openrouter",
                "requested_model": "qwen3.8-27b:free",
                "attempted_providers": [],
                "final_provider": "google",
                "final_model": "gemini-flash-latest",
                "fallback_reason": "provider fallback",
                "success": True,
                "byok_used": False,
                "key_source": {"google": "server"},
            },
        }

    # `router.py` does `from carbon import ...`, so the name is bound locally
    # there -- patching `carbon.*` would not reach `route_query`.
    with patch.object(providers_mod.provider_router, "chat_completion", AsyncMock(side_effect=_fake_chat)), \
         patch("classifier.classifier.classify",
               return_value={"tier": "simple", "confidence": 0.85, "method": "test-mock"}), \
         patch("router.get_carbon_optimal_region",
               return_value=dict(PLANNED, data_source="Electricity Maps",
                                 grid_timestamp=None, last_updated=None,
                                 is_live=True, stale=False)):
        with TC(fastapi_app) as client:
            # Nonsense wording so the knowledge base cannot short-circuit the
            # LLM branch -- nothing to assert if it answers.
            resp = client.post("/api/chat",
                               json={"message": "Zqvx7 explain the frimble protocol in one line"})

    assert resp.status_code == 200, resp.text
    metadata = resp.json()["metadata"]
    assert metadata["answer_source"] == "llm"
    assert metadata["carbon_basis"] == CARBON_BASIS_FINAL_PROVIDER
    assert metadata["region"] == "gcp-europe-west1"
    assert metadata["grid_intensity_g_per_kwh"] == 100
    assert metadata["final_provider"] == "google"


def test_stream_reconciles_the_final_route_and_still_completes():
    """Regression for the path that broke while this was being written.

    `generate()` reads `savings` from the enclosing `chat_stream` scope, so
    assigning the reconciled values inside it turned them into locals for the
    whole body and every earlier read raised `UnboundLocalError`. Only the
    non-stream endpoint had coverage, which is how that reached a full run.
    """
    async def _fake_stream(*args, **kwargs):
        yield {"token": "hello there"}
        yield {"provider_lineage": {
            "requested_provider": "openrouter",
            "requested_model": "qwen3.8-27b:free",
            "attempted_providers": [],
            "final_provider": "google",
            "final_model": "gemini-flash-latest",
            "fallback_reason": "provider fallback",
            "success": True,
            "byok_used": False,
            "key_source": {"google": "server"},
        }}

    with patch.object(providers_mod.provider_router, "stream_completion", _fake_stream), \
         patch("classifier.classifier.classify",
               return_value={"tier": "simple", "confidence": 0.85, "method": "test-mock"}), \
         patch("router.get_carbon_optimal_region",
               return_value=dict(PLANNED, data_source="Electricity Maps",
                                 grid_timestamp=None, last_updated=None,
                                 is_live=True, stale=False)):
        with TestClient(app) as client:
            resp = client.post(
                "/api/chat/stream",
                json={"message": "Zqvx7 explain the frimble protocol in one line"},
            )

    assert resp.status_code == 200, resp.text
    assert "UnboundLocalError" not in resp.text
    assert "Traceback" not in resp.text

    final = None
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            try:
                payload = json.loads(line[len("data: "):])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("done") and "metadata" in payload:
                final = payload["metadata"]

    assert final is not None, f"no terminal metadata event in:\n{resp.text[:800]}"
    assert final["answer_source"] == "llm"
    assert final["carbon_basis"] == CARBON_BASIS_FINAL_PROVIDER
    assert final["region"] == "gcp-europe-west1"
    assert final["grid_intensity_g_per_kwh"] == 100
