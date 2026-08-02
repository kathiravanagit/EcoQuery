"""
Green Provider Router — routes to the greenest cloud provider using real-time carbon data.
Combines provider region knowledge with Electricity Maps zone-based carbon intensity.
"""

import os
import logging
import asyncio
import hashlib
from typing import Dict, List, Optional
from carbon_collector import collector

logger = logging.getLogger("EcoQuery.green_provider")


# Map OpenRouter providers to their datacenter regions + Electricity Maps zones
PROVIDER_REGIONS = {
    "anthropic": {
        "name": "Anthropic",
        "regions": {
            "gcp-us-east1": {"location": "South Carolina", "zone": "US-SE-CAR", "grid": "Mixed"},
            "gcp-us-west1": {"location": "Oregon", "zone": "US-NW-PACW", "grid": "Hydro"},
            "gcp-europe-west1": {"location": "Belgium", "zone": "BE", "grid": "Wind"},
            "gcp-europe-west4": {"location": "Netherlands", "zone": "NL", "grid": "Wind/Gas"},
        },
        "greenest_region": "gcp-us-west1",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "google": {
        "name": "Google",
        "regions": {
            "gcp-europe-west1": {"location": "Belgium", "zone": "BE", "grid": "Wind"},
            "gcp-europe-west4": {"location": "Netherlands", "zone": "NL", "grid": "Wind/Gas"},
            "gcp-us-central1": {"location": "Iowa", "zone": "US-MIDA", "grid": "Wind/Coal"},
            "gcp-us-east1": {"location": "South Carolina", "zone": "US-SE-CAR", "grid": "Mixed"},
            "gcp-asia-east1": {"location": "Taiwan", "zone": "TW", "grid": "Coal/Gas"},
        },
        "greenest_region": "gcp-europe-west1",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "microsoft": {
        "name": "Microsoft Azure",
        "regions": {
            "azure-north-europe": {"location": "Ireland", "zone": "IE", "grid": "Wind/Gas"},
            "azure-west-europe": {"location": "Netherlands", "zone": "NL", "grid": "Wind"},
            "azure-uksouth": {"location": "London", "zone": "GB", "grid": "Gas/Wind"},
            "azure-westus2": {"location": "Washington", "zone": "US-NW-PACW", "grid": "Hydro"},
        },
        "greenest_region": "azure-westus2",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "amazon": {
        "name": "Amazon AWS",
        "regions": {
            "aws-eu-west-1": {"location": "Ireland", "zone": "IE", "grid": "Wind/Gas"},
            "aws-eu-central-1": {"location": "Frankfurt", "zone": "DE", "grid": "Wind/Coal"},
            "aws-us-west-2": {"location": "Oregon", "zone": "US-NW-PACW", "grid": "Hydro"},
            "aws-ap-south-1": {"location": "Mumbai", "zone": "IN-SO", "grid": "Coal"},
        },
        "greenest_region": "aws-us-west-2",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "meta": {
        "name": "Meta (Facebook)",
        "regions": {
            "meta-us-west": {"location": "Oregon", "zone": "US-NW-PACW", "grid": "Hydro"},
            "meta-us-east": {"location": "Virginia", "zone": "US-MIDA", "grid": "Gas/Coal"},
            "meta-europe": {"location": "Sweden", "zone": "SE", "grid": "Hydro/Nuclear"},
        },
        "greenest_region": "meta-europe",
        "renewable_energy_pct": 100,
        "carbon_neutral": True,
    },
    "mistral": {
        "name": "Mistral AI",
        "regions": {
            "mistral-europe": {"location": "France", "zone": "FR", "grid": "Nuclear"},
            "mistral-us": {"location": "US", "zone": "US-CAL-CISO", "grid": "Mixed"},
        },
        "greenest_region": "mistral-europe",
        "renewable_energy_pct": 80,
        "carbon_neutral": False,
    },
    "deepseek": {
        "name": "DeepSeek",
        "regions": {
            "deepseek-china": {"location": "China", "zone": "CN", "grid": "Coal"},
        },
        "greenest_region": "deepseek-china",
        "renewable_energy_pct": 20,
        "carbon_neutral": False,
    },
    "nvidia": {
        "name": "NVIDIA",
        "regions": {
            "nvidia-us": {"location": "US", "zone": "US-CAL-CISO", "grid": "Mixed"},
            "nvidia-europe": {"location": "Germany", "zone": "DE", "grid": "Wind"},
        },
        "greenest_region": "nvidia-europe",
        "renewable_energy_pct": 60,
        "carbon_neutral": False,
    },
    "cohere": {
        "name": "Cohere",
        "regions": {
            "cohere-us": {"location": "US", "zone": "US-CAL-CISO", "grid": "Mixed"},
            "cohere-canada": {"location": "Canada", "zone": "CA-QC", "grid": "Hydro"},
        },
        "greenest_region": "cohere-canada",
        "renewable_energy_pct": 90,
        "carbon_neutral": True,
    },
    "xiaomi": {
        "name": "Xiaomi",
        "regions": {
            "xiaomi-china": {"location": "China", "zone": "CN", "grid": "Coal"},
        },
        "greenest_region": "xiaomi-china",
        "renewable_energy_pct": 20,
        "carbon_neutral": False,
    },
}


class GreenProviderRouter:
    """Routes to the greenest OpenRouter provider using real-time carbon data."""

    def __init__(self):
        self.providers = PROVIDER_REGIONS
        self._scores_cache: Dict[str, dict] = {}
        self._cache_time: float = 0

    async def _get_real_intensity(self, zone: str) -> Optional[float]:
        """Get real-time carbon intensity for a zone from Electricity Maps."""
        try:
            intensity_data = await collector.get_intensity(zone)
            return intensity_data.get("intensity")
        except Exception as e:
            logger.debug(f"Could not get real intensity for {zone}: {e}")
            return None

    async def get_provider_scores(self) -> List[dict]:
        """Score all providers using real-time carbon intensity data."""
        scores = []

        for provider_id, info in self.providers.items():
            greenest_region = info["greenest_region"]
            region_data = info["regions"][greenest_region]
            zone = region_data.get("zone", "")

            # Try real-time data from Electricity Maps
            real_intensity = await self._get_real_intensity(zone) if zone else None

            # Fallback to estimated grid intensity
            if real_intensity is None:
                real_intensity = self._estimate_grid_intensity(region_data["grid"])

            # Determine if green based on intensity
            is_green = real_intensity < 100

            # Simple score: lower intensity = better
            score = real_intensity

            scores.append({
                "provider": provider_id,
                "name": info["name"],
                "greenest_region": greenest_region,
                "location": region_data["location"],
                "zone": zone,
                "grid": region_data["grid"],
                "intensity": real_intensity,
                "score": score,
                "is_green": is_green,
                "renewable_pct": info["renewable_energy_pct"],
                "carbon_neutral": info["carbon_neutral"],
                "color": self._get_color(real_intensity),
            })

        # Sort by score (lowest = greenest)
        scores.sort(key=lambda x: x["score"])
        return scores

    async def route_to_greenest(self, preferred_provider: Optional[str] = None, query: str = "") -> dict:
        """Route to the greenest provider, varying by query to show different results.

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

        # Pick from top 3 greenest providers, varying by query content
        # This ensures different queries route to different green providers
        top_green = [s for s in scores if s["is_green"]][:3]
        if not top_green:
            top_green = scores[:3]

        if query and len(top_green) > 1:
            query_hash = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
            idx = query_hash % len(top_green)
            chosen = top_green[idx]
        else:
            chosen = top_green[0]

        return {
            "provider": chosen["provider"],
            "region": chosen["greenest_region"],
            "intensity": chosen["intensity"],
            "score": chosen["score"],
            "is_green": chosen["is_green"],
            "alternatives": [x for x in top_green if x["provider"] != chosen["provider"]][:2],
        }

    async def get_green_model(self, query: str = "") -> str:
        """Get the greenest model ID for OpenRouter."""
        route = await self.route_to_greenest()
        provider = route["provider"]

        GREEN_MODELS = {
            "anthropic": "anthropic/claude-3-haiku",
            "google": "google/gemma-4-31b-it:free",
            "microsoft": "openai/gpt-oss-20b:free",
            "amazon": "amazon/nova-micro-v1",
            "meta": "nvidia/nemotron-3-super-120b-a12b:free",
            "mistral": "cohere/north-mini-code:free",
            "cohere": "cohere/north-mini-code:free",
            "nvidia": "nvidia/nemotron-3-ultra-550b-a55b:free",
        }

        return GREEN_MODELS.get(provider, "nvidia/nemotron-3-ultra-550b-a55b:free")

    def _estimate_grid_intensity(self, grid_type: str) -> float:
        """Estimate carbon intensity from grid type description."""
        GRID_ESTIMATES = {
            "Hydro/Nuclear": 15,
            "Hydro": 30,
            "Nuclear": 50,
            "Wind": 100,
            "Wind/Nuclear": 80,
            "Wind/Gas": 180,
            "Gas/Wind": 200,
            "Gas": 350,
            "Mixed": 300,
            "Wind/Coal": 350,
            "Coal/Gas": 500,
            "Coal": 650,
        }
        return GRID_ESTIMATES.get(grid_type, 350)

    def _get_color(self, intensity: float) -> str:
        """Get color class based on carbon intensity."""
        if intensity < 50:
            return "green"
        elif intensity < 100:
            return "light-green"
        elif intensity < 200:
            return "yellow"
        elif intensity < 400:
            return "orange"
        else:
            return "red"

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
