"""
Model catalog with carbon efficiency ratings for EcoQuery.
All models are free-tier via OpenRouter.
"""

CARBON_MODELS = [
    {
        "id": "nemotron-3-ultra-550b-a55b:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 8,
        "capability": "high",
        "openrouter_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "description": "550B MoE, largest free model, strong reasoning",
        "supports_images": False,
    },
    {
        "id": "nemotron-3-super-120b-a12b:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 5,
        "capability": "high",
        "openrouter_id": "nvidia/nemotron-3-super-120b-a12b:free",
        "description": "120B MoE, balanced performance and efficiency",
        "supports_images": False,
    },
    {
        "id": "llama-4-scout",
        "provider": "Meta",
        "tier": "green",
        "carbon_score": 6,
        "capability": "high",
        "openrouter_id": "meta-llama/llama-4-scout",
        "description": "Fast multimodal, 10M context, high-volume tasks",
        "supports_images": True,
    },
    {
        "id": "gpt-oss-120b:free",
        "provider": "OpenAI",
        "tier": "balanced",
        "carbon_score": 7,
        "capability": "high",
        "openrouter_id": "openai/gpt-oss-120b:free",
        "description": "Open-source GPT, strong coding and reasoning",
        "supports_images": False,
    },
    {
        "id": "deepseek-chat-v3-0324:free",
        "provider": "DeepSeek",
        "tier": "balanced",
        "carbon_score": 6,
        "capability": "high",
        "openrouter_id": "deepseek/deepseek-chat-v3-0324:free",
        "description": "General writing, summarizing, Q&A, 64K context",
        "supports_images": False,
    },
    {
        "id": "gemma-4-31b:free",
        "provider": "Google",
        "tier": "green",
        "carbon_score": 3,
        "capability": "medium",
        "openrouter_id": "google/gemma-4-31b:free",
        "description": "Multilingual, 262K context, general use",
        "supports_images": False,
    },
    {
        "id": "gpt-oss-20b:free",
        "provider": "OpenAI",
        "tier": "green",
        "carbon_score": 1,
        "capability": "low",
        "openrouter_id": "openai/gpt-oss-20b:free",
        "description": "Fast lightweight GPT, quick tasks, low latency",
        "supports_images": False,
    },
]

VISION_MODEL = "meta-llama/llama-4-scout"

# Ordered fallback chain — try these in order if primary fails
FALLBACK_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "meta-llama/llama-4-scout",
    "openai/gpt-oss-120b:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b:free",
]
