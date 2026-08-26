import pytest

from physics import spectral_series as ss


def test_series_names():
    names = ss.list_series_names()
    assert names == ["Lyman", "Balmer", "Paschen", "Brackett", "Pfund"]


@pytest.mark.parametrize(
    "n_final,expected_name",
    [(1, "Lyman"), (2, "Balmer"), (3, "Paschen"), (4, "Brackett"), (5, "Pfund")],
)
def test_identify_series(n_final, expected_name):
    assert ss.identify_series(n_final) == expected_name


def test_identify_series_unknown_returns_none():
    assert ss.identify_series(6) is None
    assert ss.identify_series(50) is None


def test_get_series_final_n():
    assert ss.get_series_final_n("Balmer") == 2
    assert ss.get_series_final_n("Lyman") == 1


def test_get_series_final_n_unknown_raises():
    with pytest.raises(ValueError):
        ss.get_series_final_n("NotASeries")


def test_get_balmer_series_transitions_matches_known_values():
    transitions = ss.get_series_transitions("Balmer", n_i_max=6)
    assert [tr.n_initial for tr in transitions] == [3, 4, 5, 6]
    assert all(tr.n_final == 2 for tr in transitions)

    # Compare against the conventional air wavelengths (what these
    # values are commonly quoted as); wavelength_nm itself is vacuum.
    expected_air_nm = {3: 656.3, 4: 486.1, 5: 434.0, 6: 410.2}
    for tr in transitions:
        assert tr.wavelength_air_nm == pytest.approx(expected_air_nm[tr.n_initial], abs=0.1)


def test_get_lyman_series_transitions():
    transitions = ss.get_series_transitions("Lyman", n_i_max=4)
    assert [tr.n_initial for tr in transitions] == [2, 3, 4]
    assert all(tr.n_final == 1 for tr in transitions)
    assert all(tr.region in ("Ultraviolet", "Vacuum Ultraviolet") for tr in transitions)


def test_get_series_transitions_invalid_range():
    with pytest.raises(ValueError):
        ss.get_series_transitions("Balmer", n_i_max=2)  # must be > n_final(2)


def test_get_series_transitions_unknown_series():
    with pytest.raises(ValueError):
        ss.get_series_transitions("Humphreys-not-implemented", n_i_max=10)
