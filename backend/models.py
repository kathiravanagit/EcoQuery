"""
Model catalog with carbon efficiency ratings for EcoQuery.
All models are free-tier via OpenRouter.
"""

CARBON_MODELS = [
    {
        "id": "deepseek-v4-flash",
        "provider": "DeepSeek",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "deepseek/deepseek-v4-flash:free",
        "description": "Fast DeepSeek V4 lane, 1M context, reasoning capable"
    },
    {
        "id": "ling-3.0-flash",
        "provider": "InclusionAI",
        "tier": "green",
        "carbon_score": 2,
        "capability": "medium",
        "openrouter_id": "inclusionai/ling-3.0-flash:free",
        "description": "124B MoE, ultra-fast flash model for simple queries"
    },
    {
        "id": "laguna-s-2.1",
        "provider": "Poolside",
        "tier": "balanced",
        "carbon_score": 3,
        "capability": "very-high",
        "openrouter_id": "poolside/laguna-s-2.1:free",
        "description": "Poolside coding agent, 128K context, tool calling"
    },
    {
        "id": "mimo-v2.5",
        "provider": "Xiaomi",
        "tier": "balanced",
        "carbon_score": 4,
        "capability": "very-high",
        "openrouter_id": "xiaomi/mimo-v2.5:free",
        "description": "Balanced reasoning and coding model"
    },
    {
        "id": "north-mini-code",
        "provider": "Cohere",
        "tier": "balanced",
        "carbon_score": 5,
        "capability": "high",
        "openrouter_id": "cohere/north-mini-code:free",
        "description": "30B MoE, code-focused, 256K context"
    },
    {
        "id": "nemotron-3-ultra",
        "provider": "NVIDIA",
        "tier": "performance",
        "carbon_score": 6,
        "capability": "highest",
        "openrouter_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "description": "550B MoE, 1M context, highest capability"
    },
]

REGION_MODEL_AFFINITY = {
    "eu-west-1": ["deepseek-v4-flash", "ling-3.0-flash", "laguna-s-2.1", "mimo-v2.5"],
    "eu-west-2": ["deepseek-v4-flash", "ling-3.0-flash", "north-mini-code"],
    "eu-west-3": ["deepseek-v4-flash", "ling-3.0-flash", "mimo-v2.5", "laguna-s-2.1"],
    "eu-central-1": ["deepseek-v4-flash", "ling-3.0-flash", "north-mini-code", "mimo-v2.5"],
    "eu-north-1": ["deepseek-v4-flash", "ling-3.0-flash"],
    "us-east-1": ["deepseek-v4-flash", "ling-3.0-flash", "laguna-s-2.1", "mimo-v2.5", "nemotron-3-ultra"],
    "us-west-1": ["deepseek-v4-flash", "ling-3.0-flash", "mimo-v2.5", "north-mini-code", "nemotron-3-ultra"],
    "us-west-2": ["deepseek-v4-flash", "ling-3.0-flash", "north-mini-code", "nemotron-3-ultra"],
}

MODEL_MAP = {m["id"]: m for m in CARBON_MODELS}
