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
