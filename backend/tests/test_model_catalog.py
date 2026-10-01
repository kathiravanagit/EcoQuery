"""Catalog integrity tests.

The structural tests always run. The live test is the one that would have
caught the rot this file previously missed: four of the original seven
`openrouter_id`s had been retired by OpenRouter (they return 404/400, not
merely "absent from the list") and a fifth was a paid model, so every simple
query was burning a 404 before failing over to Google. The old test asserted
the Meta slug and nothing else.
"""

import json
import os
import sys
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import CARBON_MODELS, FALLBACK_MODELS, VISION_MODEL
from providers import HEALTH_PROBE_MODEL
from router import MODEL_LATENCY
from routers.chat import MODEL_COST_MAP

OPENROUTER_CATALOG = "https://openrouter.ai/api/v1/models"


def test_catalog_ids_are_unique():
    ids = [m["id"] for m in CARBON_MODELS]
    openrouter_ids = [m["openrouter_id"] for m in CARBON_MODELS]
    assert len(ids) == len(set(ids))
    assert len(openrouter_ids) == len(set(openrouter_ids))


def test_catalog_is_free_only():
    """models.py promises free-tier; it has to stay literally true."""
    paid = [m["openrouter_id"] for m in CARBON_MODELS if not m["openrouter_id"].endswith(":free")]
    assert paid == []


def test_catalog_id_is_the_last_segment_of_the_openrouter_id():
    """verifier._threshold_key strips the vendor prefix before looking a model
    up, so the two id spellings have to line up for thresholds to be found."""
    for model in CARBON_MODELS:
        assert model["id"] == model["openrouter_id"].split("/")[-1], model["id"]


def test_vision_model_is_a_vision_capable_catalog_entry():
    """chat.py looks the vision model up inside CARBON_MODELS to decide whether
    image uploads are possible at all; an id that isn't there disables vision."""
    entry = next((m for m in CARBON_MODELS if m["id"] == VISION_MODEL), None)
    assert entry is not None, f"{VISION_MODEL} is not in CARBON_MODELS"
    assert entry["supports_images"] is True


def test_capabilities_cover_every_tier():
    capabilities = {m["capability"] for m in CARBON_MODELS}
    assert capabilities <= {"high", "medium", "low"}
    # complex filters to `high`; without one the safeguard falls back to the
    # whole catalog and a complex query can be handed the smallest model.
    assert "high" in capabilities
    assert "low" in capabilities


def test_fallback_chain_only_names_models_that_exist():
    catalog_openrouter_ids = {m["openrouter_id"] for m in CARBON_MODELS}
    assert set(FALLBACK_MODELS) <= catalog_openrouter_ids
    assert len(FALLBACK_MODELS) == len(set(FALLBACK_MODELS))


def test_health_probe_model_is_a_catalog_model():
    """check_health probes this model on every poll — a dead or paid slug there
    either fails the probe for the wrong reason or bills on every health check."""
    assert HEALTH_PROBE_MODEL in {m["openrouter_id"] for m in CARBON_MODELS}


def test_latency_table_matches_the_catalog_exactly():
    assert set(MODEL_LATENCY) == {m["id"] for m in CARBON_MODELS}


def test_cost_map_matches_the_catalog_exactly():
    """Every catalog model is free, so a missing key silently costs the query
    the default $0.001/1K rate and reports a real spend for a free model."""
    assert set(MODEL_COST_MAP) == {m["id"] for m in CARBON_MODELS}
    assert all(rate == 0.0 for rate in MODEL_COST_MAP.values())


def test_all_models_provision():
    """Smoke check that every model is at least syntactically sound."""
    for model in CARBON_MODELS:
        for key in ("id", "provider", "tier", "carbon_score", "capability",
                    "openrouter_id", "description", "supports_images"):
            assert key in model, f"{model.get('id')} missing {key}"
        assert isinstance(model["carbon_score"], int)
        assert model["carbon_score"] > 0


# ── Live check ───────────────────────────────────────────────────────────────
# This is the test that catches retirement: an id can be missing from
# OpenRouter's list entirely, or listed but paid, or listed and free yet
# actually return 403 at request time. The first two are cheap to check here;
# run scripts/provider_diagnostics.py for the third.

def _fetch_catalog():
    with urllib.request.urlopen(OPENROUTER_CATALOG, timeout=30) as resp:
        return {m["id"]: m for m in json.load(resp)["data"]}


def _checked_ids():
    """Every id we ever send to OpenRouter, plus its catalog spelling."""
    ids = {m["openrouter_id"] for m in CARBON_MODELS}
    ids.update(FALLBACK_MODELS)
    ids.add(HEALTH_PROBE_MODEL)
    return sorted(ids)


def test_every_id_sent_to_openrouter_still_exists_and_is_free():
    try:
        remote = _fetch_catalog()
    except Exception as exc:  # pragma: no cover - network dependent
        pytest.skip(f"could not reach OpenRouter catalog: {type(exc).__name__}")

    missing, paid = [], []
    for model_id in _checked_ids():
        info = remote.get(model_id)
        if info is None:
            missing.append(model_id)
            continue
        pricing = info.get("pricing") or {}
        if float(pricing.get("prompt", 0) or 0) > 0 or float(pricing.get("completion", 0) or 0) > 0:
            paid.append(model_id)

    assert not missing, (
        "These ids are no longer offered by OpenRouter and will 404 on every "
        f"request: {missing}"
    )
    assert not paid, (
        "These ids cost money per token, which contradicts the free-tier "
        f"catalog: {paid}"
    )
