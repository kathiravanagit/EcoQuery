"""Optional local energy telemetry for inference workloads.

Telemetry is deliberately best-effort. Cloud-provider workloads are never
reported as measured because EcoQuery cannot access the provider hardware.
"""

from __future__ import annotations

import glob
import logging
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("EcoQuery.energy")

# Intel RAPL `energy_uj` is microjoules. 1 kWh = 3.6e12 µJ.
UJ_PER_KWH = 3_600_000_000_000.0
# NVML `nvmlDeviceGetTotalEnergyConsumption` is millijoules since the driver
# loaded. 1 kWh = 3.6e6 J = 3.6e9 mJ.
MJ_PER_KWH = 3_600_000_000.0


@dataclass(frozen=True)
class EnergyReading:
    energy_kwh: float
    source: str
    started_at: float
    ended_at: float


def _read_rapl_uj() -> Optional[int]:
    values = []
    for path in glob.glob("/sys/class/powercap/intel-rapl:* /energy_uj".replace(" ", "")):
        try:
            with open(path, encoding="utf-8") as handle:
                values.append(int(handle.read().strip()))
        except (OSError, ValueError):
            continue
    return sum(values) if values else None


def _nvml_total_mj(nvml: object) -> Optional[float]:
    """Lifetime millijoules summed over every GPU, or None if any is unreadable.

    A partial reading would produce a delta against a baseline taken over a
    different device set, so one failing device voids the whole sample.
    """
    total = 0.0
    count = int(nvml.nvmlDeviceGetCount())  # type: ignore[attr-defined]
    if count <= 0:
        return None
    for index in range(count):
        handle = nvml.nvmlDeviceGetHandleByIndex(index)  # type: ignore[attr-defined]
        total += float(nvml.nvmlDeviceGetTotalEnergyConsumption(handle))  # type: ignore[attr-defined]
    return total


def begin() -> tuple[float, Optional[float], Optional[object]]:
    """Start a local telemetry sample using NVML or CPU RAPL when available.

    The middle value is the opening counter for whichever source is active —
    microjoules for RAPL, millijoules across every GPU for NVML — so `end()`
    can report this request's delta. Capturing the NVML baseline matters:
    without it the closing read is the GPU's lifetime total since boot, which
    would be billed to a single request.
    """
    started_at = time.time()
    try:
        import pynvml  # type: ignore[import-not-found]

        pynvml.nvmlInit()
        baseline = _nvml_total_mj(pynvml)
        if baseline is not None:
            return started_at, baseline, pynvml
        # Init worked but no counter is readable: fall through to RAPL rather
        # than returning an NVML handle that can only yield a lifetime total.
    except Exception:
        pass
    return started_at, _read_rapl_uj(), None


def end(started_at: float, start_value: Optional[float], nvml: Optional[object]) -> Optional[EnergyReading]:
    """Finish a sample, rejecting invalid readings instead of fabricating data."""
    ended_at = time.time()
    try:
        if nvml is not None:
            if start_value is None:
                # No opening baseline, so there is no per-request delta to
                # report. Returning the lifetime total here is how cumulative
                # GPU energy since boot got attributed to one request.
                return None
            end_mj = _nvml_total_mj(nvml)
            if end_mj is None:
                return None
            delta_mj = end_mj - float(start_value)
            if delta_mj < 0:
                # Counter went backwards (driver reload): not a usable delta.
                return None
            return EnergyReading(delta_mj / MJ_PER_KWH, "nvidia_nvml", started_at, ended_at)
        if start_value is not None:
            end_rapl_uj = _read_rapl_uj()
            if end_rapl_uj is not None and end_rapl_uj >= start_value:
                energy_kwh = (end_rapl_uj - start_value) / UJ_PER_KWH
                return EnergyReading(energy_kwh, "intel_rapl", started_at, ended_at)
    except Exception as exc:
        logger.debug("Local energy telemetry unavailable: %s", exc)
    return None


def measurement_type(*, reading: Optional[EnergyReading], provider_reported: bool = False) -> str:
    if reading is not None:
        return "measured"
    if provider_reported:
        return "provider_reported"
    return "estimated"
