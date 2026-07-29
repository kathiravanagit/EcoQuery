"""
Region Scorer — scores regions by carbon intensity, energy source, and latency.
Lower score = greener region.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("EcoQuery.region_scorer")


@dataclass
class RegionScore:
    """Score for a region."""
    region: str
    carbon_score: int  # 1-10 (1=greenest, 10=dirtiest)
    energy_score: int  # 1-10 (1=cleanest, 10=dirtiest)
    latency_score: int  # 1-10 (1=lowest, 10=highest)
    total_score: float  # Weighted total
    intensity_g_kwh: float
    primary_energy: str
    is_green: bool


# Carbon intensity thresholds (g CO₂/kWh)
CARBON_THRESHOLDS = {
    "ultra_low": 50,    # Hydro/nuclear dominant
    "low": 150,         # Wind/nuclear mix
    "medium": 300,      # Gas/renewable mix
    "high": 500,        # Coal/gas mix
    "very_high": 700,   # Coal dominant
}

# Energy source scores (lower = cleaner)
ENERGY_SCORES = {
    "hydro": 1,
    "nuclear": 2,
    "wind": 2,
    "solar": 3,
    "geothermal": 2,
    "biomass": 4,
    "gas": 6,
    "coal": 10,
    "oil": 9,
}


class RegionScorer:
    """Scores regions based on carbon intensity and energy mix."""

    def __init__(self):
        self.weights = {
            "carbon": 0.6,   # Carbon intensity weight
            "energy": 0.3,   # Energy source weight
            "latency": 0.1,  # Latency weight (optional)
        }

    def score_carbon(self, intensity: float) -> int:
        """Score carbon intensity (1=greenest, 10=dirtiest)."""
        if intensity <= CARBON_THRESHOLDS["ultra_low"]:
            return 1
        elif intensity <= CARBON_THRESHOLDS["low"]:
            return 2
        elif intensity <= CARBON_THRESHOLDS["medium"]:
            return 5
        elif intensity <= CARBON_THRESHOLDS["high"]:
            return 7
        elif intensity <= CARBON_THRESHOLDS["very_high"]:
            return 9
        else:
            return 10

    def score_energy(self, energy_mix: Dict[str, float]) -> int:
        """Score energy mix (1=cleanest, 10=dirtiest)."""
        if not energy_mix:
            return 5  # Unknown = medium score

        total_pct = sum(energy_mix.values())
        if total_pct == 0:
            return 5

        weighted_score = 0
        for source, pct in energy_mix.items():
            score = ENERGY_SCORES.get(source.lower(), 5)
            weighted_score += (pct / total_pct) * score

        # Normalize to 1-10
        return max(1, min(10, round(weighted_score)))

    def score_latency(self, latency_ms: float) -> int:
        """Score latency (1=fastest, 10=slowest)."""
        if latency_ms < 50:
            return 1
        elif latency_ms < 100:
            return 2
        elif latency_ms < 200:
            return 4
        elif latency_ms < 500:
            return 6
        else:
            return 8

    def score_region(
        self,
        region: str,
        intensity: float,
        energy_mix: Optional[Dict[str, float]] = None,
        latency_ms: Optional[float] = None,
    ) -> RegionScore:
        """Calculate total score for a region."""
        carbon = self.score_carbon(intensity)
        energy = self.score_energy(energy_mix or {})
        latency = self.score_latency(latency_ms or 200)

        total = (
            carbon * self.weights["carbon"]
            + energy * self.weights["energy"]
            + latency * self.weights["latency"]
        )

        # Determine primary energy source
        if energy_mix:
            primary = max(energy_mix, key=energy_mix.get)
        else:
            primary = "unknown"

        return RegionScore(
            region=region,
            carbon_score=carbon,
            energy_score=energy,
            latency_score=latency,
            total_score=round(total, 2),
            intensity_g_kwh=intensity,
            primary_energy=primary,
            is_green=total <= 3.0,
        )

    def rank_regions(
        self,
        regions: List[Dict],
    ) -> List[RegionScore]:
        """Rank multiple regions from greenest to dirtiest.

        regions: [{"region": str, "intensity": float, "energy_mix": dict, "latency_ms": float}]
        """
        scores = []
        for r in regions:
            score = self.score_region(
                region=r["region"],
                intensity=r.get("intensity", 400),
                energy_mix=r.get("energy_mix"),
                latency_ms=r.get("latency_ms"),
            )
            scores.append(score)

        # Sort by total score (lowest = greenest)
        return sorted(scores, key=lambda s: s.total_score)

    def get_greenest(
        self,
        regions: List[Dict],
    ) -> Optional[RegionScore]:
        """Get the single greenest region."""
        ranked = self.rank_regions(regions)
        return ranked[0] if ranked else None

    def is_green(self, intensity: float) -> bool:
        """Check if a region is considered green."""
        return intensity <= CARBON_THRESHOLDS["low"]

    def get_color(self, intensity: float) -> str:
        """Get color coding for intensity."""
        if intensity <= CARBON_THRESHOLDS["ultra_low"]:
            return "#22c55e"  # Green
        elif intensity <= CARBON_THRESHOLDS["low"]:
            return "#84cc16"  # Light green
        elif intensity <= CARBON_THRESHOLDS["medium"]:
            return "#eab308"  # Yellow
        elif intensity <= CARBON_THRESHOLDS["high"]:
            return "#f97316"  # Orange
        else:
            return "#ef4444"  # Red


scorer = RegionScorer()
