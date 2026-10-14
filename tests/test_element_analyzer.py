import numpy as np

from spectroscopy.element_analyzer import match_element_lines
from spectroscopy.element_database import get_element
from spectroscopy.peak_detection import find_absorption_features


def _spectrum_with_lines(symbol, grid):
    entry = get_element(symbol)
    intensity = np.ones_like(grid)
    for line in entry.reference_lines:
        intensity *= 1.0 - 0.28 * np.exp(-0.5 * ((grid - line.wavelength_air_nm) / 0.16) ** 2)
    return intensity


def test_calcium_reference_lines_are_identified_as_a_pattern():
    grid = np.linspace(380.0, 410.0, 6001)
    intensity = _spectrum_with_lines("Ca", grid)
    summary = match_element_lines(grid, intensity, "Ca", continuum_level=1.0)
    assert summary.detected
    assert summary.num_matched == 2
    assert all("[reference]" in row.label for row in summary.results)


def test_reference_element_with_no_absorption_is_not_identified():
    grid = np.linspace(380.0, 410.0, 3001)
    summary = match_element_lines(grid, np.ones_like(grid), "Ca", continuum_level=1.0)
    assert not summary.detected
    assert summary.num_matched == 0


def test_hydrogen_still_uses_quantum_calculated_balmer_lines():
    grid = np.linspace(380.0, 700.0, 16001)
    intensity = _spectrum_with_lines("Ca", grid)
    summary = match_element_lines(grid, intensity, "H", continuum_level=1.0)
    assert summary.num_expected >= 3
    assert all("Balmer" in row.label for row in summary.results)
    assert all("[reference]" not in row.label for row in summary.results)
