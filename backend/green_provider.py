"""
Green Provider Router — miniature version of Bedrock/Vertex region selection.
Maps OpenRouter providers to their datacenter regions and routes to the greenest.
No cloud account needed — works with existing OpenRouter key.
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional
from carbon_collector import collector
from region_scorer import scorer

logger = logging.getLogger("EcoQuery.green_provider")


# Map OpenRouter providers to their datacenter regions
# Based on public documentation from each provider
PROVIDER_REGIONS = {
    "anthropic": {
        "name": "Anthropic",
        "regions": {
            "gcp-us-east1": {"location": "South Carolina", "intensity": 400, "grid": "Mixed"},
            "gcp-us-west1": {"location": "Oregon", "intensity": 80, "grid": "Hydro"},
            "gcp-europe-west1": {"location": "Belgium", "intensity": 150, "grid": "Wind"},
            "gcp-europe-west4": {"location": "Netherlands", "intensity": 160, "grid": "Wind/Gas"},
        },
        "greenest_region": "gcp-us-west1",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "google": {
        "name": "Google",
        "regions": {
            "gcp-europe-west1": {"location": "Belgium", "intensity": 150, "grid": "Wind"},
            "gcp-europe-west4": {"location": "Netherlands", "intensity": 160, "grid": "Wind/Gas"},
            "gcp-us-central1": {"location": "Iowa", "intensity": 300, "grid": "Wind/Coal"},
            "gcp-us-east1": {"location": "South Carolina", "intensity": 400, "grid": "Mixed"},
            "gcp-asia-east1": {"location": "Taiwan", "intensity": 500, "grid": "Coal/Gas"},
        },
        "greenest_region": "gcp-europe-west1",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "microsoft": {
        "name": "Microsoft Azure",
        "regions": {
            "azure-north europe": {"location": "Ireland", "intensity": 300, "grid": "Wind/Gas"},
            "azure-west europe": {"location": "Netherlands", "intensity": 160, "grid": "Wind"},
            "azure-uksouth": {"location": "London", "intensity": 200, "grid": "Gas/Wind"},
            "azure-westus2": {"location": "Washington", "intensity": 80, "grid": "Hydro"},
        },
        "greenest_region": "azure-westus2",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "amazon": {
        "name": "Amazon AWS",
        "regions": {
            "aws-eu-west-1": {"location": "Ireland", "intensity": 300, "grid": "Wind/Gas"},
            "aws-eu-central-1": {"location": "Frankfurt", "intensity": 180, "grid": "Wind/Coal"},
            "aws-us-west-2": {"location": "Oregon", "intensity": 80, "grid": "Hydro"},
            "aws-ap-south-1": {"location": "Mumbai", "intensity": 700, "grid": "Coal"},
        },
        "greenest_region": "aws-us-west-2",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "meta": {
        "name": "Meta (Facebook)",
        "regions": {
            "meta-us-west": {"location": "Oregon", "intensity": 80, "grid": "Hydro"},
            "meta-us-east": {"location": "Virginia", "intensity": 350, "grid": "Gas/Coal"},
            "meta-europe": {"location": "Sweden", "intensity": 13, "grid": "Hydro/Nuclear"},
        },
        "greenest_region": "meta-europe",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "mistral": {
        "name": "Mistral AI",
        "regions": {
            "mistral-europe": {"location": "France", "intensity": 55, "grid": "Nuclear"},
            "mistral-us": {"location": "US", "intensity": 350, "grid": "Mixed"},
        },
        "greenest_region": "mistral-europe",
        "renewable_energy_pct": 80,
        "carbon_neutral": False,
    },
    "deepseek": {
        "name": "DeepSeek",
        "regions": {
            "deepseek-china": {"location": "China", "intensity": 550, "grid": "Coal"},
        },
        "greenest_region": "deepseek-china",
        "renewable_energy_pct": 20,
        "carbon_neutral": False,
    },
    "nvidia": {
        "name": "NVIDIA",
        "regions": {
            "nvidia-us": {"location": "US", "intensity": 350, "grid": "Mixed"},
            "nvidia-europe": {"location": "Germany", "intensity": 180, "grid": "Wind"},
        },
        "greenest_region": "nvidia-europe",
        "renewable_energy_pct": 60,
        "carbon_neutral": False,
    },
    "cohere": {
        "name": "Cohere",
        "regions": {
            "cohere-us": {"location": "US", "intensity": 350, "grid": "Mixed"},
            "cohere-canada": {"location": "Canada", "intensity": 120, "grid": "Hydro"},
        },
        "greenest_region": "cohere-canada",
        "renewable_energy_pct": 90,
        "carbon_neutral": True,
    },
    "xiaomi": {
        "name": "Xiaomi",
        "regions": {
            "xiaomi-china": {"location": "China", "intensity": 550, "grid": "Coal"},
        },
        "greenest_region": "xiaomi-china",
        "renewable_energy_pct": 20,
        "carbon_neutral": False,
    },
}


class GreenProviderRouter:
    """Routes to the greenest OpenRouter provider based on real-time carbon data."""

    def __init__(self):
        self.providers = PROVIDER_REGIONS
        self._scores_cache: Dict[str, dict] = {}
        self._cache_time: float = 0

    async def get_provider_scores(self) -> List[dict]:
        """Score all providers by their greenest region's carbon intensity."""
        scores = []

        for provider_id, info in self.providers.items():
            # Get real-time intensity for greenest region
            greenest_region = info["greenest_region"]
            region_data = info["regions"][greenest_region]

            # Try to get real-time data
            try:
                # Map provider region to Electricity Maps zone
                zone = self._map_to_zone(greenest_region)
                if zone:
                    intensity_data = await collector.get_intensity(zone)
                    real_intensity = intensity_data["intensity"]
                else:
                    real_intensity = region_data["intensity"]
            except Exception:
                real_intensity = region_data["intensity"]

            # Score the provider
            score = scorer.score_region(
                region=greenest_region,
                intensity=real_intensity,
            )

            scores.append({
                "provider": provider_id,
                "name": info["name"],
                "greenest_region": greenest_region,
                "location": region_data["location"],
                "grid": region_data["grid"],
                "intensity": real_intensity,
                "score": score.total_score,
                "is_green": score.is_green,
                "renewable_pct": info["renewable_energy_pct"],
                "carbon_neutral": info["carbon_neutral"],
                "color": scorer.get_color(real_intensity),
            })

        # Sort by score (lowest = greenest)
        scores.sort(key=lambda x: x["score"])
        return scores

    async def route_to_greenest(self, preferred_provider: Optional[str] = None) -> dict:
        """Route to the greenest provider.

        Returns:
            {
                "provider": str,
                "region": str,
                "intensity": float,
                "score": float,
                "alternatives": list,
            }
        """
        scores = await self.get_provider_scores()

        if preferred_provider:
            for s in scores:
                if s["provider"] == preferred_provider:
                    return {
                        "provider": s["provider"],
                        "region": s["greenest_region"],
                        "intensity": s["intensity"],
                        "score": s["score"],
                        "is_green": s["is_green"],
                        "alternatives": [x for x in scores if x["provider"] != preferred_provider][:2],
                    }

        # Return greenest
        best = scores[0]
        return {
            "provider": best["provider"],
            "region": best["greenest_region"],
            "intensity": best["intensity"],
            "score": best["score"],
            "is_green": best["is_green"],
            "alternatives": scores[1:3],
        }

    async def get_green_model(self, query: str = "") -> str:
        """Get the greenest model ID for OpenRouter.

        Usage: model = await router.get_green_model()
        """
        route = await self.route_to_greenest()
        provider = route["provider"]

        # Map provider to OpenRouter model
        GREEN_MODELS = {
            "anthropic": "anthropic/claude-3-haiku",
            "google": "google/gemini-2.0-flash-001",
            "microsoft": "microsoft/phi-3-mini-128k-instruct",
            "amazon": "amazon/nova-micro-v1",
            "meta": "meta-llama/llama-3.1-8b-instruct",
            "mistral": "mistralai/mistral-7b-instruct",
            "cohere": "cohere/command-r",
            "nvidia": "nvidia/nemotron-3-ultra",
        }

        return GREEN_MODELS.get(provider, "deepseek/deepseek-v4-flash")

    def _map_to_zone(self, region: str) -> Optional[str]:
        """Map provider region to Electricity Maps zone."""
        ZONE_MAP = {
            "gcp-us-east1": "US-SE",
            "gcp-us-west1": "US-NW",
            "gcp-europe-west1": "DE",
            "gcp-europe-west4": "NL",
            "gcp-us-central1": "US-MISO",
            "gcp-asia-east1": "TW",
            "azure-north europe": "IE",
            "azure-west europe": "NL",
            "azure-uksouth": "GB",
            "azure-westus2": "US-NW",
            "aws-eu-west-1": "IE",
            "aws-eu-central-1": "DE",
            "aws-us-west-2": "US-NW",
            "aws-ap-south-1": "IN-SOUTH",
            "meta-us-west": "US-NW",
            "meta-us-east": "US-VIRGINIA-CAROLINAS",
            "meta-europe": "SE",
            "mistral-europe": "FR",
            "cohere-canada": "CA-QC",
        }
        return ZONE_MAP.get(region)

    def get_all_providers(self) -> List[dict]:
        """List all providers with their regions."""
        result = []
        for pid, info in self.providers.items():
            result.append({
                "id": pid,
                "name": info["name"],
                "greenest_region": info["greenest_region"],
                "renewable_pct": info["renewable_energy_pct"],
                "carbon_neutral": info["carbon_neutral"],
            })
        return result


green_router = GreenProviderRouter()
