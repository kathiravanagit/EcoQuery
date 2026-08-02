"""
Smart Carbon-Aware Router — routes requests to the greenest provider/region.
Supports: AWS Bedrock, Google Vertex AI, Ollama (self-hosted), OpenRouter (fallback).
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass
from carbon_collector import collector
from region_scorer import scorer, RegionScore

logger = logging.getLogger("EcoQuery.smart_router")


@dataclass
class Provider:
    """LLM provider with region info."""
    name: str
    region: str
    endpoint: str
    model: str
    supports_region_pinning: bool
    cost_per_1k_tokens: float
    api_key: str = ""


# Provider registry
PROVIDERS = {
    "aws-bedrock": {
        "regions": {
            "eu-west-1": {"endpoint": "bedrock.eu-west-1.amazonaws.com", "name": "Ireland"},
            "eu-west-2": {"endpoint": "bedrock.eu-west-2.amazonaws.com", "name": "London"},
            "eu-central-1": {"endpoint": "bedrock.eu-central-1.amazonaws.com", "name": "Frankfurt"},
            "us-east-1": {"endpoint": "bedrock.us-east-1.amazonaws.com", "name": "Virginia"},
            "us-west-2": {"endpoint": "bedrock.us-west-2.amazonaws.com", "name": "Oregon"},
        },
        "models": ["anthropic.claude-3-haiku", "amazon.titan-text-lite"],
        "requires_key": True,
        "env_key": "AWS_ACCESS_KEY_ID",
    },
    "google-vertex": {
        "regions": {
            "europe-west1": {"endpoint": "europe-west1-aiplatform.googleapis.com", "name": "Belgium"},
            "europe-west4": {"endpoint": "europe-west4-aiplatform.googleapis.com", "name": "Netherlands"},
            "us-central1": {"endpoint": "us-central1-aiplatform.googleapis.com", "name": "Iowa"},
            "asia-east1": {"endpoint": "asia-east1-aiplatform.googleapis.com", "name": "Taiwan"},
        },
        "models": ["gemini-2.0-flash", "gemini-1.5-pro"],
        "requires_key": True,
        "env_key": "GOOGLE_APPLICATION_CREDENTIALS",
    },
    "ollama": {
        "regions": {},  # Dynamic — from OLLAMA_ENDPOINTS env
        "models": ["llama3.2", "mistral", "codellama"],
        "requires_key": False,
        "env_key": "OLLAMA_BASE_URL",
    },
    "openrouter": {
        "regions": {"global": {"endpoint": "openrouter.ai/api/v1", "name": "Global"}},
        "models": ["nemotron-3-ultra-550b-a55b:free", "gemma-4-31b-it:free", "gpt-oss-20b:free"],
        "requires_key": True,
        "env_key": "OPENAI_API_KEY",
    },
}


class SmartRouter:
    """Routes requests to the greenest available provider/region."""

    def __init__(self):
        self._providers: List[Provider] = []
        self._load_providers()

    def _load_providers(self):
        """Load available providers from environment."""
        # AWS Bedrock
        if os.getenv("AWS_ACCESS_KEY_ID"):
            for region, info in PROVIDERS["aws-bedrock"]["regions"].items():
                self._providers.append(Provider(
                    name="aws-bedrock",
                    region=region,
                    endpoint=info["endpoint"],
                    model="anthropic.claude-3-haiku",
                    supports_region_pinning=True,
                    cost_per_1k_tokens=0.001,
                    api_key=os.getenv("AWS_ACCESS_KEY_ID", ""),
                ))

        # Google Vertex AI
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            for region, info in PROVIDERS["google-vertex"]["regions"].items():
                self._providers.append(Provider(
                    name="google-vertex",
                    region=region,
                    endpoint=info["endpoint"],
                    model="gemini-2.0-flash",
                    supports_region_pinning=True,
                    cost_per_1k_tokens=0.0005,
                ))

        # Ollama (self-hosted VPS)
        raw = os.getenv("OLLAMA_ENDPOINTS", "")
        if not raw:
            url = os.getenv("OLLAMA_BASE_URL", "")
            region = os.getenv("OLLAMA_REGION", "eu-north-1")
            if url:
                self._providers.append(Provider(
                    name="ollama",
                    region=region,
                    endpoint=url,
                    model="llama3.2",
                    supports_region_pinning=True,
                    cost_per_1k_tokens=0,
                ))
        else:
            for part in raw.split(","):
                part = part.strip()
                if ":" in part:
                    url, region = part.rsplit(":", 1)
                    self._providers.append(Provider(
                        name="ollama",
                        region=region,
                        endpoint=url,
                        model="llama3.2",
                        supports_region_pinning=True,
                        cost_per_1k_tokens=0,
                    ))

        # OpenRouter (fallback)
        if os.getenv("OPENAI_API_KEY"):
            self._providers.append(Provider(
                name="openrouter",
                region="global",
                endpoint="openrouter.ai/api/v1",
                model="nemotron-3-ultra-550b-a55b:free",
                supports_region_pinning=False,
                cost_per_1k_tokens=0,
                api_key=os.getenv("OPENAI_API_KEY", ""),
            ))

    async def route(
        self,
        query: str,
        mode: str = "eco",
        preferred_model: Optional[str] = None,
    ) -> dict:
        """Route query to greenest provider.

        Returns:
            {
                "provider": Provider,
                "score": RegionScore,
                "intensity": float,
                "is_green": bool,
                "alternatives": list,
            }
        """
        if not self._providers:
            raise RuntimeError("No providers configured")

        # Get carbon intensity for all provider regions
        tasks = []
        for p in self._providers:
            if p.supports_region_pinning:
                tasks.append(collector.get_intensity(p.region))

        intensities = await asyncio.gather(*tasks, return_exceptions=True)

        # Build region data for scoring
        region_data = []
        for i, provider in enumerate(self._providers):
            if provider.supports_region_pinning:
                intensity = intensities[i] if i < len(intensities) and not isinstance(intensities[i], Exception) else None
                if intensity:
                    region_data.append({
                        "region": provider.region,
                        "intensity": intensity["intensity"],
                        "energy_mix": intensity.get("energy", {}),
                    })

        # Rank regions
        ranked = scorer.rank_regions(region_data)

        # Find best provider
        best_provider = None
        best_score = None

        for score in ranked:
            for provider in self._providers:
                if provider.region == score.region:
                    if preferred_model and provider.model != preferred_model:
                        continue
                    best_provider = provider
                    best_score = score
                    break
            if best_provider:
                break

        # Fallback to any available provider
        if not best_provider:
            best_provider = self._providers[0]
            best_score = scorer.score_region(
                region=best_provider.region,
                intensity=400,
            )

        # Get alternatives
        alternatives = []
        for score in ranked[1:3]:
            for provider in self._providers:
                if provider.region == score.region:
                    alternatives.append({
                        "provider": provider.name,
                        "region": provider.region,
                        "score": score.total_score,
                        "intensity": score.intensity_g_kwh,
                    })

        return {
            "provider": best_provider,
            "score": best_score,
            "intensity": best_score.intensity_g_kwh,
            "is_green": best_score.is_green,
            "alternatives": alternatives,
        }

    def get_available_providers(self) -> List[Dict]:
        """List all available providers."""
        return [
            {
                "name": p.name,
                "region": p.region,
                "model": p.model,
                "cost_per_1k": p.cost_per_1k_tokens,
            }
            for p in self._providers
        ]


router = SmartRouter()
