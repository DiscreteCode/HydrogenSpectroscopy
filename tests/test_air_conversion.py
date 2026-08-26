import pytest

from physics import air_conversion as ac


def test_h_alpha_vacuum_to_air_matches_known_value():
    # Known literature values: 656.46 nm vacuum -> 656.28 nm air
    air = ac.vacuum_to_air_nm(656.4696)
    assert air == pytest.approx(656.28, abs=0.01)


def test_air_always_shorter_than_vacuum_in_optical_range():
    for vac in (300.0, 500.0, 656.47, 1000.0, 1600.0):
        air = ac.vacuum_to_air_nm(vac)
        assert air is not None
        assert air < vac


def test_round_trip_air_vacuum_conversion():
    for vac in (250.0, 434.17, 656.47, 900.0, 1500.0):
        air = ac.vacuum_to_air_nm(vac)
        recovered_vac = ac.air_to_vacuum_nm(air)
        assert recovered_vac == pytest.approx(vac, abs=1e-4)


def test_outside_validity_range_returns_none():
    # Deep UV (e.g. Lyman-alpha at 121.6 nm) is well outside the
    # formula's validity range.
    assert ac.vacuum_to_air_nm(121.6) is None
    assert ac.vacuum_to_air_nm(50.0) is None
    # Far IR (e.g. long Pfund-series lines) likewise.
    assert ac.vacuum_to_air_nm(5000.0) is None


def test_refractive_index_close_to_one():
    n = ac.refractive_index_standard_air(656.47)
    assert n is not None
    assert 1.0002 < n < 1.0004


def test_nonpositive_wavelength_rejected():
    with pytest.raises(ValueError):
        ac.vacuum_to_air_nm(0)
    with pytest.raises(ValueError):
        ac.vacuum_to_air_nm(-100)
    with pytest.raises(ValueError):
        ac.air_to_vacuum_nm(0)
    with pytest.raises(ValueError):
        ac.refractive_index_standard_air(-1)
