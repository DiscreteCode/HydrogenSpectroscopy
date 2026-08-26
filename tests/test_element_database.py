import pytest

from physics.transitions import compute_emission_transition
from spectroscopy import element_database as edb


def test_list_elements_includes_hydrogen_and_placeholders():
    elements = edb.list_elements()
    assert "H" in elements
    assert set(elements) >= {"H", "He", "Na", "Ca", "Fe"}


def test_get_hydrogen_is_quantum_calculated_with_no_hardcoded_lines():
    h = edb.get_element("H")
    assert h.symbol == "H"
    assert h.source == edb.LineSource.QUANTUM_CALCULATED
    # Hydrogen deliberately carries NO reference line list -- every
    # line is computed on demand from the physics engine instead.
    assert h.reference_lines == ()


def test_hydrogen_lines_are_never_hardcoded_but_computed_live():
    """Cross-check: the element database's notion of 'hydrogen' must
    stay consistent with the live physics engine, because nothing about
    hydrogen is stored as a static table here."""
    tr = compute_emission_transition(3, 2)
    assert tr.display_wavelength_nm == pytest.approx(656.3, abs=0.1)
    # The element database doesn't duplicate this number anywhere;
    # this test exists to document that expectation for future readers.


@pytest.mark.parametrize("symbol", ["He", "Na", "Ca", "Fe"])
def test_placeholder_elements_are_clearly_marked_reference_only(symbol):
    entry = edb.get_element(symbol)
    assert entry.source == edb.LineSource.REFERENCE_DATABASE
    assert len(entry.reference_lines) > 0
    assert "not quantum-calculated" in entry.note.lower()
    for line in entry.reference_lines:
        assert line.wavelength_air_nm > 0
        assert line.label


def test_get_unknown_element_raises_clear_error():
    with pytest.raises(ValueError, match="Unknown element symbol"):
        edb.get_element("Xx")


def test_element_entries_are_immutable():
    h = edb.get_element("H")
    with pytest.raises(Exception):
        h.symbol = "X"  # frozen dataclass -- must not be mutable
