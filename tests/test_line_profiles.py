import numpy as np
import pytest

from physics import line_profiles as lp


def test_gaussian_peak_at_center_equals_amplitude():
    grid = np.linspace(600, 700, 10001)
    profile = lp.gaussian_profile(grid, center_nm=656.3, amplitude=5.0, sigma_nm=1.0)
    assert profile.max() == pytest.approx(5.0, rel=1e-3)
    peak_idx = np.argmax(profile)
    assert grid[peak_idx] == pytest.approx(656.3, abs=0.02)


def test_gaussian_symmetric_about_center():
    grid = np.linspace(650, 662, 4001)
    profile = lp.gaussian_profile(grid, center_nm=656.0, amplitude=1.0, sigma_nm=0.5)
    # value 2nm to the left should equal value 2nm to the right
    left = lp.gaussian_profile(np.array([654.0]), 656.0, 1.0, 0.5)[0]
    right = lp.gaussian_profile(np.array([658.0]), 656.0, 1.0, 0.5)[0]
    assert left == pytest.approx(right, rel=1e-9)


def test_gaussian_integral_matches_analytic_formula():
    # Integral of a Gaussian A*exp(-(x-x0)^2/2sigma^2) dx = A*sigma*sqrt(2*pi)
    grid = np.linspace(-50, 50, 200001)
    amplitude, sigma = 2.0, 3.0
    profile = lp.gaussian_profile(grid, center_nm=0.0, amplitude=amplitude, sigma_nm=sigma)
    numeric_integral = np.trapezoid(profile, grid)
    analytic_integral = amplitude * sigma * np.sqrt(2 * np.pi)
    assert numeric_integral == pytest.approx(analytic_integral, rel=1e-3)


def test_gaussian_rejects_nonpositive_sigma():
    grid = np.linspace(600, 700, 100)
    with pytest.raises(ValueError):
        lp.gaussian_profile(grid, 656.3, 1.0, sigma_nm=0.0)
    with pytest.raises(ValueError):
        lp.gaussian_profile(grid, 656.3, 1.0, sigma_nm=-1.0)


def test_lorentzian_peak_at_center_equals_amplitude():
    grid = np.linspace(600, 700, 10001)
    profile = lp.lorentzian_profile(grid, center_nm=656.3, amplitude=3.0, gamma_nm=0.5)
    assert profile.max() == pytest.approx(3.0, rel=1e-6)


def test_lorentzian_half_max_at_gamma():
    gamma = 1.0
    amplitude = 4.0
    value_at_gamma = lp.lorentzian_profile(np.array([1.0]), 0.0, amplitude, gamma)[0]
    assert value_at_gamma == pytest.approx(amplitude / 2.0, rel=1e-9)


def test_line_profile_dispatch_matches_direct_calls():
    grid = np.linspace(600, 700, 500)
    g1 = lp.line_profile(lp.ProfileKind.GAUSSIAN, grid, 656.3, 1.0, 0.8)
    g2 = lp.gaussian_profile(grid, 656.3, 1.0, 0.8)
    assert np.allclose(g1, g2)

    l1 = lp.line_profile(lp.ProfileKind.LORENTZIAN, grid, 656.3, 1.0, 0.8)
    l2 = lp.lorentzian_profile(grid, 656.3, 1.0, 0.8)
    assert np.allclose(l1, l2)


def test_fwhm_sigma_round_trip():
    sigma = 0.75
    fwhm = lp.fwhm_from_sigma(sigma)
    assert lp.sigma_from_fwhm(fwhm) == pytest.approx(sigma, rel=1e-9)
    # sanity: FWHM should be a bit more than 2x sigma
    assert 2.3 < fwhm / sigma < 2.4
