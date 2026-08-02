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
    {
        "id": "gemma-4-31b-it:free",
        "provider": "Google",
        "tier": "green",
        "carbon_score": 2,
        "capability": "high",
        "openrouter_id": "google/gemma-4-31b-it:free",
        "description": "31B instruct-tuned, latest Gemma"
    },
    {
        "id": "gpt-oss-20b:free",
        "provider": "OpenAI",
        "tier": "balanced",
        "carbon_score": 3,
        "capability": "medium",
        "openrouter_id": "openai/gpt-oss-20b:free",
        "description": "20B open-source, OpenAI quality"
    },
    {
        "id": "north-mini-code:free",
        "provider": "Cohere",
        "tier": "balanced",
        "carbon_score": 4,
        "capability": "medium",
        "openrouter_id": "cohere/north-mini-code:free",
        "description": "Compact coding model, fast inference"
    },
    {
        "id": "ling-3.0-flash:free",
        "provider": "InclusionAI",
        "tier": "performance",
        "carbon_score": 5,
        "capability": "medium",
        "openrouter_id": "inclusionai/ling-3.0-flash:free",
        "description": "Flash model, ultra-fast responses"
    },
    # TokenReply-only free models (fallback when OpenRouter fails)
    {
        "id": "nemotron-3-ultra-free",
        "provider": "NVIDIA (TokenReply)",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "tr-nemotron-3-ultra-free",
        "description": "550B MoE via TokenReply, largest free model"
    },
    {
        "id": "mimo-v2.5-free",
        "provider": "Mimo (TokenReply)",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "tr-mimo-v2.5-free",
        "description": "Mimo v2.5, strong reasoning via TokenReply"
    },
    {
        "id": "mimo-v2.5-thinking-free",
        "provider": "Mimo (TokenReply)",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "tr-mimo-v2.5-thinking-free",
        "description": "Mimo v2.5 thinking, chain-of-thought via TokenReply"
    },
    {
        "id": "deepseek-v4-flash-free",
        "provider": "DeepSeek (TokenReply)",
        "tier": "balanced",
        "carbon_score": 3,
        "capability": "medium",
        "openrouter_id": "tr-deepseek-v4-flash-free",
        "description": "DeepSeek V4 flash via TokenReply"
    },
]

REGION_MODEL_AFFINITY = {
    "eu-west-1": ["nemotron-3-ultra-550b-a55b:free", "gemma-4-31b-it:free", "gpt-oss-20b:free"],
    "eu-west-2": ["nemotron-3-super-120b-a12b:free", "gemma-4-31b-it:free", "north-mini-code:free"],
    "eu-west-3": ["nemotron-3-ultra-550b-a55b:free", "gemma-4-31b-it:free", "ling-3.0-flash:free"],
    "eu-central-1": ["nemotron-3-super-120b-a12b:free", "gemma-4-31b-it:free", "gpt-oss-20b:free"],
    "eu-north-1": ["nemotron-3-ultra-550b-a55b:free", "gemma-4-31b-it:free"],
    "us-east-1": ["nemotron-3-ultra-550b-a55b:free", "gemma-4-31b-it:free", "gpt-oss-20b:free", "north-mini-code:free"],
    "us-west-1": ["nemotron-3-super-120b-a12b:free", "gemma-4-31b-it:free", "ling-3.0-flash:free"],
    "us-west-2": ["nemotron-3-ultra-550b-a55b:free", "gemma-4-31b-it:free", "gpt-oss-20b:free"],
}

MODEL_MAP = {m["id"]: m for m in CARBON_MODELS}
