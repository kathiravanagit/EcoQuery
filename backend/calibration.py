"""Versioned energy calibration data used for transparent estimates."""

import math
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


def combined_relative_uncertainty(calibration: Calibration = DEFAULT_CALIBRATION) -> float:
    """Root-sum-square of the calibrated error components.

    This is the single figure of merit quoted against any CO₂ estimate this
    module produces, so the UI can render `12.4 g ± 62%` without re-deriving it
    from the component list. Components are treated as independent, so the
    root-sum-square is the right combination rather than a plain sum.
    """
    return math.sqrt(sum(value ** 2 for value in (
        calibration.token_relative_uncertainty,
        calibration.model_relative_uncertainty,
        calibration.grid_relative_uncertainty,
        calibration.region_relative_uncertainty,
        calibration.fallback_relative_uncertainty,
    )))


def aggregate_uncertainty_pct(calibration: Calibration = DEFAULT_CALIBRATION) -> float:
    """Relative band (in percent) for a *summed* total of CO₂ estimates.

    The dominant error terms — model energy calibration, grid and region
    inference — are systematic rather than per-query noise, so they are fully
    correlated across readings. Summing N queries therefore does not shrink the
    band the way independent errors would (an N-reduction would need the
    1/sqrt(N) factor, which would imply precision the calibration cannot back).
    The total carries the same relative uncertainty as each estimate, which is
    the conservative and honest treatment for an aggregate.
    """
    return round(combined_relative_uncertainty(calibration) * 100, 1)


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
