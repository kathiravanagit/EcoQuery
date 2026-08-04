"""
Model catalog with carbon efficiency ratings for EcoQuery.
All models are free-tier via OpenRouter.
"""

CARBON_MODELS = [
    {
        "id": "nemotron-3-ultra-550b-a55b:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "description": "550B MoE, largest free model, strong reasoning"
    },
    {
        "id": "nemotron-3-super-120b-a12b:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 2,
        "capability": "high",
        "openrouter_id": "nvidia/nemotron-3-super-120b-a12b:free",
        "description": "120B MoE, balanced performance and efficiency"
    },
]
