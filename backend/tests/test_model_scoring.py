"""Regression tests for select_model's scoring contract.

The router scores five normalized terms (capability, carbon, latency, cost,
provider risk) weighted by routing mode. Two properties used to be false and
are the point of this test file:

  * the routing mode decided nothing -- every mode returned the same model;
  * carbon intensity never reached the decision at all.

Both are now locked in below, along with the tiering invariants that the
normalization must not break.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

import router  # noqa: E402
from router import select_model  # noqa: E402


def _model_id(tier, mode="balanced", ci=400.0, pl=500, confidence=1.0):
    return select_model(tier, "NOR", float(ci), mode=mode,
                        confidence=confidence, prompt_length=pl)["model"]


def _capability(model_id):
    return next(c["capability"] for c in router.CARBON_MODELS
                if c["id"] == model_id)


def _carbon_score(model_id):
    return next(c["carbon_score"] for c in router.CARBON_MODELS
                if c["id"] == model_id)


def _latency(model_id):
    return router.MODEL_LATENCY.get(model_id, 2.0)


# --- a catalog that states its requirement ----------------------------------
#
# The two tests below guard a property of the *scoring code*: that `mode` and
# grid intensity reach the decision at all. Both were once false -- every mode
# returned the same model, and carbon intensity never arrived.
#
# The live catalog cannot serve as their fixture. Demonstrating the property
# needs a model that is faster but dirtier than the greenest eligible one, and
# whether the catalog holds such a model depends on which vendor models happen
# to be free this month. OpenRouter retired the only one that did
# (qwen3.8-27b, latency 1.4 against north-mini-code's 1.6), after which `green`
# and `fast` selected the same model in every tier and these two tests failed
# -- not because select_model changed, but because the vendor list did. A
# controlled catalog states the requirement and cannot go stale.
_SLOW_GREEN = {
    "id": "fixture-green-slow:free",
    "provider": "Fixture",
    "tier": "green",
    "carbon_score": 1,
    "capability": "medium",
    "openrouter_id": "fixture/green-slow:free",
    "description": "greenest but slowest",
    "supports_images": False,
}
_FAST_DIRTY = {
    "id": "fixture-fast-dirty:free",
    "provider": "Fixture",
    "tier": "green",
    "carbon_score": 8,
    "capability": "medium",
    "openrouter_id": "fixture/fast-dirty:free",
    "description": "fastest but dirtiest",
    "supports_images": False,
}


@pytest.fixture
def conflicting_catalog(monkeypatch):
    """Two medium-capability models that disagree on carbon and latency.

    The reference scales (CARBON_REFERENCE_G, LATENCY_REFERENCE_S,
    COST_REFERENCE) are deliberately left as the live catalog sets them: they
    are meant to be fixed constants, and a fixture that moved them would be
    exercising a different formula. Both fixture latencies sit inside the real
    LATENCY_REFERENCE_S range of (0.9, 2.5).
    """
    monkeypatch.setattr(router, "CARBON_MODELS", [_SLOW_GREEN, _FAST_DIRTY])
    monkeypatch.setattr(router, "MODEL_LATENCY", {
        _SLOW_GREEN["id"]: 1.8,
        _FAST_DIRTY["id"]: 1.0,
    })


# --- the two properties this unit exists to fix -----------------------------

def test_routing_mode_changes_the_pick(conflicting_catalog):
    """Modes must not be decorative: green and fast disagree."""
    green = _model_id("medium", mode="green")
    fast = _model_id("medium", mode="fast")
    assert green == _SLOW_GREEN["id"]
    assert fast == _FAST_DIRTY["id"]
    assert _carbon_score(green) < _carbon_score(fast)
    assert _latency(fast) < _latency(green)


def test_dirtier_grid_selects_a_greener_model(conflicting_catalog):
    """Grid intensity must reach the decision, not be normalized away.

    In `fast` mode the latency term normally wins, but on a carbon-intensive
    grid the carbon term outweighs it and a greener model is chosen.
    """
    clean = _model_id("medium", mode="fast", ci=10, pl=500)
    dirty = _model_id("medium", mode="fast", ci=1000, pl=500)
    assert clean == _FAST_DIRTY["id"]
    assert dirty == _SLOW_GREEN["id"]
    assert _carbon_score(dirty) < _carbon_score(clean)


def test_intensity_is_not_cancelled_by_normalization():
    """Reference scales must be fixed constants, not per-call candidate ranges.

    If carbon were min-max normalized across the candidate set, intensity
    would multiply every candidate equally and cancel out. Normalization is
    therefore driven by module constants only.
    """
    assert router.CARBON_REFERENCE_G > 0
    assert router.LATENCY_REFERENCE_S == (0.9, 2.5)
    # Identical inputs must give identical output regardless of call order.
    a = [_model_id("medium", mode=m, ci=ci) for ci in (10, 1000)
         for m in ("green", "fast")]
    b = [_model_id("medium", mode=m, ci=ci) for ci in (10, 1000)
         for m in ("green", "fast")]
    assert a == b


# --- mode semantics ----------------------------------------------------------

def test_green_mode_always_picks_the_greenest_eligible_model():
    for tier in ("simple", "medium", "complex"):
        eligible = [c for c in router.CARBON_MODELS
                    if _capability(c["id"]) == "high"
                    or tier == "simple"
                    or (tier == "medium" and c["capability"] in ("medium", "high"))]
        best = min(c["carbon_score"] for c in eligible)
        for ci in (10, 400, 1000):
            assert _carbon_score(_model_id(tier, mode="green", ci=ci)) == best


def test_low_cost_mode_picks_the_cheapest_eligible_model():
    """Cost is proportional to carbon_score, so it must pick the lowest score."""
    for tier in ("simple", "medium", "complex"):
        eligible = [c for c in router.CARBON_MODELS
                    if c["capability"] == "high"
                    or tier == "simple"
                    or (tier == "medium" and c["capability"] in ("medium", "high"))]
        best = min(c["carbon_score"] for c in eligible)
        for ci in (10, 400, 1000):
            assert _carbon_score(_model_id(tier, mode="low-cost", ci=ci)) == best


def test_quality_mode_never_picks_less_capable_than_balanced():
    rank = {"low": 0, "medium": 1, "high": 2}
    for tier in ("simple", "medium", "complex"):
        for ci in (10, 400, 1000):
            for pl in (50, 500, 2000):
                q = _capability(_model_id(tier, mode="quality", ci=ci, pl=pl))
                b = _capability(_model_id(tier, mode="balanced", ci=ci, pl=pl))
                assert rank[q] >= rank[b], (
                    f"{tier} quality={q} was less capable than balanced={b}")


def test_quality_mode_upgrades_a_simple_query():
    """`quality` must refuse the weakest model without jumping to the largest."""
    assert _capability(_model_id("simple", mode="quality")) != "low"
    assert _latency(_model_id("simple", mode="quality")) < 2.0


def test_performance_and_budget_aliases_resolve():
    assert (_model_id("medium", mode="performance")
            == _model_id("medium", mode="fast"))
    assert (_model_id("medium", mode="budget")
            == _model_id("medium", mode="low-cost"))


# --- tiering invariants ------------------------------------------------------

def test_tiering_is_preserved_in_the_default_mode():
    """balanced must still route simple to a small model, complex to a large one."""
    assert _capability(_model_id("simple", mode="balanced")) == "low"
    assert _capability(_model_id("complex", mode="balanced")) == "high"


def test_complex_tier_never_drops_below_high_capability():
    high = {c["id"] for c in router.CARBON_MODELS if c["capability"] == "high"}
    for mode in ("green", "balanced", "fast", "quality", "low-cost"):
        for ci in (10, 400, 1000):
            for pl in (50, 500, 2000):
                assert _model_id("complex", mode=mode, ci=ci, pl=pl) in high


def test_low_confidence_medium_escalates_to_high_capability():
    for mode in ("green", "balanced", "fast", "quality", "low-cost"):
        assert _capability(
            _model_id("medium", mode=mode, confidence=0.5)) == "high"


def test_unknown_tier_does_not_raise():
    """route_query is called with arbitrary classifier output."""
    assert _model_id("unknown_tier_xyz") is not None


# --- response contract -------------------------------------------------------

def test_response_keys_are_unchanged():
    assert {
        "model", "provider", "display_name", "openrouter_id", "tier",
        "carbon_score", "estimated_latency_s", "reason", "quality_safeguard",
    } <= set(select_model("simple", "NOR", 400.0))


def test_selected_model_carries_an_explanatory_reason():
    reason = select_model("simple", "NOR", 400.0, mode="balanced")["reason"]
    assert "Objective score" in reason
    assert "balanced" in reason
