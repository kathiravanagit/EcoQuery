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
    "llama-4-scout:free": 1.2,
    "deepseek-chat-v3-0324:free": 1.8,
    "gpt-oss-120b:free": 2.5,
    "gpt-oss-20b:free": 1.0,
    "gemma-4-31b:free": 1.5,
}


def select_model(tier: str, region_code: str, carbon_intensity: float) -> dict:
    candidates = list(CARBON_MODELS)

    if tier == "simple":
        candidates = [c for c in candidates if c["carbon_score"] <= 3] or candidates
    elif tier == "medium":
        candidates = [c for c in candidates if c["carbon_score"] <= 6] or candidates

    candidates.sort(key=lambda m: m["carbon_score"])

    chosen = candidates[0]
    estimated_latency = MODEL_LATENCY.get(chosen["id"], 2.0)

    return {
        "model": chosen["id"],
        "provider": chosen["provider"],
        "display_name": f"{chosen['provider']} {chosen['id']}",
        "openrouter_id": chosen["openrouter_id"],
        "tier": chosen["tier"],
        "carbon_score": chosen["carbon_score"],
        "estimated_latency_s": estimated_latency,
        "reason": f"{chosen['description']} (carbon score: {chosen['carbon_score']}/10)"
    }


def compute_savings(model_carbon_score: int | float, region_intensity: float, prompt_length: int = 50) -> dict:
    estimated_tokens = max(10, int((prompt_length / 4.0) * 2.5))
    energy_per_1k_kwh = 0.0002 * (model_carbon_score / 3.0)
    energy_used_kwh = (estimated_tokens / 1000.0) * energy_per_1k_kwh
    estimated_co2_g = round(energy_used_kwh * region_intensity, 4)
    baseline_energy_kwh = (estimated_tokens / 1000.0) * 0.001
    baseline_co2_g = round(baseline_energy_kwh * 475.0, 4)
    saved_vs_baseline_g = max(0.0, round(baseline_co2_g - estimated_co2_g, 4))

    return {
        "estimated_co2_g": estimated_co2_g,
        "saved_vs_baseline_g": saved_vs_baseline_g,
        "baseline_g": baseline_co2_g,
        "estimated_tokens": estimated_tokens
    }


async def route_query(tier: str, prompt_length: int = 50) -> dict:
    region_info = await get_carbon_optimal_region()
    region_code = region_info["region"]
    intensity = region_info.get("carbon_intensity_g_kwh", 200.0)
    selection = select_model(tier, region_code, intensity)
    savings = compute_savings(selection["carbon_score"], intensity, prompt_length=prompt_length)
    return {
        "region": region_info,
        "model": selection,
        "savings": savings,
        "display": f"{selection['display_name']} via {region_code} ({region_info['energy_source']})",
    }
