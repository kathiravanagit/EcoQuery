"""
Model catalog with carbon efficiency ratings for EcoQuery.
Includes support for Cloud (OpenAI, Anthropic, Groq) and Local (Ollama) inference.
"""

CARBON_MODELS = [
    {
        "id": "groq-llama-3.1-70b",
        "provider": "Groq",
        "tier": "green",
        "carbon_score": 1,
        "capability": "high",
        "openrouter_id": "groq/llama-3.1-70b",
        "description": "Ultra-fast LPU inference with high energy efficiency"
    },
    {
        "id": "gemini-2.5-flash-lite",
        "provider": "Google",
        "tier": "green",
        "carbon_score": 1,
        "capability": "medium",
        "openrouter_id": "google/gemini-2.5-flash-lite",
        "description": "Ultra-efficient, ideal for simple queries"
    },
    {
        "id": "llama-3.1-8b",
        "provider": "Meta",
        "tier": "green",
        "carbon_score": 1,
        "capability": "medium",
        "openrouter_id": "meta-llama/llama-3.1-8b-instruct",
        "description": "Lightweight open-source model"
    },
    {
        "id": "gpt-4o-mini",
        "provider": "OpenAI",
        "tier": "green",
        "carbon_score": 2,
        "capability": "high",
        "openrouter_id": "openai/gpt-4o-mini",
        "description": "Highly efficient cloud model, excellent for most queries"
    },
    {
        "id": "claude-3-haiku",
        "provider": "Anthropic",
        "tier": "green",
        "carbon_score": 3,
        "capability": "high",
        "openrouter_id": "anthropic/claude-3-haiku",
        "description": "Fast and efficient with strong reasoning"
    },
    {
        "id": "groq-mixtral-8x7b",
        "provider": "Groq",
        "tier": "balanced",
        "carbon_score": 3,
        "capability": "high",
        "openrouter_id": "groq/mixtral-8x7b",
        "description": "High-throughput sparse MoE on specialized hardware"
    },
    {
        "id": "gpt-4o",
        "provider": "OpenAI",
        "tier": "balanced",
        "carbon_score": 5,
        "capability": "very-high",
        "openrouter_id": "openai/gpt-4o",
        "description": "Strong all-rounder with good efficiency"
    },
    {
        "id": "gemini-2.5-flash",
        "provider": "Google",
        "tier": "balanced",
        "carbon_score": 4,
        "capability": "very-high",
        "openrouter_id": "google/gemini-2.5-flash",
        "description": "Fast, capable, moderate carbon cost"
    },
    {
        "id": "claude-3.5-sonnet",
        "provider": "Anthropic",
        "tier": "balanced",
        "carbon_score": 5,
        "capability": "very-high",
        "openrouter_id": "anthropic/claude-3.5-sonnet",
        "description": "Excellent reasoning with balanced efficiency"
    },
    {
        "id": "llama-3.1-70b",
        "provider": "Meta",
        "tier": "balanced",
        "carbon_score": 6,
        "capability": "high",
        "openrouter_id": "meta-llama/llama-3.1-70b-instruct",
        "description": "Capable open-source model"
    },
    {
        "id": "gpt-4.5",
        "provider": "OpenAI",
        "tier": "performance",
        "carbon_score": 9,
        "capability": "highest",
        "openrouter_id": "openai/gpt-4.5-preview",
        "description": "Maximum capability, higher carbon cost"
    },
    {
        "id": "gemini-2.5-pro",
        "provider": "Google",
        "tier": "performance",
        "carbon_score": 8,
        "capability": "highest",
        "openrouter_id": "google/gemini-2.5-pro",
        "description": "Google's most capable, moderate-high carbon"
    },
    {
        "id": "claude-3.5-opus",
        "provider": "Anthropic",
        "tier": "performance",
        "carbon_score": 10,
        "capability": "highest",
        "openrouter_id": "anthropic/claude-3.5-opus",
        "description": "Anthropic's most powerful, higher carbon cost"
    },
    {
        "id": "llama-3.1-405b",
        "provider": "Meta",
        "tier": "performance",
        "carbon_score": 9,
        "capability": "highest",
        "openrouter_id": "meta-llama/llama-3.1-405b-instruct",
        "description": "Largest open-source model"
    },
]

REGION_MODEL_AFFINITY = {
    "eu-west-1": ["gpt-4o-mini", "claude-3-haiku", "gpt-4o", "claude-3.5-sonnet", "groq-llama-3.1-70b"],
    "eu-west-2": ["gpt-4o-mini", "llama-3.1-8b", "gpt-4o", "llama-3.1-70b"],
    "eu-west-3": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "claude-3-haiku", "claude-3.5-sonnet"],
    "eu-central-1": ["gpt-4o-mini", "gpt-4o", "llama-3.1-8b", "llama-3.1-70b", "groq-mixtral-8x7b"],
    "eu-north-1": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gpt-4o-mini"],
    "us-east-1": ["gpt-4o-mini", "gpt-4o", "gpt-4.5", "claude-3-haiku", "claude-3.5-sonnet", "claude-3.5-opus"],
    "us-west-1": ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-pro", "llama-3.1-8b", "llama-3.1-70b", "llama-3.1-405b"],
    "us-west-2": ["gpt-4o-mini", "gpt-4o", "gpt-4.5", "llama-3.1-8b", "llama-3.1-70b", "groq-llama-3.1-70b"],
}

MODEL_MAP = {m["id"]: m for m in CARBON_MODELS}
