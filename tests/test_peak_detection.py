import numpy as np
import pytest

from physics.line_profiles import gaussian_profile
from spectroscopy import peak_detection as pd


def test_find_absorption_features_detects_known_dip():
    grid = np.linspace(600, 700, 5000)
    continuum = np.ones_like(grid)
    intensity = continuum - gaussian_profile(grid, 656.3, 0.4, 0.8)
    features = pd.find_absorption_features(grid, intensity, continuum_level=1.0, prominence=0.05)
    assert len(features) == 1
    assert features[0].wavelength_nm == pytest.approx(656.3, abs=0.05)


def test_find_absorption_features_detects_multiple_dips():
    grid = np.linspace(380, 700, 10000)
    continuum = np.ones_like(grid)
    intensity = continuum.copy()
    for center in (656.3, 486.1, 434.0, 410.2):
        intensity -= gaussian_profile(grid, center, 0.3, 0.6)
    features = pd.find_absorption_features(grid, intensity, continuum_level=1.0, prominence=0.05)
    assert len(features) == 4
    found_wavelengths = sorted(f.wavelength_nm for f in features)
    expected = sorted([656.3, 486.1, 434.0, 410.2])
    for found, exp in zip(found_wavelengths, expected):
        assert found == pytest.approx(exp, abs=0.1)


def test_find_emission_features_detects_known_peak():
    grid = np.linspace(600, 700, 5000)
    intensity = gaussian_profile(grid, 656.3, 1.0, 0.8)
    features = pd.find_emission_features(grid, intensity, prominence=0.1)
    assert len(features) == 1
    assert features[0].wavelength_nm == pytest.approx(656.3, abs=0.05)


def test_no_features_in_flat_spectrum():
    grid = np.linspace(400, 700, 1000)
    flat = np.ones_like(grid)
    features = pd.find_absorption_features(grid, flat, continuum_level=1.0)
    assert features == []


def test_estimate_local_continuum_shape():
    grid = np.linspace(400, 700, 2000)
    continuum_true = 1.0 + 0.0 * grid
    intensity = continuum_true - gaussian_profile(grid, 550, 0.5, 1.0)
    estimated = pd.estimate_local_continuum(grid, intensity, window_frac=0.1)
    # Away from the dip, the estimated continuum should be close to 1.0
    assert estimated[0] > 0.9
    assert estimated[-1] > 0.9


def test_absorption_features_report_prominence_and_width():
    grid = np.linspace(600, 700, 5000)
    continuum = np.ones_like(grid)
    intensity = continuum - gaussian_profile(grid, 656.3, 0.4, 0.8)
    features = pd.find_absorption_features(grid, intensity, continuum_level=1.0, prominence=0.05)
    assert len(features) == 1
    assert features[0].prominence > 0
    assert features[0].width_nm is not None
    assert features[0].width_nm > 0


def test_distance_nm_merges_close_features():
    grid = np.linspace(650, 660, 5000)
    continuum = np.ones_like(grid)
    # Two dips only 0.3 nm apart -- with a large minimum distance,
    # find_peaks should only report the more prominent one.
    intensity = continuum - gaussian_profile(grid, 655.0, 0.5, 0.1) - gaussian_profile(grid, 655.3, 0.3, 0.1)
    close_together = pd.find_absorption_features(grid, intensity, prominence=0.05, distance_nm=None)
    far_apart_required = pd.find_absorption_features(grid, intensity, prominence=0.05, distance_nm=2.0)
    assert len(close_together) >= len(far_apart_required)
    assert len(far_apart_required) == 1


def test_width_nm_filters_narrow_features():
    grid = np.linspace(600, 700, 20000)
    continuum = np.ones_like(grid)
    # A very narrow, spiky dip vs the smoother, well-known H-alpha dip.
    intensity = (
        continuum
        - gaussian_profile(grid, 656.3, 0.4, 0.8)
        - gaussian_profile(grid, 620.0, 0.3, 0.02)
    )
    all_features = pd.find_absorption_features(grid, intensity, prominence=0.05)
    wide_only = pd.find_absorption_features(grid, intensity, prominence=0.05, width_nm=0.3)
    assert len(all_features) == 2
    assert len(wide_only) == 1
    assert wide_only[0].wavelength_nm == pytest.approx(656.3, abs=0.05)


def test_emission_features_report_prominence():
    grid = np.linspace(600, 700, 5000)
    intensity = gaussian_profile(grid, 656.3, 1.0, 0.8)
    features = pd.find_emission_features(grid, intensity, prominence=0.1)
    assert features[0].prominence > 0


def test_short_spectrum_returns_no_crash():
    grid = np.array([600.0, 650.0])
    intensity = np.array([1.0, 1.0])
    assert pd.find_absorption_features(grid, intensity) == []
