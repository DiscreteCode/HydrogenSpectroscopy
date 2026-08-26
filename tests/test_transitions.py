import pytest

from physics import transitions as t
from physics.transitions import TransitionKind


# Reference VACUUM wavelengths, nm. The Rydberg formula with CODATA
# fundamental constants computes vacuum wavelengths directly (there is
# no atmosphere in lambda = hc/deltaE). Cross-checked against the
# literature vacuum value for H-alpha (656.46 nm; e.g. Wikipedia
# "Hydrogen-alpha", citing 656.28 nm air / 656.46 nm vacuum) and
# internally against the official NIST hydrogen Rydberg constant
# R_H = 10,967,758.3406 m^-1, which reproduces these same figures to
# 8 significant figures -- see the derivation note in
# physics/constants.py.
VACUUM_BALMER_NM = {
    (3, 2): 656.4696,   # H-alpha (vacuum)
    (4, 2): 486.2738,   # H-beta  (vacuum)
    (5, 2): 434.1730,   # H-gamma (vacuum)
    (6, 2): 410.2935,   # H-delta (vacuum)
}

# The project brief's own reference values are the conventional STANDARD
# AIR wavelengths (matching e.g. the widely tabulated air figures
# 656.28/486.13/434.05/410.17 nm, rounded to 1 decimal place). These are
# what a lab spectrometer measures through air, and what almost every
# introductory textbook quotes without mentioning the air/vacuum
# distinction at all.
AIR_BALMER_NM = {
    (3, 2): 656.3,
    (4, 2): 486.1,
    (5, 2): 434.0,
    (6, 2): 410.2,
}


@pytest.mark.parametrize("pair,expected_nm", list(VACUUM_BALMER_NM.items()))
def test_balmer_vacuum_wavelengths(pair, expected_nm):
    n_i, n_f = pair
    transition = t.compute_transition(n_i, n_f)
    assert transition.wavelength_nm == pytest.approx(expected_nm, abs=0.02)


@pytest.mark.parametrize("pair,expected_nm", list(AIR_BALMER_NM.items()))
def test_balmer_air_wavelengths_match_project_brief(pair, expected_nm):
    n_i, n_f = pair
    transition = t.compute_transition(n_i, n_f)
    assert transition.wavelength_air_nm is not None
    assert transition.wavelength_air_nm == pytest.approx(expected_nm, abs=0.1)
    # Air wavelength must always be shorter than vacuum wavelength
    # (n_air > 1 slows and compresses the wave).
    assert transition.wavelength_air_nm < transition.wavelength_nm


def test_h_alpha_full_physical_summary():
    """The flagship 3->2 transition described throughout the brief."""
    tr = t.compute_emission_transition(3, 2)
    assert tr.delta_e_ev == pytest.approx(1.889, abs=2e-3)
    assert tr.wavelength_nm == pytest.approx(656.47, abs=0.01)       # vacuum
    assert tr.wavelength_air_nm == pytest.approx(656.3, abs=0.05)    # air / textbook value
    assert tr.display_wavelength_nm == tr.wavelength_air_nm
    assert tr.frequency_hz == pytest.approx(4.57e14, rel=2e-3)
    assert tr.series == "Balmer"
    assert tr.region == "Visible"
    assert tr.kind == TransitionKind.EMISSION
    assert tr.label == "3 -> 2"


def test_lyman_alpha_is_ultraviolet():
    tr = t.compute_emission_transition(2, 1)
    assert tr.wavelength_nm == pytest.approx(121.567, abs=0.05)
    assert tr.series == "Lyman"
    assert tr.region in ("Ultraviolet", "Vacuum Ultraviolet")


def test_paschen_alpha_is_infrared():
    tr = t.compute_emission_transition(4, 3)
    assert tr.series == "Paschen"
    assert tr.region in ("Near Infrared", "Infrared")


def test_emission_requires_n_initial_greater_than_n_final():
    with pytest.raises(ValueError):
        t.compute_emission_transition(2, 3)  # backwards
    with pytest.raises(ValueError):
        t.compute_emission_transition(2, 2)  # equal


def test_absorption_transition_is_mirror_of_emission():
    emission = t.compute_transition(3, 2)
    absorption = t.compute_transition(2, 3)
    assert emission.wavelength_nm == pytest.approx(absorption.wavelength_nm, rel=1e-12)
    assert emission.delta_e_ev == pytest.approx(absorption.delta_e_ev, rel=1e-12)
    assert emission.kind == TransitionKind.EMISSION
    assert absorption.kind == TransitionKind.ABSORPTION


def test_same_n_rejected():
    with pytest.raises(ValueError):
        t.compute_transition(2, 2)


def test_invalid_n_rejected():
    with pytest.raises(ValueError):
        t.compute_transition(0, 1)
    with pytest.raises(ValueError):
        t.compute_transition(1, -1)


def test_energy_scales_correctly_with_n():
    # Higher-n initial states falling to the same final state release
    # LESS energy per step as n_initial grows (levels crowd near 0 eV)
    e1 = t.compute_emission_transition(3, 2).delta_e_ev
    e2 = t.compute_emission_transition(10, 2).delta_e_ev
    e3 = t.compute_emission_transition(100, 2).delta_e_ev
    assert e1 < e2 < e3 < 3.4  # bounded by the series limit (E_2 to E_inf = 3.4eV)


def test_series_limit_convergence():
    # As n_initial -> infinity, the transition energy approaches the
    # ionization energy of the final state (the series limit).
    from physics.hydrogen import ionization_energy_ev

    tr = t.compute_emission_transition(200, 2)
    assert tr.delta_e_ev == pytest.approx(ionization_energy_ev(2), abs=0.01)
