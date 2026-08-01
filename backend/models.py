"""
Model catalog with carbon efficiency ratings for EcoQuery.
All models are free-tier via OpenRouter.
"""

CARBON_MODELS = [
    {
        "id": "deepseek-r1-0528:free",
        "provider": "DeepSeek",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "deepseek/deepseek-r1-0528:free",
        "description": "DeepSeek R1 reasoning model, 671B MoE"
    },
    {
        "id": "qwen3-235b-a22b:free",
        "provider": "Alibaba",
        "tier": "green",
        "carbon_score": 2,
        "capability": "high",
        "openrouter_id": "qwen/qwen3-235b-a22b:free",
        "description": "235B MoE, strong reasoning and coding"
    },
    {
        "id": "llama-4-maverick:free",
        "provider": "Meta",
        "tier": "green",
        "carbon_score": 2,
        "capability": "high",
        "openrouter_id": "meta-llama/llama-4-maverick:free",
        "description": "400B MoE, 1M context, multimodal"
    },
    {
        "id": "gemma-3-27b-it:free",
        "provider": "Google",
        "tier": "balanced",
        "carbon_score": 3,
        "capability": "medium",
        "openrouter_id": "google/gemma-3-27b-it:free",
        "description": "27B instruct-tuned, fast and efficient"
    },
    {
        "id": "mistral-small-3.1-24b-instruct:free",
        "provider": "Mistral",
        "tier": "balanced",
        "carbon_score": 4,
        "capability": "medium",
        "openrouter_id": "mistralai/mistral-small-3.1-24b-instruct:free",
        "description": "24B, 128K context, function calling"
    },
    {
        "id": "phi-4-reasoning:free",
        "provider": "Microsoft",
        "tier": "performance",
        "carbon_score": 5,
        "capability": "high",
        "openrouter_id": "microsoft/phi-4-reasoning:free",
        "description": "14B, advanced reasoning capabilities"
    },
]

REGION_MODEL_AFFINITY = {
    "eu-west-1": ["deepseek-r1-0528:free", "qwen3-235b-a22b:free", "llama-4-maverick:free"],
    "eu-west-2": ["deepseek-r1-0528:free", "gemma-3-27b-it:free", "mistral-small-3.1-24b-instruct:free"],
    "eu-west-3": ["deepseek-r1-0528:free", "qwen3-235b-a22b:free", "llama-4-maverick:free"],
    "eu-central-1": ["deepseek-r1-0528:free", "gemma-3-27b-it:free", "mistral-small-3.1-24b-instruct:free"],
    "eu-north-1": ["deepseek-r1-0528:free", "qwen3-235b-a22b:free"],
    "us-east-1": ["deepseek-r1-0528:free", "qwen3-235b-a22b:free", "llama-4-maverick:free", "phi-4-reasoning:free"],
    "us-west-1": ["deepseek-r1-0528:free", "qwen3-235b-a22b:free", "gemma-3-27b-it:free", "phi-4-reasoning:free"],
    "us-west-2": ["deepseek-r1-0528:free", "gemma-3-27b-it:free", "phi-4-reasoning:free"],
}

MODEL_MAP = {m["id"]: m for m in CARBON_MODELS}
