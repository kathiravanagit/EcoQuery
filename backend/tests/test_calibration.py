from calibration import CALIBRATION_VERSION, get_calibration


def test_calibration_is_versioned_and_scales_by_model_score():
    low = get_calibration(1)
    high = get_calibration(6)
    assert CALIBRATION_VERSION
    assert low.energy_kwh_per_1000_tokens < high.energy_kwh_per_1000_tokens
    assert low.token_relative_uncertainty > 0
    assert low.model_relative_uncertainty > low.token_relative_uncertainty
