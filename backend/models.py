"""
Model catalog with carbon efficiency ratings for EcoQuery.

Every entry is a genuinely free (`:free`) OpenRouter model that was
live-probed for an actual completion before being added here — a model
appearing in OpenRouter's catalog is not the same as it answering.

`carbon_score` is an energy proxy: higher means larger/more carbon, so the
router prefers a low score. `capability` drives the quality safeguard (a
complex query only ever sees `high` models).
"""

CARBON_MODELS = [
    {
        "id": "nemotron-3-ultra-550b-a55b:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 8,
        "capability": "high",
        "openrouter_id": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "description": "550B frontier reasoning, 1M context, largest free model",
        "supports_images": False,
    },
    {
        "id": "dots-3-note-preview:free",
        "provider": "Dots Studio",
        "tier": "balanced",
        "carbon_score": 6,
        "capability": "medium",
        "openrouter_id": "dots-studio/dots-3-note-preview:free",
        "description": "Open-weight MoE, 512K context, image and video input",
        "supports_images": True,
    },
    {
        # OpenRouter retired the free variant of `nemotron-3-super-120b-a12b`
        # (the paid id survives, so the slug itself still resolves for paying
        # accounts — which is how a dead free id hides from a price check).
        # `nemotron-3.5-super-vl` fills that slot: same 120B/12B-active class,
        # already in the catalog, so no new energy proxy is invented.
        "id": "nemotron-3.5-super-vl:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 5,
        # Promoted from medium: it is the only other 120B-class free model, and
        # `complex` filters to `high` — without it that tier has one candidate.
        "capability": "high",
        "openrouter_id": "nvidia/nemotron-3.5-super-vl:free",
        "description": "120B MoE (12B active) vision-language model, 1M context, image and video input",
        "supports_images": True,
    },
    {
        "id": "nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "provider": "NVIDIA",
        "tier": "green",
        "carbon_score": 3,
        "capability": "medium",
        "openrouter_id": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "description": "30B multimodal reasoning, audio/image/video input",
        "supports_images": True,
    },
    {
        "id": "north-mini-code:free",
        "provider": "Cohere",
        "tier": "balanced",
        "carbon_score": 2,
        "capability": "medium",
        "openrouter_id": "cohere/north-mini-code:free",
        "description": "Agentic coding model, 256K context",
        "supports_images": False,
    },
    {
        "id": "lfm-2.5-2.6b:free",
        "provider": "LiquidAI",
        "tier": "green",
        "carbon_score": 1,
        "capability": "low",
        "openrouter_id": "liquid/lfm-2.5-2.6b:free",
        "description": "2.6B compact reasoning model, quick tasks, low latency",
        "supports_images": False,
    },
]

# Must be an entry of CARBON_MODELS — chat.py looks the vision model up there
# to reject image uploads when no vision-capable model is available.
#
# Was `qwen3.8-27b:free`, which OpenRouter retired: no qwen free model remains
# in the catalog at all, so every image upload was routing to an id that 404s.
# Replaced only after live-probing it for a real completion at >16 max_tokens
# — the two Gemma candidates both answer 429 "rate-limited upstream", and a
# model that is listed and free but never answers is the failure this comment
# exists to prevent.
VISION_MODEL = "nemotron-3.5-super-vl:free"

# Ordered fallback chain — try these in order if primary fails
FALLBACK_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "dots-studio/dots-3-note-preview:free",
    "cohere/north-mini-code:free",
    "liquid/lfm-2.5-2.6b:free",
]
