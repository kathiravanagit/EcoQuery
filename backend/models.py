"""
Model catalog with carbon efficiency ratings for EcoQuery.
All models are free-tier via OpenCode Zen.
"""

CARBON_MODELS = [
    {
        "id": "deepseek-v4-flash-free",
        "provider": "OpenCode Zen",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "deepseek-v4-flash-free",
        "description": "Fast DeepSeek V4 lane, 1M context, reasoning capable"
    },
    {
        "id": "ling-3.0-flash-free",
        "provider": "OpenCode Zen",
        "tier": "green",
        "carbon_score": 2,
        "capability": "medium",
        "openrouter_id": "ling-3.0-flash-free",
        "description": "Ultra-fast flash model for simple queries"
    },
    {
        "id": "laguna-s-2.1-free",
        "provider": "OpenCode Zen",
        "tier": "balanced",
        "carbon_score": 3,
        "capability": "very-high",
        "openrouter_id": "laguna-s-2.1-free",
        "description": "Poolside coding agent, 128K context, tool calling"
    },
    {
        "id": "mimo-v2.5-free",
        "provider": "OpenCode Zen",
        "tier": "balanced",
        "carbon_score": 4,
        "capability": "very-high",
        "openrouter_id": "mimo-v2.5-free",
        "description": "Balanced reasoning and coding model"
    },
    {
        "id": "north-mini-code-free",
        "provider": "OpenCode Zen",
        "tier": "balanced",
        "carbon_score": 5,
        "capability": "high",
        "openrouter_id": "north-mini-code-free",
        "description": "Code-focused model, 256K context"
    },
    {
        "id": "nemotron-3-ultra-free",
        "provider": "OpenCode Zen",
        "tier": "performance",
        "carbon_score": 6,
        "capability": "highest",
        "openrouter_id": "nemotron-3-ultra-free",
        "description": "NVIDIA 550B MoE, 1M context, highest capability"
    },
]

REGION_MODEL_AFFINITY = {
    "eu-west-1": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "laguna-s-2.1-free", "mimo-v2.5-free"],
    "eu-west-2": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "north-mini-code-free"],
    "eu-west-3": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "mimo-v2.5-free", "laguna-s-2.1-free"],
    "eu-central-1": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "north-mini-code-free", "mimo-v2.5-free"],
    "eu-north-1": ["deepseek-v4-flash-free", "ling-3.0-flash-free"],
    "us-east-1": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "laguna-s-2.1-free", "mimo-v2.5-free", "nemotron-3-ultra-free"],
    "us-west-1": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "mimo-v2.5-free", "north-mini-code-free", "nemotron-3-ultra-free"],
    "us-west-2": ["deepseek-v4-flash-free", "ling-3.0-flash-free", "north-mini-code-free", "nemotron-3-ultra-free"],
}

MODEL_MAP = {m["id"]: m for m in CARBON_MODELS}
