"""
Multi-source carbon intensity provider.
Aggregates data from Electricity Maps, WattTime-style fallbacks, and static regional baselines.
"""

import os
import logging
import time
import asyncio
from typing import Optional, Dict, List

logger = logging.getLogger("EcoQuery.carbon")

ELECTRICITY_MAPS_API = "https://api.electricitymap.org/v3"

_cache: Dict[str, dict] = {"data": None, "timestamp": 0.0}
CACHE_TTL = 600

REGIONS = {
    "eu-west-1": {"name": "Ireland", "zone": "IE", "lat": 53.3, "lon": -6.3},
    "eu-west-2": {"name": "London", "zone": "GB", "lat": 51.5, "lon": -0.1},
    "eu-west-3": {"name": "Paris", "zone": "FR", "lat": 48.9, "lon": 2.3},
    "eu-central-1": {"name": "Frankfurt", "zone": "DE", "lat": 50.1, "lon": 8.7},
    "eu-north-1": {"name": "Stockholm", "zone": "SE", "lat": 59.3, "lon": 18.1},
    "us-east-1": {"name": "N. Virginia", "zone": "US-VIRGINIA-CAROLINAS", "lat": 37.4, "lon": -79.0},
    "us-west-1": {"name": "N. California", "zone": "US-CAL-NORTH", "lat": 37.4, "lon": -122.0},
    "us-west-2": {"name": "Oregon", "zone": "US-NW-PPM", "lat": 45.5, "lon": -122.7},
}

# Static regional baselines (g CO2/kWh) from IEA 2024 data
STATIC_REGIONAL_INTENSITY = {
    "eu-west-1": 316.0,
    "eu-west-2": 220.0,
    "eu-west-3": 56.0,
    "eu-central-1": 350.0,
    "eu-north-1": 13.0,
    "us-east-1": 380.0,
    "us-west-1": 200.0,
    "us-west-2": 80.0,
}


async def _fetch_electricity_maps(zone: str, api_key: str) -> Optional[float]:
    import httpx
    url = f"{ELECTRICITY_MAPS_API}/carbon-intensity/latest?zone={zone}"
    headers = {"auth-token": api_key}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data.get("carbonIntensity")
    except Exception as e:
        logger.warning(f"Electricity Maps API error for {zone}: {e}")
        return None


async def _fetch_multi_source(region_code: str, zone: str, api_key: str) -> Optional[float]:
    """Try Electricity Maps first, fall back to static baselines."""
    if api_key:
        intensity = await _fetch_electricity_maps(zone, api_key)
        if intensity is not None:
            return intensity

    static = STATIC_REGIONAL_INTENSITY.get(region_code)
    if static is not None:
        logger.info(f"Using static baseline for {region_code}: {static} g/kWh")
        return static

    return None


async def get_carbon_optimal_region() -> dict:
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"] < CACHE_TTL):
        return _cache["data"]

    api_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "")

    tasks = [
        _fetch_multi_source(code, info["zone"], api_key)
        for code, info in REGIONS.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    regions_with_intensity = []
    for (region_code, info), intensity in zip(REGIONS.items(), results):
        if isinstance(intensity, (int, float)):
            regions_with_intensity.append((region_code, info, float(intensity)))

    if regions_with_intensity:
        regions_with_intensity.sort(key=lambda x: x[2])
        best_code, best_info, best_intensity = regions_with_intensity[0]
        result = {
            "region": best_code,
            "energy_source": _estimate_source(best_intensity),
            "carbon_intensity_g_kwh": best_intensity,
            "estimated_savings_g_co2": _estimate_savings(best_intensity),
            "method": "electricity-maps-api" if api_key else "static-baselines",
            "all_regions": {
                code: {"intensity": intens, "source": REGIONS[code]["name"]}
                for code, _, intens in regions_with_intensity
            }
        }
    else:
        result = _mock_region()

    _cache["data"] = result
    _cache["timestamp"] = now
    return result


def _estimate_source(intensity: float) -> str:
    if intensity < 50:
        return "Hydro/Wind/Solar"
    elif intensity < 200:
        return "Mixed Renewables"
    elif intensity < 400:
        return "Natural Gas Mix"
    else:
        return "Coal Grid Baseline"


def _estimate_savings(intensity: float) -> float:
    baseline = 475.0
    savings = max(0.0, baseline - intensity) * 0.005
    return round(savings, 3)


def _mock_region() -> dict:
    return {
        "region": "eu-north-1",
        "energy_source": "Hydro/Wind",
        "carbon_intensity_g_kwh": 18.5,
        "estimated_savings_g_co2": 1.2,
        "method": "mock-fallback",
        "all_regions": {}
    }
