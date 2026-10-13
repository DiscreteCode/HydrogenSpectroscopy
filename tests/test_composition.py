import numpy as np
import pytest
from spectroscopy.composition import generate_composition_spectrum, summarize_composition
from spectroscopy.spectrum import build_wavelength_grid


def test_composition_spectrum_is_finite_and_normalizes_inputs():
    grid = build_wavelength_grid(380, 700, 8000)
    spectrum = generate_composition_spectrum(grid, {'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2}, noise_level=0, random_seed=1)
    assert np.all(np.isfinite(spectrum.intensity))
    assert np.all(spectrum.intensity >= 0)
    assert sum(spectrum.abundances.values()) == pytest.approx(100)
    assert {r['symbol'] for r in summarize_composition(spectrum)} == {'H','He','Na','Ca','Fe'}


def test_composition_spectrum_changes_with_abundance():
    grid = build_wavelength_grid(380, 700, 8000)
    low = generate_composition_spectrum(grid, {'H': 1, 'He': 98, 'Na': 0, 'Ca': 0, 'Fe': 1}, noise_level=0)
    high = generate_composition_spectrum(grid, {'H': 90, 'He': 5, 'Na': 2, 'Ca': 1, 'Fe': 2}, noise_level=0)
    assert not np.allclose(low.intensity, high.intensity)


def test_composition_rejects_invalid_abundance_and_noise():
    grid = build_wavelength_grid(380, 700, 1000)
    with pytest.raises(ValueError):
        generate_composition_spectrum(grid, {'H': 0, 'He': 0, 'Na': 0, 'Ca': 0, 'Fe': 0})
    with pytest.raises(ValueError):
        generate_composition_spectrum(grid, noise_level=-1)


def test_zero_abundance_suppresses_that_elements_lines():
    grid = build_wavelength_grid(380, 700, 8000)
    values = {'H': 70, 'He': 25, 'Na': 0, 'Ca': 1, 'Fe': 2}
    spectrum = generate_composition_spectrum(grid, values, noise_level=0)
    sodium_lines = [r for r in spectrum.results if r.symbol == 'Na']
    assert sodium_lines
    assert all(not r.detected for r in sodium_lines)
    assert all(r.depth < 0.025 for r in sodium_lines)


def test_composition_rejects_invalid_physical_parameters():
    grid = build_wavelength_grid(380, 700, 1000)
    with pytest.raises(ValueError):
        generate_composition_spectrum(grid, temperature_k=0)
    with pytest.raises(ValueError):
        generate_composition_spectrum(grid, radial_velocity_kms=float('nan'))
    with pytest.raises(ValueError):
        generate_composition_spectrum(grid, line_sigma_nm=0)


def test_zero_abundance_elements_remain_undetected_with_noise():
    grid = build_wavelength_grid(380, 700, 8000)
    spectrum = generate_composition_spectrum(
        grid,
        {'H': 80, 'He': 20, 'Na': 0, 'Ca': 0, 'Fe': 0},
        noise_level=0.02,
        random_seed=40,
    )
    rows = {row['symbol']: row for row in summarize_composition(spectrum)}
    for symbol in ('Na', 'Ca', 'Fe'):
        assert rows[symbol]['lines_detected'] == 0
        assert rows[symbol]['status'] == 'NOT DETECTED'


def test_composition_generation_is_reproducible_for_same_seed():
    grid = build_wavelength_grid(380, 700, 2000)
    first = generate_composition_spectrum(grid, noise_level=0.01, random_seed=123)
    second = generate_composition_spectrum(grid, noise_level=0.01, random_seed=123)
    assert np.array_equal(first.intensity, second.intensity)
