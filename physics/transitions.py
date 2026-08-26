"""
physics.transitions
====================

Turns a pair of quantum numbers (n_initial, n_final) into a fully
computed physical transition: energy gap, photon wavelength, frequency,
wavenumber, spectral series, and spectral region. Every downstream
module (spectrum simulator, series viewer, stellar analyzer) builds on
top of the ``Transition`` objects produced here -- nothing downstream
re-derives wavelengths independently.

Sign convention
----------------
- Emission: an electron falls from a higher level to a lower one
  (n_initial > n_final) and a photon is released.
- Absorption: an electron is promoted from a lower level to a higher
  one (n_initial < n_final) by absorbing a photon of matching energy.

Both are physically valid and both are supported here; the *emission
only* restriction mentioned for the interactive Energy Level UI is a
UI-level choice (see app/), not a physics-engine limitation, since
absorption is exactly as real a process and is needed for the
absorption-spectrum mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from physics.air_conversion import vacuum_to_air_nm
from physics.constants import (
    HC_EV_NM,
    classify_spectral_region,
    energy_ev_to_wavelength_nm,
    wavelength_nm_to_frequency_hz,
)
from physics.hydrogen import energy_level_ev
from physics.spectral_series import identify_series


class TransitionKind(str, Enum):
    EMISSION = "emission"
    ABSORPTION = "absorption"


@dataclass(frozen=True)
class Transition:
    """A single computed hydrogen electronic transition.

    ``wavelength_nm`` is the physically fundamental VACUUM wavelength,
    computed directly from ``lambda = hc / delta_E`` with no assumptions
    about a surrounding medium. ``wavelength_air_nm`` is the same
    photon's wavelength as it would disperse through standard air (what
    a lab spectrometer or the naked eye through Earth's atmosphere
    actually sees) -- this is the number that matches the commonly
    quoted "656.3 nm" textbook figure for H-alpha, versus 656.46 nm in
    vacuum. Both are correct; they describe the same photon in two
    different media. See physics/air_conversion.py for the conversion.
    ``wavelength_air_nm`` is None outside that formula's validity range
    (roughly 200-1700 nm), since an "air wavelength" isn't a physically
    meaningful quantity to quote for e.g. deep-UV Lyman lines.
    """

    n_initial: int
    n_final: int
    delta_e_ev: float
    wavelength_nm: float           # vacuum wavelength (fundamental)
    wavelength_air_nm: float | None  # standard-air wavelength, if applicable
    frequency_hz: float
    wavenumber_m_inv: float
    kind: TransitionKind
    series: str | None       # e.g. "Balmer"; None if n_final==0 doesn't apply
    region: str              # e.g. "Visible"

    @property
    def label(self) -> str:
        arrow = "->"
        return f"{self.n_initial} {arrow} {self.n_final}"

    @property
    def display_wavelength_nm(self) -> float:
        """The wavelength value most appropriate to show as the
        headline number in the UI: the standard-air value when it's
        defined (matching conventional textbook/lab figures), falling
        back to vacuum for transitions outside air's validity range
        (e.g. deep Lyman-series UV lines)."""
        return self.wavelength_air_nm if self.wavelength_air_nm is not None else self.wavelength_nm


def _validate_pair(n_initial: int, n_final: int) -> None:
    if n_initial == n_final:
        raise ValueError(
            f"n_initial and n_final must differ (got n={n_initial} for both); "
            "a transition requires a change of quantum state."
        )
    for label, n in (("n_initial", n_initial), ("n_final", n_final)):
        if n < 1:
            raise ValueError(f"{label} must be >= 1, got {n}")


def compute_transition(n_initial: int, n_final: int) -> Transition:
    """Compute the full physical description of the transition
    n_initial -> n_final.

    ΔE = |E_initial - E_final|            (energy conservation)
    λ  = hc / ΔE                          (photon wavelength)
    ν  = c / λ                            (photon frequency)
    """
    _validate_pair(n_initial, n_final)

    e_initial = energy_level_ev(n_initial)
    e_final = energy_level_ev(n_final)
    delta_e_ev = abs(e_initial - e_final)

    wavelength_nm = energy_ev_to_wavelength_nm(delta_e_ev)
    wavelength_air_nm = vacuum_to_air_nm(wavelength_nm)
    # Frequency is a medium-independent property of the photon -- it
    # must always be derived from the VACUUM wavelength, never the air
    # one, or the value would be subtly wrong.
    frequency_hz = wavelength_nm_to_frequency_hz(wavelength_nm)
    wavenumber_m_inv = 1.0 / (wavelength_nm * 1e-9)

    kind = TransitionKind.EMISSION if n_initial > n_final else TransitionKind.ABSORPTION
    series = identify_series(min(n_initial, n_final))
    region = classify_spectral_region(wavelength_nm)

    return Transition(
        n_initial=n_initial,
        n_final=n_final,
        delta_e_ev=delta_e_ev,
        wavelength_nm=wavelength_nm,
        wavelength_air_nm=wavelength_air_nm,
        frequency_hz=frequency_hz,
        wavenumber_m_inv=wavenumber_m_inv,
        kind=kind,
        series=series,
        region=region,
    )


def compute_emission_transition(n_initial: int, n_final: int) -> Transition:
    """Same as compute_transition, but explicitly asserts this is a
    physically valid emission (n_initial must be > n_final). Raises a
    clear, user-facing-friendly error otherwise -- this is what the
    Energy Level / Transition Explorer UI should call, since it only
    permits emission transitions."""
    if n_initial <= n_final:
        raise ValueError(
            f"Not a valid emission transition: n_initial ({n_initial}) must be "
            f"greater than n_final ({n_final}). An electron emits a photon "
            "only when falling to a *lower* energy state."
        )
    return compute_transition(n_initial, n_final)


# Sanity-check constant exposed for tests / UI footers: hc in eV*nm.
HC_EV_NM_REFERENCE = HC_EV_NM
