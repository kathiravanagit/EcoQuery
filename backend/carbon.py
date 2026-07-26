import os
import logging
import time
import asyncio
from typing import Optional

logger = logging.getLogger("EcoQuery.carbon")

ELECTRICITY_MAPS_API = "https://api.electricitymap.org/v3"

# In-memory cache for carbon data (TTL = 10 minutes)
_cache = {"data": None, "timestamp": 0.0}
CACHE_TTL = 600

REGIONS = {
    "eu-west-1": {"name": "Ireland", "zone": "IE"},
    "eu-west-2": {"name": "London", "zone": "GB"},
    "eu-west-3": {"name": "Paris", "zone": "FR"},
    "eu-central-1": {"name": "Frankfurt", "zone": "DE"},
    "eu-north-1": {"name": "Stockholm", "zone": "SE"},
    "us-east-1": {"name": "N. Virginia", "zone": "US-VIRGINIA-CAROLINAS"},
    "us-west-1": {"name": "N. California", "zone": "US-CAL-NORTH"},
    "us-west-2": {"name": "Oregon", "zone": "US-NW-PPM"},
}

async def get_carbon_intensity(zone: str, api_key: str) -> Optional[float]:
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

async def get_carbon_optimal_region() -> dict:
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"] < CACHE_TTL):
        return _cache["data"]

    api_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "")

    if api_key:
        # Fetch all region carbon intensities in parallel using asyncio.gather
        tasks = [get_carbon_intensity(info["zone"], api_key) for info in REGIONS.values()]
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
                "method": "electricity-maps-api"
            }
            _cache["data"] = result
            _cache["timestamp"] = now
            return result

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
        "method": "mock-fallback"
    }

