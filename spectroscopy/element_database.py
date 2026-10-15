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

Every reference line carries the citation of the table it was taken
from. Do not add reference lines without a citation; do not ever
silently blend a reference-database line with a computed hydrogen line
in the UI without labeling which is which.

Wavelengths are standard-AIR wavelengths in nm (the convention used by
the NIST Handbook of Basic Atomic Spectroscopic Data tables below),
matching the air wavelengths used for the computed hydrogen lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LineSource(str, Enum):
    QUANTUM_CALCULATED = "quantum_calculated"   # derived live from physics engine
    REFERENCE_DATABASE = "reference_database"    # looked up, not computed here


NIST_HANDBOOK = (
    "NIST Handbook of Basic Atomic Spectroscopic Data, "
    "https://physics.nist.gov/PhysRefData/Handbook/ (wavelength tables, "
    "air wavelengths, converted from Angstrom where tabulated in A)"
)


@dataclass(frozen=True)
class ReferenceLine:
    """One reference-database line (standard-air wavelength, nm)."""

    wavelength_air_nm: float
    label: str
    citation: str = NIST_HANDBOOK
    # Relative intensity as tabulated by the source (arbitrary units,
    # comparable only within one element/ion table). None if not used.
    tabulated_intensity: float | None = None


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

# Reference (looked-up, NOT computed) lines. Values: NIST Handbook of
# Basic Atomic Spectroscopic Data, wavelength tables (He I: 4 decimals
# where tabulated; Na I, Ca II/I: 3-4 decimals; Fe I: 0.01 nm precision
# as tabulated in the strong-lines table).
HELIUM = ElementEntry(
    symbol="He",
    name="Helium",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(447.1479, "He I 447.1", tabulated_intensity=200),
        ReferenceLine(492.1931, "He I 492.2", tabulated_intensity=20),
        ReferenceLine(501.5678, "He I 501.6", tabulated_intensity=100),
        ReferenceLine(587.562, "He I D3", tabulated_intensity=500),
        ReferenceLine(667.8152, "He I 667.8", tabulated_intensity=200),
        ReferenceLine(706.5177, "He I 706.5", tabulated_intensity=100),
    ),
    note="Reference lines only; not quantum-calculated in this app. "
    "He I D3 is the 587.56 nm fine-structure blend (components at "
    "587.5615/587.5640/587.5966 nm).",
)

SODIUM = ElementEntry(
    symbol="Na",
    name="Sodium",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(588.995, "Na I D2", tabulated_intensity=1000),
        ReferenceLine(589.592, "Na I D1", tabulated_intensity=500),
    ),
    note="Reference lines only; not quantum-calculated in this app.",
)

CALCIUM = ElementEntry(
    symbol="Ca",
    name="Calcium",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(393.3661, "Ca II K", tabulated_intensity=1000),
        ReferenceLine(396.8467, "Ca II H", tabulated_intensity=1000),
        ReferenceLine(422.6727, "Ca I 422.7", tabulated_intensity=1000),
    ),
    note="Reference lines only; not quantum-calculated in this app. "
    "The Ca II H&K lines are prominent in stellar spectra.",
)

IRON = ElementEntry(
    symbol="Fe",
    name="Iron",
    source=LineSource.REFERENCE_DATABASE,
    reference_lines=(
        ReferenceLine(382.04, "Fe I 382.0", tabulated_intensity=500),
        ReferenceLine(385.99, "Fe I 386.0", tabulated_intensity=500),
        ReferenceLine(388.63, "Fe I 388.6", tabulated_intensity=300),
        ReferenceLine(404.58, "Fe I 404.6", tabulated_intensity=300),
        ReferenceLine(438.35, "Fe I 438.4", tabulated_intensity=200),
        ReferenceLine(516.75, "Fe I 516.8", tabulated_intensity=250),
    ),
    note="Reference lines only (illustrative subset of the strongest "
    "tabulated Fe I lines); not quantum-calculated in this app. Iron's "
    "real spectrum has thousands of lines.",
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
