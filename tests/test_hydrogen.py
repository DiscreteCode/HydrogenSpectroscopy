import pytest

from physics import hydrogen as h


def test_ground_state_energy_is_minus_13_6_ev():
    e1 = h.energy_level_ev(1)
    assert e1 == pytest.approx(-13.6, abs=5e-3)
    assert e1 < 0


def test_energy_increases_toward_zero_with_n():
    # Energies should be monotonically increasing (less negative) as
    # n increases: E_1 < E_2 < E_3 < ... < 0
    energies = [h.energy_level_ev(n) for n in range(1, 11)]
    assert energies == sorted(energies)
    assert all(e < 0 for e in energies)


@pytest.mark.parametrize(
    "n,expected_ev",
    [
        (1, -13.6),
        (2, -3.4),
        (3, -1.511),
        (4, -0.850),
        (5, -0.544),
        (6, -0.378),
    ],
)
def test_known_energy_levels(n, expected_ev):
    assert h.energy_level_ev(n) == pytest.approx(expected_ev, abs=5e-3)


def test_energy_level_object():
    level = h.energy_level(2)
    assert level.n == 2
    assert level.energy_ev == pytest.approx(-3.4, abs=5e-3)
    assert level.is_ground_state is False
    assert h.energy_level(1).is_ground_state is True


def test_energy_levels_list_ordering_and_range():
    levels = h.energy_levels(n_max=5)
    assert [lvl.n for lvl in levels] == [1, 2, 3, 4, 5]
    assert levels[0].energy_ev < levels[-1].energy_ev

    levels_offset = h.energy_levels(n_min=3, n_max=5)
    assert [lvl.n for lvl in levels_offset] == [3, 4, 5]


def test_ionization_energy():
    assert h.ionization_energy_ev(1) == pytest.approx(13.6, abs=5e-3)
    # Ionizing from n=2 requires far less energy than from the ground state
    assert h.ionization_energy_ev(2) == pytest.approx(3.4, abs=5e-3)
    assert h.ionization_energy_ev(2) < h.ionization_energy_ev(1)


def test_invalid_n_rejected():
    with pytest.raises(ValueError):
        h.energy_level_ev(0)
    with pytest.raises(ValueError):
        h.energy_level_ev(-3)
    with pytest.raises(TypeError):
        h.energy_level_ev(3.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        h.energy_level_ev("3")  # type: ignore[arg-type]


def test_n_exceeding_supported_maximum_rejected():
    with pytest.raises(ValueError):
        h.energy_level_ev(h.MAX_SUPPORTED_N + 1)


def test_energy_levels_range_validation():
    with pytest.raises(ValueError):
        h.energy_levels(n_max=3, n_min=5)  # n_max < n_min
    with pytest.raises(ValueError):
        h.energy_levels(n_max=5, n_min=0)
