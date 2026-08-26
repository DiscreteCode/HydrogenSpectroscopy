import numpy as np
import pytest

from physics.spectral_series import get_series_transitions
from physics.transitions import compute_emission_transition
from spectroscopy import spectrum as sp


def test_wavelength_grid_basic():
    grid = sp.build_wavelength_grid(400, 700, 1000)
    assert len(grid) == 1000
    assert grid[0] == pytest.approx(400)
    assert grid[-1] == pytest.approx(700)


def test_wavelength_grid_rejects_bad_range():
    with pytest.raises(ValueError):
        sp.build_wavelength_grid(700, 400)
    with pytest.raises(ValueError):
        sp.build_wavelength_grid(0, 400)
    with pytest.raises(ValueError):
        sp.build_wavelength_grid(400, 700, num_points=2)


def test_emission_spectrum_peaks_at_transition_wavelengths():
    transitions = get_series_transitions("Balmer", n_i_max=6)
    grid = sp.build_wavelength_grid(380, 700, 8000)
    lines = sp.make_spectral_lines(transitions, sigma_nm=0.5)
    spectrum = sp.generate_emission_spectrum(lines, grid)

    assert spectrum.mode == sp.SpectrumMode.EMISSION
    # H-alpha should be the tallest peak (using default illustrative amplitudes).
    h_alpha_nm = compute_emission_transition(3, 2).display_wavelength_nm
    idx_near_alpha = np.argmin(np.abs(grid - h_alpha_nm))
    assert spectrum.intensity[idx_near_alpha] == pytest.approx(spectrum.intensity.max(), rel=0.05)
    # Baseline (far from any line) should be ~0.
    assert spectrum.intensity[0] == pytest.approx(0.0, abs=1e-6)


def test_absorption_spectrum_dips_below_continuum():
    transitions = get_series_transitions("Balmer", n_i_max=4)
    grid = sp.build_wavelength_grid(380, 700, 8000)
    lines = sp.make_spectral_lines(transitions, sigma_nm=0.8, amplitude_scale=0.5)
    spectrum = sp.generate_absorption_spectrum(lines, grid, continuum=1.0)

    assert spectrum.mode == sp.SpectrumMode.ABSORPTION
    assert spectrum.intensity.max() <= 1.0 + 1e-9
    h_alpha_nm = compute_emission_transition(3, 2).display_wavelength_nm
    idx_near_alpha = np.argmin(np.abs(grid - h_alpha_nm))
    assert spectrum.intensity[idx_near_alpha] < 1.0  # a real dip
    # far from any line, should be back near the continuum
    assert spectrum.intensity[0] == pytest.approx(1.0, abs=1e-6)


def test_absorption_spectrum_never_negative():
    transitions = get_series_transitions("Balmer", n_i_max=6)
    grid = sp.build_wavelength_grid(380, 700, 4000)
    # deliberately huge amplitude to try to force negative intensity
    lines = sp.make_spectral_lines(transitions, sigma_nm=2.0, amplitude_scale=50.0)
    spectrum = sp.generate_absorption_spectrum(lines, grid, continuum=1.0)
    assert np.all(spectrum.intensity >= 0.0)


def test_generate_spectrum_convenience_dispatch():
    transitions = get_series_transitions("Balmer", n_i_max=4)
    grid = sp.build_wavelength_grid(380, 700, 2000)
    emission = sp.generate_spectrum(transitions, sp.SpectrumMode.EMISSION, grid)
    absorption = sp.generate_spectrum(transitions, sp.SpectrumMode.ABSORPTION, grid)
    assert emission.mode == sp.SpectrumMode.EMISSION
    assert absorption.mode == sp.SpectrumMode.ABSORPTION


def test_default_amplitude_decreases_with_n_initial():
    tr_alpha = compute_emission_transition(3, 2)
    tr_higher = compute_emission_transition(6, 2)
    assert sp.default_relative_amplitude(tr_alpha) > sp.default_relative_amplitude(tr_higher)


def test_amplitudes_list_length_mismatch_rejected():
    transitions = get_series_transitions("Balmer", n_i_max=6)  # 4 transitions: 3,4,5,6
    with pytest.raises(ValueError):
        sp.make_spectral_lines(transitions, amplitudes=[1.0, 2.0])  # wrong length (2 != 4)


# --- Spectrum data-model validation and methods (checkpoint 1, section 1) ---

def test_spectrum_construction_and_auto_sort():
    wl = np.array([500.0, 400.0, 450.0])
    inten = np.array([2.0, 1.0, 3.0])
    spec = sp.Spectrum(wl, inten, mode=sp.SpectrumMode.ABSORPTION)
    assert list(spec.wavelength_nm) == [400.0, 450.0, 500.0]
    assert list(spec.intensity) == [1.0, 3.0, 2.0]  # values travel with their wavelength
    assert len(spec) == 3


def test_spectrum_rejects_mismatched_lengths():
    with pytest.raises(sp.SpectrumValidationError):
        sp.Spectrum(np.array([400.0, 500.0]), np.array([1.0]), mode=sp.SpectrumMode.EMISSION)


def test_spectrum_rejects_empty():
    with pytest.raises(sp.SpectrumValidationError):
        sp.Spectrum(np.array([]), np.array([]), mode=sp.SpectrumMode.EMISSION)


def test_spectrum_rejects_nonpositive_wavelengths():
    with pytest.raises(sp.SpectrumValidationError):
        sp.Spectrum(np.array([-1.0, 400.0]), np.array([1.0, 2.0]), mode=sp.SpectrumMode.EMISSION)
    with pytest.raises(sp.SpectrumValidationError):
        sp.Spectrum(np.array([0.0, 400.0]), np.array([1.0, 2.0]), mode=sp.SpectrumMode.EMISSION)


def test_spectrum_rejects_nonfinite_values():
    with pytest.raises(sp.SpectrumValidationError):
        sp.Spectrum(np.array([400.0, np.nan]), np.array([1.0, 2.0]), mode=sp.SpectrumMode.EMISSION)
    with pytest.raises(sp.SpectrumValidationError):
        sp.Spectrum(np.array([400.0, 500.0]), np.array([1.0, np.inf]), mode=sp.SpectrumMode.EMISSION)


def test_spectrum_copy_is_independent():
    grid = sp.build_wavelength_grid(400, 700, 100)
    spec = sp.Spectrum(grid, np.ones_like(grid), mode=sp.SpectrumMode.ABSORPTION)
    clone = spec.copy()
    clone.intensity[0] = 99.0
    assert spec.intensity[0] == pytest.approx(1.0)  # original untouched


def test_spectrum_select_range():
    grid = sp.build_wavelength_grid(380, 700, 3200)
    spec = sp.Spectrum(grid, np.ones_like(grid), mode=sp.SpectrumMode.ABSORPTION)
    subset = spec.select_range(600, 700)
    assert subset.wavelength_nm.min() >= 600
    assert subset.wavelength_nm.max() <= 700
    assert len(subset) < len(spec)


def test_spectrum_select_range_invalid():
    grid = sp.build_wavelength_grid(380, 700, 100)
    spec = sp.Spectrum(grid, np.ones_like(grid), mode=sp.SpectrumMode.ABSORPTION)
    with pytest.raises(ValueError):
        spec.select_range(700, 380)  # backwards
    with pytest.raises(ValueError):
        spec.select_range(10000, 20000)  # entirely outside coverage


def test_spectrum_normalize_max():
    grid = np.array([400.0, 500.0, 600.0])
    spec = sp.Spectrum(grid, np.array([2.0, 8.0, 4.0]), mode=sp.SpectrumMode.EMISSION)
    normed = spec.normalize(method="max")
    assert normed.intensity.max() == pytest.approx(1.0)
    assert normed.intensity[0] == pytest.approx(0.25)


def test_spectrum_normalize_area():
    grid = np.linspace(1.0, 11.0, 10001)
    spec = sp.Spectrum(grid, np.ones_like(grid), mode=sp.SpectrumMode.EMISSION)
    normed = spec.normalize(method="area")
    area = np.trapezoid(normed.intensity, normed.wavelength_nm)
    assert area == pytest.approx(1.0, rel=1e-3)


def test_spectrum_normalize_unknown_method_rejected():
    grid = np.array([400.0, 500.0])
    spec = sp.Spectrum(grid, np.array([1.0, 2.0]), mode=sp.SpectrumMode.EMISSION)
    with pytest.raises(ValueError):
        spec.normalize(method="bogus")


def test_spectrum_resample_matches_original_at_shared_points():
    grid = sp.build_wavelength_grid(400, 700, 3000)
    spec = sp.Spectrum(grid, np.sin(grid / 50.0), mode=sp.SpectrumMode.ABSORPTION)
    new_grid = np.linspace(450, 650, 500)
    resampled = spec.resample(new_grid)
    assert len(resampled) == 500
    # Every resampled point should exactly match a direct interpolation
    # of the original at that same wavelength (resample() is just
    # np.interp under the hood -- this checks it's wired correctly).
    expected = np.interp(resampled.wavelength_nm, spec.wavelength_nm, spec.intensity)
    assert np.allclose(resampled.intensity, expected, atol=1e-12)


def test_spectrum_resample_rejects_empty_grid():
    grid = sp.build_wavelength_grid(400, 700, 100)
    spec = sp.Spectrum(grid, np.ones_like(grid), mode=sp.SpectrumMode.EMISSION)
    with pytest.raises(ValueError):
        spec.resample(np.array([]))


def test_spectrum_from_arrays_factory():
    wl = np.array([400.0, 500.0, 600.0])
    inten = np.array([1.0, 2.0, 3.0])
    spec = sp.Spectrum.from_arrays(wl, inten, mode="absorption")
    assert spec.mode == sp.SpectrumMode.ABSORPTION
    assert spec.lines == []


def test_spectrum_wavelength_range_property():
    grid = sp.build_wavelength_grid(400, 700, 500)
    spec = sp.Spectrum(grid, np.ones_like(grid), mode=sp.SpectrumMode.EMISSION)
    lo, hi = spec.wavelength_range_nm
    assert lo == pytest.approx(400)
    assert hi == pytest.approx(700)
