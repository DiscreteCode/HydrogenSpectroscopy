import numpy as np
import pytest

from physics import blackbody as bb


def test_wien_peak_matches_sun_approx():
    # The Sun's photosphere (~5778 K) peaks near 500-510 nm (visible green).
    peak = bb.wien_peak_wavelength_nm(5778)
    assert 480 < peak < 520


def test_hotter_star_peaks_bluer():
    peak_hot = bb.wien_peak_wavelength_nm(20000)
    peak_cool = bb.wien_peak_wavelength_nm(4000)
    assert peak_hot < peak_cool


def test_normalized_continuum_peaks_at_one():
    grid = np.linspace(100, 2000, 2000)
    continuum = bb.normalized_blackbody_continuum(grid, 9000.0)
    assert continuum.max() == pytest.approx(1.0, rel=1e-9)
    assert continuum.min() >= 0.0


def test_normalized_continuum_peak_near_wien_law():
    grid = np.linspace(100, 3000, 5000)
    temperature = 6000.0
    continuum = bb.normalized_blackbody_continuum(grid, temperature)
    peak_idx = np.argmax(continuum)
    expected_peak = bb.wien_peak_wavelength_nm(temperature)
    assert grid[peak_idx] == pytest.approx(expected_peak, rel=0.05)


def test_nonpositive_temperature_rejected():
    with pytest.raises(ValueError):
        bb.planck_spectral_radiance(500.0, 0.0)
    with pytest.raises(ValueError):
        bb.wien_peak_wavelength_nm(-100)


def test_radiance_is_positive():
    radiance = bb.planck_spectral_radiance(np.array([300.0, 500.0, 1000.0]), 5778.0)
    assert np.all(radiance > 0)
