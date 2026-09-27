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


def begin() -> tuple[float, Optional[int], Optional[object]]:
    """Start a local telemetry sample using NVML or CPU RAPL when available."""
    started_at = time.time()
    nvml = None
    try:
        import pynvml  # type: ignore[import-not-found]

        pynvml.nvmlInit()
        nvml = pynvml
        return started_at, None, nvml
    except Exception:
        return started_at, _read_rapl_uj(), None


def end(started_at: float, start_rapl_uj: Optional[int], nvml: Optional[object]) -> Optional[EnergyReading]:
    """Finish a sample, rejecting invalid readings instead of fabricating data."""
    ended_at = time.time()
    try:
        if nvml is not None:
            total_mwh = 0.0
            count = nvml.nvmlDeviceGetCount()
            for index in range(count):
                handle = nvml.nvmlDeviceGetHandleByIndex(index)
                total_mwh += float(nvml.nvmlDeviceGetTotalEnergyConsumption(handle))
            energy_kwh = total_mwh / 1_000_000.0
            if energy_kwh >= 0:
                return EnergyReading(energy_kwh, "nvidia_nvml", started_at, ended_at)
        elif start_rapl_uj is not None:
            end_rapl_uj = _read_rapl_uj()
            if end_rapl_uj is not None and end_rapl_uj >= start_rapl_uj:
                return EnergyReading((end_rapl_uj - start_rapl_uj) / 3_600_000_000.0, "intel_rapl", started_at, ended_at)
    except Exception as exc:
        logger.debug("Local energy telemetry unavailable: %s", exc)
    return None


def measurement_type(*, reading: Optional[EnergyReading], provider_reported: bool = False) -> str:
    if reading is not None:
        return "measured"
    if provider_reported:
        return "provider_reported"
    return "estimated"
