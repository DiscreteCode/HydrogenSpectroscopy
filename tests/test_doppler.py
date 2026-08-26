import pytest

from physics import doppler as d


H_ALPHA_NM = 656.279


def test_zero_velocity_no_shift():
    observed = d.doppler_shift_classical(H_ALPHA_NM, 0.0)
    assert observed == pytest.approx(H_ALPHA_NM)


def test_receding_source_redshifts():
    observed = d.doppler_shift_classical(H_ALPHA_NM, velocity_kms=100.0)
    assert observed > H_ALPHA_NM


def test_approaching_source_blueshifts():
    observed = d.doppler_shift_classical(H_ALPHA_NM, velocity_kms=-100.0)
    assert observed < H_ALPHA_NM


def test_classical_shift_magnitude():
    # delta_lambda/lambda = v/c ; v=299.792458 km/s -> beta=0.001 exactly
    observed = d.doppler_shift_classical(H_ALPHA_NM, velocity_kms=299.792458)
    expected = H_ALPHA_NM * 1.001
    assert observed == pytest.approx(expected, rel=1e-9)


def test_classical_and_relativistic_agree_at_stellar_velocities():
    # At typical stellar radial velocities (tens to low hundreds of
    # km/s), classical and relativistic Doppler should agree to within
    # a tiny fraction of a percent.
    v = 150.0
    classical = d.doppler_shift_classical(H_ALPHA_NM, v)
    relativistic = d.doppler_shift_relativistic(H_ALPHA_NM, v)
    assert classical == pytest.approx(relativistic, rel=1e-6)


def test_relativistic_symmetric_time_dilation_effect():
    # Relativistic Doppler is NOT perfectly symmetric between + and -
    # velocity the way classical is (there's a second-order transverse
    # time dilation piece), but at v=0 both formulas must agree exactly.
    assert d.doppler_shift_relativistic(H_ALPHA_NM, 0.0) == pytest.approx(H_ALPHA_NM)


def test_velocity_from_shift_round_trip_classical():
    true_v = 87.3
    observed = d.doppler_shift_classical(H_ALPHA_NM, true_v)
    recovered_v = d.velocity_from_shift_kms(H_ALPHA_NM, observed, relativistic=False)
    assert recovered_v == pytest.approx(true_v, rel=1e-9)


def test_velocity_from_shift_round_trip_relativistic():
    true_v = -220.0
    observed = d.doppler_shift_relativistic(H_ALPHA_NM, true_v)
    recovered_v = d.velocity_from_shift_kms(H_ALPHA_NM, observed, relativistic=True)
    assert recovered_v == pytest.approx(true_v, rel=1e-6)


def test_superluminal_velocity_rejected():
    with pytest.raises(ValueError):
        d.doppler_shift_classical(H_ALPHA_NM, velocity_kms=300000.0)  # > c


def test_doppler_result_dataclass():
    result = d.doppler_result(H_ALPHA_NM, velocity_kms=50.0)
    assert result.rest_wavelength_nm == H_ALPHA_NM
    assert result.observed_wavelength_nm > H_ALPHA_NM
    assert result.velocity_kms == 50.0
    assert result.beta == pytest.approx(50.0 / 299792.458, rel=1e-6)
    assert result.relativistic is False


def test_nonpositive_wavelengths_rejected_in_inverse_problem():
    with pytest.raises(ValueError):
        d.velocity_from_shift_kms(0.0, 656.3)
    with pytest.raises(ValueError):
        d.velocity_from_shift_kms(656.3, -1.0)
