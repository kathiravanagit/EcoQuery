"""
Carbon-aware model router for EcoQuery.

Routes by a weighted score over five normalized terms: capability, carbon,
latency, cost and provider risk. Which term dominates depends on the routing
mode, so carbon is *not* always the deciding factor -- see docs/METHODOLOGY.md.
"""

import logging
from carbon import get_carbon_optimal_region
from calibration import CALIBRATION_VERSION, combined_relative_uncertainty, get_calibration
from models import CARBON_MODELS

logger = logging.getLogger("EcoQuery.router")

SUPPORTED_ROUTING_MODES = ("green", "balanced", "quality", "fast", "low-cost")

# Expected round-trip latency in seconds, keyed by models.CARBON_MODELS id.
# Ordered by model size: the router's default tie-break is "fastest model that
# is good enough", so the tiers only separate if these are ordered sensibly.
MODEL_LATENCY = {
    "nemotron-3-ultra-550b-a55b:free": 2.5,
    "nemotron-3-super-120b-a12b:free": 2.1,
    "dots-3-note-preview:free": 1.9,
    "nemotron-3-nano-omni-30b-a3b-reasoning:free": 1.7,
    "north-mini-code:free": 1.6,
    "qwen3.8-27b:free": 1.4,
    "lfm-2.5-2.6b:free": 0.9,
}


# Fixed reference scales for the scoring terms.
#
# select_model sums five terms that have incompatible natural units (grams,
# seconds, dollars, an ordinal capability rank), so each term is mapped onto a
# FIXED reference range before its mode weight is applied. Without this the
# weights are meaningless: measured against the raw units, latency spanned 1.6
# while carbon spanned 0.09 and cost 0.007, so latency decided every route
# regardless of mode.
#
# The references must be fixed constants, never derived from the candidate
# set. carbon_intensity multiplies every candidate's carbon term equally, so a
# per-call min-max normalization would cancel the grid intensity out completely
# and leave the router blind to how dirty the grid is.
_SCORES = [m["carbon_score"] for m in CARBON_MODELS]

# Carbon (g) of the largest catalog model for a 500-character message on a
# 400 gCO2e/kWh grid. Sized so the catalog's carbon spread (~0.875) is
# comparable to the latency spread (1.0) at that reference condition, which is
# what lets the carbon and latency weights trade off against each other.
CARBON_REFERENCE_G = (500 / 1000.0) * 0.0002 * (max(_SCORES) / 3.0) * 400.0

LATENCY_REFERENCE_S = (min(MODEL_LATENCY.values()), max(MODEL_LATENCY.values()))
COST_REFERENCE = (0.001 * min(_SCORES), 0.001 * max(_SCORES))
PROVIDER_RISK_REFERENCE = (1.0, 2.0)  # self-hosted, hosted

CAPABILITY_RANK = {"low": 0, "medium": 1, "high": 2}
# Capability each tier is aiming for, one step above the floor the filter
# enforces. quality_risk penalizes models that fall short of it, which is the
# only thing the `quality` mode (w1 = 5) has to decide with -- the floor has
# already removed everything below the tier's minimum.
CAPABILITY_IDEAL = {"simple": "medium", "medium": "high", "complex": "high"}
QUALITY_RISK_PENALTY = 0.25


def _normalize(value: float, low: float, high: float) -> float:
    """Map a raw term onto its fixed reference range. Lower is better.

    Deliberately not clamped: a long prompt on a carbon-intensive grid really
    does emit more than the reference, and clamping would stop that term from
    discriminating between candidates exactly when it matters most.
    """
    if high == low:
        return 0.0
    return (value - low) / (high - low)


def select_model(tier: str, region_code: str, carbon_intensity: float, mode: str = "balanced", confidence: float = 1.0, prompt_length: int = 50) -> dict:
    candidates = list(CARBON_MODELS)
    original_candidate_count = len(candidates)
    
    # 1. Quality Safeguard
    # The router should not choose a smaller model merely because it is greener.
    if tier == "complex" or (tier == "medium" and confidence < 0.75):
        candidates = [c for c in candidates if c["capability"] == "high"]
    elif tier == "medium":
        candidates = [c for c in candidates if c["capability"] in ("medium", "high")]
        
    if not candidates:
        candidates = list(CARBON_MODELS) # fallback if filtered out too strictly
    quality_safeguard_applied = len(candidates) != original_candidate_count
        
    # Weights: (w1_quality, w2_carbon, w3_latency, w4_cost, w5_risk)
    mode = {"performance": "fast", "budget": "low-cost"}.get(mode, mode)
    weights = {
        "green": (1.0, 5.0, 1.0, 1.0, 1.0),
        "balanced": (2.0, 2.0, 1.0, 1.0, 1.0),
        "fast": (1.0, 1.0, 5.0, 1.0, 1.0),
        "quality": (5.0, 1.0, 1.0, 1.0, 1.0),
        "low-cost": (1.0, 1.0, 1.0, 5.0, 1.0),
    }
    w1, w2, w3, w4, w5 = weights.get(mode, weights["balanced"])
    
    best_score = float('inf')
    chosen = candidates[0]
    
    for c in candidates:
        # Quality risk: capability below the tier's ideal. The capability
        # floor above already enforces the tier's *minimum*, so this term
        # only separates survivors from each other -- it is what lets
        # `quality` mode prefer a more capable model over a greener one.
        ideal_rank = CAPABILITY_RANK[CAPABILITY_IDEAL.get(tier, "medium")]
        quality_risk = (QUALITY_RISK_PENALTY
                        if CAPABILITY_RANK[c["capability"]] < ideal_rank
                        else 0.0)

        # Carbon cost
        energy_per_1k = 0.0002 * (c["carbon_score"] / 3.0)
        estimated_carbon = (prompt_length / 1000.0) * energy_per_1k * carbon_intensity
        
        # Latency
        latency = MODEL_LATENCY.get(c["id"], 2.0)
        
        # Cost (approximate)
        cost = 0.001 * c["carbon_score"] # simplistic mock cost
        
        # Provider failure risk (could be dynamic, fixed for now)
        provider_risk = 1.0 if c["provider"] == "Ollama (Local)" else 2.0
        
        total_score = (
            w1 * quality_risk
            + w2 * _normalize(estimated_carbon, 0.0, CARBON_REFERENCE_G)
            + w3 * _normalize(latency, *LATENCY_REFERENCE_S)
            + w4 * _normalize(cost, *COST_REFERENCE)
            + w5 * _normalize(provider_risk, *PROVIDER_RISK_REFERENCE)
        )

        if total_score < best_score:
            best_score = total_score
            chosen = c

    estimated_latency = MODEL_LATENCY.get(chosen["id"], 2.0)

    return {
        "model": chosen["id"],
        "provider": chosen["provider"],
        "display_name": f"{chosen['provider']} {chosen['id']}",
        "openrouter_id": chosen["openrouter_id"],
        "tier": chosen["tier"],
        "carbon_score": chosen["carbon_score"],
        "estimated_latency_s": estimated_latency,
        "reason": f"Objective score: {round(best_score, 2)} (Mode: {mode})",
        "quality_safeguard": {
            "applied": quality_safeguard_applied,
            "minimum_capability": "high" if tier == "complex" or (tier == "medium" and confidence < 0.75) else "medium",
            "escalation_reason": "Capability threshold protected answer quality" if quality_safeguard_applied else None,
        },
    }


def compute_savings(model_carbon_score: int | float, region_intensity: float, prompt_length: int = 50) -> dict:
    estimated_tokens = max(10, int((prompt_length / 4.0) * 2.5))
    calibration = get_calibration(model_carbon_score)
    energy_per_1k_kwh = calibration.energy_kwh_per_1000_tokens
    energy_used_kwh = (estimated_tokens / 1000.0) * energy_per_1k_kwh
    estimated_co2_g = round(energy_used_kwh * region_intensity, 4)
    baseline_energy_kwh = (estimated_tokens / 1000.0) * 0.001
    baseline_co2_g = round(baseline_energy_kwh * 475.0, 4)
    saved_vs_baseline_g = max(0.0, round(baseline_co2_g - estimated_co2_g, 4))
    
    uncertainty_relative = combined_relative_uncertainty(calibration)
    uncertainty_min = round(max(0.0, estimated_co2_g * (1.0 - uncertainty_relative)), 4)
    uncertainty_max = round(estimated_co2_g * (1.0 + uncertainty_relative), 4)

    return {
        "estimated_co2_g": estimated_co2_g,
        "saved_vs_baseline_g": saved_vs_baseline_g,
        "baseline_g": baseline_co2_g,
        "estimated_tokens": estimated_tokens,
        "energy_assumption_kwh_per_1000_tokens": round(energy_per_1k_kwh, 6),
        "calibration_version": CALIBRATION_VERSION,
        "calibration_source": calibration.source,
        # Single relative band for this estimate, so consumers can apply it to
        # derived figures (e.g. emissions avoided) without re-running the maths.
        "uncertainty_relative": round(uncertainty_relative, 4),
        "uncertainty_components": {
            "token_estimation": calibration.token_relative_uncertainty,
            "model_energy": calibration.model_relative_uncertainty,
            "grid_intensity": calibration.grid_relative_uncertainty,
            "provider_region": calibration.region_relative_uncertainty,
            "fallback_behavior": calibration.fallback_relative_uncertainty,
        },
        "uncertainty_range_g": {
            "min": uncertainty_min,
            "max": uncertainty_max
        }
    }


async def route_query(tier: str, prompt_length: int = 50, mode: str = "balanced", confidence: float = 1.0) -> dict:
    region_info = await get_carbon_optimal_region()
    region_code = region_info["region"]
    intensity = region_info.get("carbon_intensity_g_kwh", 200.0)
    selection = select_model(tier, region_code, intensity, mode=mode, confidence=confidence, prompt_length=prompt_length)
    savings = compute_savings(selection["carbon_score"], intensity, prompt_length=prompt_length)
    return {
        "region": region_info,
        "model": selection,
        "savings": savings,
        "display": f"{selection['display_name']} via {region_code} ({region_info['energy_source']})",
    }
