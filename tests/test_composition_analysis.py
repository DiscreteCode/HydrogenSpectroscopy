"""Blind detection / inference tests. The analyzer never sees the truth."""
import csv
import io

import numpy as np
import pytest

from spectroscopy.composition import (
    DEFAULT_ABUNDANCES, generate_composition_spectrum, invert_model_line_depth, model_line_depth,
)
from spectroscopy.composition_analysis import (
    analyze_composition, compare_input_and_inferred, estimate_continuum, write_analysis_csv,
)
from spectroscopy.element_database import ELEMENT_DATABASE
from spectroscopy.spectrum import build_wavelength_grid

GRID = build_wavelength_grid(380, 700, 8000)


def _run(ab, rv=0.0, noise=0.008, sig=0.22, seed=7):
    sp = generate_composition_spectrum(GRID, ab, radial_velocity_kms=rv, noise_level=noise,
                                       line_sigma_nm=sig, random_seed=seed)
    return sp, analyze_composition(GRID, sp.intensity)


def test_model_depth_roundtrip_and_monotonic():
    for sym in DEFAULT_ABUNDANCES:
        prev = -1
        for f in (0.01, 0.1, 1, 3, 6):
            a = f * DEFAULT_ABUNDANCES[sym]
            d = model_line_depth(sym, a)
            assert d > prev and d < 0.78
            prev = d
            assert invert_model_line_depth(sym, d) == pytest.approx(a, rel=1e-6)
    assert model_line_depth('Na', 0) == 0.0


def test_continuum_estimate_ignores_lines():
    sp, an = _run({'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2}, noise=0.0)
    true = sp.continuum
    interior = (GRID > 395) & (GRID < 695)  # edge lines (Fe 382/386 nm) make the window edge ill-determined
    assert np.max(np.abs(an.continuum_estimate / true - 1)[interior]) < 0.02
    assert estimate_continuum(GRID, true).shape == GRID.shape


def test_default_composition_recovered_blindly():
    ab = {'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2}
    sp, an = _run(ab)
    assert an.fit_converged
    assert abs(an.radial_velocity_kms) < 3
    for row in compare_input_and_inferred(an, sp.abundances):
        assert abs(row['difference_percent']) < 2.5, row
        assert row['detected']


@pytest.mark.parametrize('rv', [-250.0, -60.0, 0.0, 120.0, 300.0])
def test_radial_velocity_estimated_without_being_told(rv):
    _, an = _run({'H': 60, 'He': 20, 'Na': 5, 'Ca': 5, 'Fe': 10}, rv=rv, noise=0.01, seed=3)
    assert an.radial_velocity_kms == pytest.approx(rv, abs=5.0)


def test_absent_elements_not_detected_with_noise():
    for seed in (1, 2, 3, 4, 5):
        _, an = _run({'H': 80, 'He': 20, 'Na': 0, 'Ca': 0, 'Fe': 0}, noise=0.02, seed=seed, rv=40)
        for sym in ('Na', 'Ca', 'Fe'):
            assert not an.element(sym).detected, (sym, seed)
            assert an.element(sym).inferred_percent == 0.0
        assert an.element('H').detected and an.element('He').detected


def test_inferred_abundances_normalize_and_track_input_on_mystery_presets():
    presets = [{'H': 55, 'He': 30, 'Na': 0, 'Ca': 5, 'Fe': 10},
               {'H': 45, 'He': 25, 'Na': 15, 'Ca': 10, 'Fe': 5}]
    for k, ab in enumerate(presets):
        sp, an = _run(ab, rv=-80, noise=0.01, seed=41 + k)
        assert sum(e.inferred_percent for e in an.elements) == pytest.approx(100.0)
        for row in compare_input_and_inferred(an, sp.abundances):
            assert abs(row['difference_percent']) < 4.0, row


def test_line_width_estimated():
    _, an = _run({'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2}, sig=0.35, noise=0.005)
    assert an.line_sigma_nm == pytest.approx(0.35, rel=0.1)


def test_detected_wavelengths_match_reference_after_doppler():
    _, an = _run({'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2}, rv=100, noise=0.005)
    isolated = [m for m in an.matches if m.detected and not m.blended and np.isfinite(m.detected_wavelength_nm)]
    assert len(isolated) >= 8
    for m in isolated:
        assert abs(m.detected_wavelength_nm - m.expected_observed_nm) < 0.15
        assert m.expected_observed_nm == pytest.approx(m.reference_nm * (1 + 100 / 299792.458), abs=0.05)


def test_table_rows_reference_database_values_and_sources():
    _, an = _run({'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2})
    ref = {(sym, round(l.wavelength_air_nm, 4)) for sym, e in ELEMENT_DATABASE.items()
           for l in e.reference_lines}
    for m in an.matches:
        if m.symbol == 'H':
            assert m.source == 'Quantum calculated'
        else:
            assert m.source == 'Reference database'
            assert (m.symbol, round(m.reference_nm, 4)) in ref
            assert 'NIST' in m.citation


def test_na_doublet_flagged_blended():
    _, an = _run({'H': 70, 'He': 25, 'Na': 5, 'Ca': 1, 'Fe': 2})
    na = [m for m in an.matches if m.symbol == 'Na']
    assert len(na) == 2 and all(m.blended for m in na)


def test_zero_noise_spectrum_analyzes():
    sp, an = _run({'H': 50, 'He': 50, 'Na': 0, 'Ca': 0, 'Fe': 0}, noise=0.0)
    assert np.isfinite(an.noise_sigma)
    assert abs(an.element('H').inferred_percent - 50) < 2


def test_narrow_window_still_works():
    grid = build_wavelength_grid(480, 680, 4000)
    sp = generate_composition_spectrum(grid, {'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2}, noise_level=0.005)
    an = analyze_composition(grid, sp.intensity)
    assert an.element('H').detected
    assert not an.element('Ca').lines_checked or an.element('Ca').lines_checked <= 1


@pytest.mark.parametrize('bad', ['nan', 'short', 'shape', 'order', 'zeros'])
def test_invalid_inputs_raise_value_error(bad):
    wl, fl = GRID.copy(), np.ones_like(GRID)
    if bad == 'nan':
        fl[5] = np.nan
    elif bad == 'short':
        wl, fl = wl[:10], fl[:10]
    elif bad == 'shape':
        fl = fl[:-1]
    elif bad == 'order':
        wl = wl[::-1].copy()
    elif bad == 'zeros':
        fl = np.zeros_like(fl)
    with pytest.raises(ValueError):
        analyze_composition(wl, fl)


def test_range_without_candidate_lines_raises():
    grid = np.linspace(900, 1000, 500)
    with pytest.raises(ValueError):
        analyze_composition(grid, np.ones(500))


def test_per_element_transmission_reconstructs_noiseless_spectrum():
    sp = generate_composition_spectrum(GRID, noise_level=0.0)
    prod = sp.continuum.copy()
    for t in sp.element_transmission.values():
        prod *= t
    np.testing.assert_allclose(prod, sp.intensity, atol=1e-12)


def _csv(sp, an, hide):
    buf = io.StringIO()
    write_analysis_csv(buf, sp, an, hide_solution=hide)
    return list(csv.reader(io.StringIO(buf.getvalue())))


def test_csv_has_sections_units_and_separate_input_inferred_columns():
    sp, an = _run({'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2})
    rows = _csv(sp, an, hide=False)
    flat = [r[0] for r in rows if r]
    assert '# SECTION: element summary' in flat
    assert '# SECTION: detected lines' in flat
    assert '# SECTION: spectrum' in flat
    head = next(r for r in rows if r and r[0] == 'Element')
    assert 'Simulated input (%)' in head and 'Inferred (%)' in head
    spec_head_i = next(i for i, r in enumerate(rows) if r and r[0] == '# SECTION: spectrum') + 1
    assert rows[spec_head_i][0] == 'Wavelength (nm)'
    data = rows[spec_head_i + 1:]
    assert len(data) == GRID.size
    assert float(data[0][0]) == pytest.approx(380)
    assert len(rows[spec_head_i]) == 5 + 5  # five per-element truth columns
    hydrogen = next(r for r in rows if r and r[0] == 'Hydrogen')
    assert float(hydrogen[1]) == pytest.approx(70.0)


def test_csv_hides_solution_for_mystery():
    sp, an = _run({'H': 45, 'He': 25, 'Na': 15, 'Ca': 10, 'Fe': 5})
    text = '\n'.join(','.join(r) for r in _csv(sp, an, hide=True))
    rows = _csv(sp, an, hide=True)
    assert all(r[1:9] == ['Hidden'] * 8 for r in rows if r and r[0] in {'Hydrogen', 'Helium', 'Sodium', 'Calcium', 'Iron'})
    assert 'simulated truth' not in text
    assert 'radial_velocity_kms=0.0' not in text.split('Estimated by analysis')[0]
