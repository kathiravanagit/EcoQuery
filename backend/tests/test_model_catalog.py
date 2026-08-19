import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import CARBON_MODELS, FALLBACK_MODELS, VISION_MODEL


def test_llama_scout_uses_current_openrouter_slug():
    llama = next(model for model in CARBON_MODELS if model["provider"] == "Meta")

    assert llama["id"] == "llama-4-scout"
    assert llama["openrouter_id"] == "meta-llama/llama-4-scout"
    assert VISION_MODEL == llama["openrouter_id"]
    assert llama["openrouter_id"] in FALLBACK_MODELS