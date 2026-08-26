import math

import pytest

from physics import constants as c


def test_rydberg_energy_matches_textbook_13_6_ev():
    # The reduced-mass corrected value should be extremely close to the
    # commonly quoted 13.6 eV (NIST: 13.598434 eV).
    assert c.RYDBERG_ENERGY_EV == pytest.approx(13.598, abs=1e-3)
    assert c.RYDBERG_ENERGY_EV == pytest.approx(13.6, abs=5e-3)


def test_hc_ev_nm_matches_known_constant():
    # hc is a very commonly tabulated spectroscopy constant: 1239.84 eV*nm
    assert c.HC_EV_NM == pytest.approx(1239.84, abs=0.05)


def test_rydberg_hydrogen_smaller_than_infinite_mass():
    # Finite nuclear mass correction must reduce (not increase) R_H
    # relative to R_infinity, and by a tiny fraction (~0.05%).
    assert c.RYDBERG_HYDROGEN < c.RYDBERG_INFINITY
    ratio = c.RYDBERG_HYDROGEN / c.RYDBERG_INFINITY
    assert ratio == pytest.approx(1.0, abs=0.001)


@pytest.mark.parametrize(
    "wavelength_nm,expected_ev",
    [
        (656.279, 1.8891),  # H-alpha
        (500.0, 2.4797),
        (1239.84, 1.0),
    ],
)
def test_wavelength_energy_round_trip(wavelength_nm, expected_ev):
    energy = c.wavelength_nm_to_energy_ev(wavelength_nm)
    assert energy == pytest.approx(expected_ev, rel=1e-3)
    # round trip back to wavelength
    back = c.energy_ev_to_wavelength_nm(energy)
    assert back == pytest.approx(wavelength_nm, rel=1e-9)


def test_frequency_wavelength_round_trip():
    wl = 656.279
    freq = c.wavelength_nm_to_frequency_hz(wl)
    assert freq == pytest.approx(4.568e14, rel=1e-3)
    back = c.frequency_hz_to_wavelength_nm(freq)
    assert back == pytest.approx(wl, rel=1e-9)


def test_ev_joule_round_trip():
    ev = 13.6
    j = c.ev_to_joule(ev)
    assert j == pytest.approx(2.179e-18, rel=1e-3)
    assert c.joule_to_ev(j) == pytest.approx(ev, rel=1e-9)


@pytest.mark.parametrize(
    "wavelength_nm,expected_region",
    [
        (121.6, "Vacuum Ultraviolet"),   # Lyman-alpha
        (300.0, "Ultraviolet"),
        (500.0, "Visible"),
        (656.3, "Visible"),               # H-alpha
        (1000.0, "Near Infrared"),
        (5000.0, "Infrared"),
    ],
)
def test_classify_spectral_region(wavelength_nm, expected_region):
    assert c.classify_spectral_region(wavelength_nm) == expected_region


def test_classify_spectral_region_rejects_nonpositive():
    with pytest.raises(ValueError):
        c.classify_spectral_region(0)
    with pytest.raises(ValueError):
        c.classify_spectral_region(-5)


def test_kms_ms_round_trip():
    assert c.ms_to_kms(c.kms_to_ms(42.0)) == pytest.approx(42.0)


def test_negative_or_zero_wavelength_rejected_everywhere():
    with pytest.raises(ValueError):
        c.wavelength_nm_to_energy_ev(0)
    with pytest.raises(ValueError):
        c.wavelength_nm_to_energy_ev(-1)
    with pytest.raises(ValueError):
        c.wavelength_nm_to_frequency_hz(0)
    with pytest.raises(ValueError):
        c.frequency_hz_to_wavelength_nm(0)
    with pytest.raises(ValueError):
        c.energy_ev_to_wavelength_nm(0)
    with pytest.raises(ValueError):
        c.energy_ev_to_frequency_hz(0)
    with pytest.raises(ValueError):
        c.frequency_hz_to_energy_ev(0)
