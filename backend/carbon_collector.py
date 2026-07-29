"""
Carbon Data Collector — fetches real-time carbon intensity data.
Sources: Electricity Maps API (real-time) + IEA 2024 baselines (fallback).
"""

import os
import logging
import time
import asyncio
import httpx
from typing import Optional, Dict

logger = logging.getLogger("EcoQuery.carbon_collector")

ELECTRICITY_MAPS_API = "https://api.electricitymap.org/v3"
CACHE_TTL = 300  # 5 minutes

# IEA 2024 baselines (g CO₂/kWh) — used when API unavailable
IEA_BASELINES = {
    "seattle": 30,
    "stockholm": 13,
    "paris": 55,
    "quebec": 2,
    "iceland": 0,
    "norway": 1,
    "frankfurt": 180,
    "amsterdam": 150,
    "london": 200,
    "dublin": 300,
    "tokyo": 450,
    "singapore": 400,
    "mumbai": 700,
    "virginia": 350,
    "california": 250,
    "oregon": 80,
    "montreal": 2,
    "saopaulo": 75,
    "sydney": 500,
    "taipei": 500,
}

# Energy source profiles per region
ENERGY_SOURCES = {
    "seattle": {"hydro": 90, "nuclear": 5, "wind": 3, "gas": 2},
    "stockholm": {"nuclear": 40, "hydro": 45, "wind": 15},
    "paris": {"nuclear": 70, "wind": 15, "hydro": 10, "gas": 5},
    "frankfurt": {"wind": 30, "coal": 25, "gas": 20, "nuclear": 15, "solar": 10},
    "amsterdam": {"wind": 45, "gas": 30, "nuclear": 10, "solar": 10, "coal": 5},
    "london": {"gas": 35, "wind": 30, "nuclear": 15, "coal": 10, "solar": 10},
    "virginia": {"gas": 40, "nuclear": 30, "coal": 15, "wind": 10, "solar": 5},
    "tokyo": {"gas": 40, "nuclear": 25, "coal": 20, "renewable": 15},
    "mumbai": {"coal": 55, "gas": 25, "renewable": 15, "nuclear": 5},
    "singapore": {"gas": 95, "solar": 5},
}


class CarbonDataCollector:
    """Fetches real-time carbon intensity from multiple sources."""

    def __init__(self):
        self.api_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "")
        self._cache: Dict[str, dict] = {}
        self._cache_time: Dict[str, float] = {}

    async def get_intensity(self, zone: str) -> dict:
        """Get carbon intensity for a zone.

        Returns: {"intensity": float, "source": str, "timestamp": str}
        """
        # Check cache
        if zone in self._cache:
            age = time.time() - self._cache_time.get(zone, 0)
            if age < CACHE_TTL:
                return self._cache[zone]

        # Try Electricity Maps API
        if self.api_key:
            try:
                result = await self._fetch_electricity_maps(zone)
                self._cache[zone] = result
                self._cache_time[zone] = time.time()
                return result
            except Exception as e:
                logger.warning(f"Electricity Maps failed for {zone}: {e}")

        # Fallback to IEA baselines
        result = self._get_iea_baseline(zone)
        self._cache[zone] = result
        self._cache_time[zone] = time.time()
        return result

    async def _fetch_electricity_maps(self, zone: str) -> dict:
        """Fetch from Electricity Maps API."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{ELECTRICITY_MAPS_API}/carbon-intensity/latest",
                params={"zone": zone},
                headers={"auth-token": self.api_key},
            )
            response.raise_for_status()
            data = response.json()

        return {
            "intensity": data["carbonIntensity"],
            "source": "electricity_maps",
            "timestamp": data.get("datetime", ""),
            "energy": data.get("energyMix", {}),
        }

    def _get_iea_baseline(self, zone: str) -> dict:
        """Fallback to IEA 2024 baselines."""
        # Try exact match
        if zone in IEA_BASELINES:
            return {
                "intensity": IEA_BASELINES[zone],
                "source": "iea_2024_baseline",
                "timestamp": "",
                "energy": ENERGY_SOURCES.get(zone, {}),
            }

        # Try partial match
        zone_lower = zone.lower()
        for key in IEA_BASELINES:
            if key in zone_lower or zone_lower in key:
                return {
                    "intensity": IEA_BASELINES[key],
                    "source": "iea_2024_baseline",
                    "timestamp": "",
                    "energy": ENERGY_SOURCES.get(key, {}),
                }

        # Default fallback
        return {
            "intensity": 400,
            "source": "default_fallback",
            "timestamp": "",
            "energy": {},
        }

    async def get_all_regions(self, zones: list) -> dict:
        """Get intensity for multiple zones concurrently."""
        tasks = {zone: self.get_intensity(zone) for zone in zones}
        results = {}

        for zone, coro in tasks.items():
            try:
                results[zone] = await coro
            except Exception as e:
                logger.error(f"Failed to get intensity for {zone}: {e}")
                results[zone] = self._get_iea_baseline(zone)

        return results

    def get_energy_source(self, zone: str) -> str:
        """Get primary energy source for a zone."""
        sources = ENERGY_SOURCES.get(zone, {})
        if not sources:
            return "unknown"
        return max(sources, key=sources.get)

    def get_green_hours(self, zone: str) -> list:
        """Get hours when grid is typically greenest (solar + wind peak)."""
        # Wind peaks at night, solar peaks midday
        sources = ENERGY_SOURCES.get(zone, {})
        wind_pct = sources.get("wind", 0) + sources.get("hydro", 0)
        solar_pct = sources.get("solar", 0)

        green_hours = []

        # Wind/hydro hours (night/early morning)
        if wind_pct > 30:
            green_hours.extend([1, 2, 3, 4, 5, 22, 23])

        # Solar hours (midday)
        if solar_pct >= 10:
            green_hours.extend([10, 11, 12, 13, 14])

        return sorted(set(green_hours)) if green_hours else [2, 3, 4, 5]


collector = CarbonDataCollector()
