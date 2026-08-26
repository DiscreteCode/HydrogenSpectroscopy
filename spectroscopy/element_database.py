"""
spectroscopy.element_database
==============================

Architecture hook for future multi-element identification (project
brief section 13). Hydrogen is the only element this application
*computes* quantum mechanically (via physics.hydrogen / physics.transitions).
Everything else listed here is reference data -- well known, standard
laboratory air wavelengths -- included only so the data model and
matching pipeline are demonstrably extensible, and explicitly NOT
derived from a quantum calculation in this app.

Do not add more "reference" elements without also adding a clear
citation; do not ever silently blend a reference-database line with a
computed hydrogen line in the UI without labeling which is which.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LineSource(str, Enum):
    QUANTUM_CALCULATED = "quantum_calculated"   # derived live from physics engine
    REFERENCE_DATABASE = "reference_database"    # looked up, not computed here


@dataclass(frozen=True)
class ReferenceLine:
    wavelength_air_nm: float
    label: str


@dataclass(frozen=True)
class ElementEntry:
    symbol: str
    name: str
    source: LineSource
    reference_lines: tuple[ReferenceLine, ...] = ()
    note: str = ""


# Hydrogen: the only element with a live quantum-mechanical engine in
# this app (see physics/hydrogen.py, physics/transitions.py). No
# hardcoded line list here -- transitions are always computed on demand.
HYDROGEN = ElementEntry(
    symbol="H",
    name="Hydrogen",
    source=LineSource.QUANTUM_CALCULATED,
    reference_lines=(),
    note="Every hydrogen line in this application is computed live from "
    "E_n = -13.6 eV/n^2, never looked up.",
)

# The following are standard, extremely well-established laboratory air
# wavelengths (the kind found in any spectroscopy reference table),
# included ONLY to demonstrate that the element database / line-matching
# architecture generalizes beyond hydrogen. They are NOT computed by
# this application's physics engine and should never be presented to a
# user as "calculated".
HELIUM = ElementEntry(
    symbol="He",
    name="Helium",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(587.6, "He I D3"),
        ReferenceLine(667.8, "He I"),
        ReferenceLine(447.1, "He I"),
    ),
    note="Reference lines only; not quantum-calculated in this app.",
)

SODIUM = ElementEntry(
    symbol="Na",
    name="Sodium",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(589.0, "Na D2"),
        ReferenceLine(589.6, "Na D1"),
    ),
    note="Reference lines only; not quantum-calculated in this app.",
)

CALCIUM = ElementEntry(
    symbol="Ca",
    name="Calcium",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(393.4, "Ca II K"),
        ReferenceLine(396.8, "Ca II H"),
    ),
    note="Reference lines only; not quantum-calculated in this app. "
    "The Ca II H&K lines are prominent in stellar spectra.",
)

IRON = ElementEntry(
    symbol="Fe",
    name="Iron",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(438.4, "Fe I"),
        ReferenceLine(526.9, "Fe I"),
        ReferenceLine(495.8, "Fe I"),
    ),
    note="Reference lines only (illustrative subset); not quantum-calculated "
    "in this app. Iron's real spectrum has thousands of lines.",
)

ELEMENT_DATABASE: dict[str, ElementEntry] = {
    e.symbol: e for e in (HYDROGEN, HELIUM, SODIUM, CALCIUM, IRON)
}


def list_elements() -> list[str]:
    return list(ELEMENT_DATABASE.keys())


def get_element(symbol: str) -> ElementEntry:
    try:
        return ELEMENT_DATABASE[symbol]
    except KeyError as exc:
        raise ValueError(
            f"Unknown element symbol '{symbol}'. Known: {list_elements()}"
        ) from exc
