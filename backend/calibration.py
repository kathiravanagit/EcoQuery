"""Versioned energy calibration data used for transparent estimates."""

from dataclasses import dataclass


CALIBRATION_VERSION = "2026-09-27-v1"


@dataclass(frozen=True)
class Calibration:
    energy_kwh_per_1000_tokens: float
    token_relative_uncertainty: float
    model_relative_uncertainty: float
    grid_relative_uncertainty: float
    region_relative_uncertainty: float
    fallback_relative_uncertainty: float
    source: str


DEFAULT_CALIBRATION = Calibration(
    energy_kwh_per_1000_tokens=0.0002,
    token_relative_uncertainty=0.20,
    model_relative_uncertainty=0.50,
    grid_relative_uncertainty=0.15,
    region_relative_uncertainty=0.25,
    fallback_relative_uncertainty=0.10,
    source="default-model-calibration; replace with measured workload data",
)


def get_calibration(model_carbon_score: float) -> Calibration:
    """Return the current versioned calibration for a model score.

    The score scaling preserves existing routing behavior while keeping the
    calibration version and uncertainty factors visible in API metadata.
    """
    return Calibration(
        energy_kwh_per_1000_tokens=DEFAULT_CALIBRATION.energy_kwh_per_1000_tokens * (model_carbon_score / 3.0),
        token_relative_uncertainty=DEFAULT_CALIBRATION.token_relative_uncertainty,
        model_relative_uncertainty=DEFAULT_CALIBRATION.model_relative_uncertainty,
        grid_relative_uncertainty=DEFAULT_CALIBRATION.grid_relative_uncertainty,
        region_relative_uncertainty=DEFAULT_CALIBRATION.region_relative_uncertainty,
        fallback_relative_uncertainty=DEFAULT_CALIBRATION.fallback_relative_uncertainty,
        source=DEFAULT_CALIBRATION.source,
    )
