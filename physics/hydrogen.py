"""
physics.hydrogen
=================

The quantum-mechanical energy levels of the hydrogen atom (Bohr model /
non-relativistic Schrodinger result -- both give the same energy
spectrum for hydrogen). This module has no knowledge of transitions,
spectra, or the GUI; it only answers "what is the energy of state n".

    E_n = -13.6 eV / n^2   (n = 1, 2, 3, ...)

The constant is not hard-coded as 13.6; it is derived in
``physics.constants`` from CODATA fundamental constants with the
electron-proton reduced-mass correction applied, which is the physically
correct value for a *real* (finite nuclear mass) hydrogen atom.
"""

from __future__ import annotations

from dataclasses import dataclass

from physics.constants import RYDBERG_ENERGY_EV

MAX_SUPPORTED_N = 200  # sane upper bound; beyond this, floating point
                        # energy differences between adjacent levels
                        # become numerically meaningless for this app.


@dataclass(frozen=True)
class HydrogenEnergyLevel:
    """A single quantized energy state of the hydrogen atom."""

    n: int
    energy_ev: float

    @property
    def is_ground_state(self) -> bool:
        return self.n == 1

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"n={self.n}: {self.energy_ev:.4f} eV"


def _validate_n(n: int) -> None:
    if not isinstance(n, (int,)) or isinstance(n, bool):
        raise TypeError(f"Quantum number n must be an int, got {type(n).__name__}")
    if n < 1:
        raise ValueError(f"Quantum number n must be >= 1, got {n}")
    if n > MAX_SUPPORTED_N:
        raise ValueError(
            f"Quantum number n={n} exceeds supported maximum of {MAX_SUPPORTED_N}"
        )


def energy_level_ev(n: int) -> float:
    """Return the energy (in eV) of hydrogen quantum state n.

    E_n = -RYDBERG_ENERGY_EV / n^2

    The energy is negative because it is measured relative to the
    ionization limit (E = 0, a free electron at rest infinitely far
    from the proton). More negative = more tightly bound.
    """
    _validate_n(n)
    return -RYDBERG_ENERGY_EV / (n ** 2)


def energy_level(n: int) -> HydrogenEnergyLevel:
    """Return the full HydrogenEnergyLevel object for quantum state n."""
    return HydrogenEnergyLevel(n=n, energy_ev=energy_level_ev(n))


def energy_levels(n_max: int, n_min: int = 1) -> list[HydrogenEnergyLevel]:
    """Return all hydrogen energy levels from n_min to n_max inclusive,
    ordered by increasing n (i.e. increasing, less-negative energy)."""
    if n_min < 1:
        raise ValueError(f"n_min must be >= 1, got {n_min}")
    if n_max < n_min:
        raise ValueError(f"n_max ({n_max}) must be >= n_min ({n_min})")
    return [energy_level(n) for n in range(n_min, n_max + 1)]


def ionization_energy_ev(n: int = 1) -> float:
    """Energy required to ionize the atom starting from state n
    (i.e. the energy gap between state n and the n->infinity limit at
    E=0). For n=1 this is the textbook 13.6 eV ionization energy."""
    _validate_n(n)
    return -energy_level_ev(n)
