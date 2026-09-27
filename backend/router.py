"""
Carbon-aware model router for EcoQuery.
Always routes with carbon-first priority.
"""

import logging
from carbon import get_carbon_optimal_region
from models import CARBON_MODELS

logger = logging.getLogger("EcoQuery.router")

MODEL_LATENCY = {
    "nemotron-3-ultra-550b-a55b:free": 2.0,
    "nemotron-3-super-120b-a12b:free": 1.5,
    "llama-4-scout": 1.2,
    "deepseek-chat-v3-0324:free": 1.8,
    "gpt-oss-120b:free": 2.5,
    "gpt-oss-20b:free": 1.0,
    "gemma-4-31b:free": 1.5,
}


def select_model(tier: str, region_code: str, carbon_intensity: float, mode: str = "balanced", confidence: float = 1.0, prompt_length: int = 50) -> dict:
    candidates = list(CARBON_MODELS)
    
    # 1. Quality Safeguard
    # The router should not choose a smaller model merely because it is greener.
    if tier == "complex" or (tier == "medium" and confidence < 0.75):
        candidates = [c for c in candidates if c["capability"] == "high"]
    elif tier == "medium":
        candidates = [c for c in candidates if c["capability"] in ("medium", "high")]
        
    if not candidates:
        candidates = list(CARBON_MODELS) # fallback if filtered out too strictly
        
    # Weights: (w1_quality, w2_carbon, w3_latency, w4_cost, w5_risk)
    weights = {
        "green": (1.0, 5.0, 1.0, 1.0, 1.0),
        "balanced": (2.0, 2.0, 1.0, 1.0, 1.0),
        "fast": (1.0, 1.0, 5.0, 1.0, 1.0),
        "quality": (5.0, 1.0, 1.0, 1.0, 1.0),
        "budget": (1.0, 1.0, 1.0, 5.0, 1.0),
    }
    w1, w2, w3, w4, w5 = weights.get(mode, weights["balanced"])
    
    best_score = float('inf')
    chosen = candidates[0]
    
    for c in candidates:
        # Quality risk: higher for lower capabilities if tier demands more
        quality_risk = 0.0
        if tier == "complex" and c["capability"] != "high": quality_risk = 10.0
        elif tier == "medium" and c["capability"] == "low": quality_risk = 5.0
        
        # Carbon cost
        energy_per_1k = 0.0002 * (c["carbon_score"] / 3.0)
        estimated_carbon = (prompt_length / 1000.0) * energy_per_1k * carbon_intensity
        
        # Latency
        latency = MODEL_LATENCY.get(c["id"], 2.0)
        
        # Cost (approximate)
        cost = 0.001 * c["carbon_score"] # simplistic mock cost
        
        # Provider failure risk (could be dynamic, fixed for now)
        provider_risk = 1.0 if c["provider"] == "Ollama (Local)" else 2.0
        
        total_score = (w1 * quality_risk) + (w2 * estimated_carbon) + (w3 * latency) + (w4 * cost) + (w5 * provider_risk)
        
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
        "reason": f"Objective score: {round(best_score, 2)} (Mode: {mode})"
    }


def compute_savings(model_carbon_score: int | float, region_intensity: float, prompt_length: int = 50) -> dict:
    estimated_tokens = max(10, int((prompt_length / 4.0) * 2.5))
    energy_per_1k_kwh = 0.0002 * (model_carbon_score / 3.0)
    energy_used_kwh = (estimated_tokens / 1000.0) * energy_per_1k_kwh
    estimated_co2_g = round(energy_used_kwh * region_intensity, 4)
    baseline_energy_kwh = (estimated_tokens / 1000.0) * 0.001
    baseline_co2_g = round(baseline_energy_kwh * 475.0, 4)
    saved_vs_baseline_g = max(0.0, round(baseline_co2_g - estimated_co2_g, 4))
    
    uncertainty_min = round(estimated_co2_g * 0.5, 4)
    uncertainty_max = round(estimated_co2_g * 2.0, 4)

    return {
        "estimated_co2_g": estimated_co2_g,
        "saved_vs_baseline_g": saved_vs_baseline_g,
        "baseline_g": baseline_co2_g,
        "estimated_tokens": estimated_tokens,
        "energy_assumption_kwh_per_1000_tokens": round(energy_per_1k_kwh, 6),
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
