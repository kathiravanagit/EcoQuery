import sys
import types

import pytest

import energy
from energy import EnergyReading, measurement_type


def test_energy_measurement_type_distinguishes_sources():
    assert measurement_type(reading=EnergyReading(0.001, "intel_rapl", 1, 2)) == "measured"
    assert measurement_type(reading=None, provider_reported=True) == "provider_reported"
    assert measurement_type(reading=None) == "estimated"


def test_zero_energy_is_valid_measured_reading():
    reading = EnergyReading(0.0, "nvidia_nvml", 1, 2)
    assert measurement_type(reading=reading) == "measured"


def test_rapl_reading_is_converted_to_kwh(monkeypatch):
    # end() only samples the closing RAPL counter; the start value is passed in.
    monkeypatch.setattr(energy, "_read_rapl_uj", lambda: 4_600_000)
    reading = energy.end(10.0, 1_000_000, None)
    assert reading is not None
    assert reading.source == "intel_rapl"
    # 3_600_000 µJ = 3.6 J = 0.000001 kWh
    assert reading.energy_kwh == pytest.approx(0.000001)


def test_invalid_or_negative_rapl_delta_is_unavailable(monkeypatch):
    monkeypatch.setattr(energy, "_read_rapl_uj", lambda: 999)
    assert energy.end(10.0, 1_000, None) is None


class _FakeNvml:
    """One GPU whose lifetime counter (mJ) the test controls."""

    def __init__(self, total_mj: float, devices: int = 1):
        self._total_mj = total_mj
        self._devices = devices

    def nvmlDeviceGetCount(self):
        return self._devices

    def nvmlDeviceGetHandleByIndex(self, index):
        return index

    def nvmlDeviceGetTotalEnergyConsumption(self, handle):
        return self._total_mj


def test_nvml_reports_a_per_request_delta_in_kwh():
    # begin() saw 1_000_000 mJ, end() sees 4_600_000 mJ -> 3.6 kJ used.
    reading = energy.end(10.0, 1_000_000, _FakeNvml(4_600_000))
    assert reading is not None
    assert reading.source == "nvidia_nvml"
    # 3_600_000 mJ = 3.6 kJ = 0.001 kWh
    assert reading.energy_kwh == pytest.approx(0.001)


def test_nvml_without_an_opening_baseline_is_not_measured():
    # begin() used to return no NVML baseline, so end() summed the GPU's
    # lifetime energy since driver load and billed all of it to one request.
    assert energy.end(10.0, None, _FakeNvml(4_600_000)) is None


def test_nvml_negative_delta_is_unavailable():
    # Counter reset (driver reload) rather than a real per-request delta.
    assert energy.end(10.0, 5_000_000, _FakeNvml(4_600_000)) is None


def test_nvml_delta_sums_every_gpu():
    # begin() sums the same device set: 3 x 1_000_000 mJ at the open,
    # 3 x 4_600_000 mJ at the close -> 3 x 3_600_000 mJ used.
    reading = energy.end(10.0, 3 * 1_000_000, _FakeNvml(4_600_000, devices=3))
    assert reading is not None
    assert reading.energy_kwh == pytest.approx((3 * 3_600_000) / energy.MJ_PER_KWH)


def test_begin_captures_an_nvml_baseline(monkeypatch):
    fake = types.SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlDeviceGetCount=lambda: 1,
        nvmlDeviceGetHandleByIndex=lambda index: index,
        nvmlDeviceGetTotalEnergyConsumption=lambda handle: 1_000_000,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)

    _started_at, start_value, nvml = energy.begin()

    assert nvml is fake
    assert start_value == 1_000_000


def test_begin_falls_back_to_rapl_when_no_counter_is_readable(monkeypatch):
    fake = types.SimpleNamespace(
        nvmlInit=lambda: None,
        nvmlDeviceGetCount=lambda: 0,
        nvmlDeviceGetHandleByIndex=lambda index: index,
        nvmlDeviceGetTotalEnergyConsumption=lambda handle: 0,
    )
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    monkeypatch.setattr(energy, "_read_rapl_uj", lambda: 7_777)

    _started_at, start_value, nvml = energy.begin()

    assert nvml is None
    assert start_value == 7_777
