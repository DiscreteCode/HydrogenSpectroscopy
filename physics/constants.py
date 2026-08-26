"""
physics.constants
==================

Single source of truth for every physical constant and unit conversion
used in the application. Every other physics module imports from here —
no magic numbers are allowed to live anywhere else in the codebase.

Values are derived from ``scipy.constants`` (2018 CODATA recommended
values, the same dataset used by NIST) rather than hard-coded, so the
provenance of every number is traceable.

References
----------
- CODATA 2018 recommended values (via scipy.constants)
- NIST Atomic Spectra Database: https://physics.nist.gov/PhysRefData/ASD/
"""

from __future__ import annotations

from dataclasses import dataclass

from scipy import constants as _sp

# ---------------------------------------------------------------------------
# Fundamental constants (SI units)
# ---------------------------------------------------------------------------

PLANCK_H: float = _sp.h                     # Planck constant [J*s]  (exact, SI 2019)
SPEED_OF_LIGHT: float = _sp.c               # Speed of light in vacuum [m/s] (exact)
ELEMENTARY_CHARGE: float = _sp.e            # Elementary charge [C]  (exact, SI 2019)
ELECTRON_MASS: float = _sp.m_e              # Electron rest mass [kg]
PROTON_MASS: float = _sp.m_p                # Proton rest mass [kg]
BOLTZMANN_CONSTANT: float = _sp.k           # Boltzmann constant [J/K] (exact, SI 2019)

# Planck constant expressed in eV*s -- convenient for spectroscopy work.
PLANCK_H_EV: float = PLANCK_H / ELEMENTARY_CHARGE

# ---------------------------------------------------------------------------
# Rydberg constants
# ---------------------------------------------------------------------------

# Rydberg constant for infinite nuclear mass (the textbook R_infinity).
RYDBERG_INFINITY: float = _sp.Rydberg  # [1/m]

# Reduced-mass correction: a real hydrogen atom has a proton of finite
# mass, not an infinitely heavy nucleus, so the electron orbits the
# common center of mass. This shifts every hydrogen energy level by the
# factor mu/m_e = M_p/(M_p+m_e). Using the corrected constant is what
# makes our computed Balmer wavelengths match the NIST reference values
# to 3-4 significant figures instead of being systematically off by
# ~0.05%.
_REDUCED_MASS_FACTOR: float = PROTON_MASS / (PROTON_MASS + ELECTRON_MASS)

# Rydberg constant specific to hydrogen (finite nuclear mass), in [1/m].
RYDBERG_HYDROGEN: float = RYDBERG_INFINITY * _REDUCED_MASS_FACTOR

# The hydrogen ground-state ionization energy, i.e. the "13.6 eV" from
# introductory textbooks, computed directly from R_H rather than
# hard-coded. E = h*c*R_H
RYDBERG_ENERGY_J: float = PLANCK_H * SPEED_OF_LIGHT * RYDBERG_HYDROGEN
RYDBERG_ENERGY_EV: float = RYDBERG_ENERGY_J / ELEMENTARY_CHARGE

# ---------------------------------------------------------------------------
# Convenience combined constants
# ---------------------------------------------------------------------------

# h*c expressed directly in eV*nm. This single constant is what lets us
# write the very clean, very common spectroscopist's formula:
#     wavelength_nm = HC_EV_NM / delta_E_eV
HC_EV_NM: float = (PLANCK_H * SPEED_OF_LIGHT / ELEMENTARY_CHARGE) * 1e9

# ---------------------------------------------------------------------------
# Spectral region boundaries (nm), used to label a transition's region.
# These are the conventional (not razor-sharp-physical) boundaries used
# throughout optics and astronomy.
# ---------------------------------------------------------------------------

UV_VISIBLE_BOUNDARY_NM: float = 380.0
VISIBLE_IR_BOUNDARY_NM: float = 750.0


@dataclass(frozen=True)
class SpectralRegion:
    name: str
    lower_nm: float  # inclusive
    upper_nm: float  # exclusive (except last region, which is open-ended)


SPECTRAL_REGIONS: tuple[SpectralRegion, ...] = (
    SpectralRegion("Vacuum Ultraviolet", 10.0, 200.0),
    SpectralRegion("Ultraviolet", 200.0, UV_VISIBLE_BOUNDARY_NM),
    SpectralRegion("Visible", UV_VISIBLE_BOUNDARY_NM, VISIBLE_IR_BOUNDARY_NM),
    SpectralRegion("Near Infrared", VISIBLE_IR_BOUNDARY_NM, 2500.0),
    SpectralRegion("Infrared", 2500.0, float("inf")),
)


def classify_spectral_region(wavelength_nm: float) -> str:
    """Return the conventional name of the spectral region containing
    ``wavelength_nm``. Falls back to 'Infrared'/'Ultraviolet' at the
    extremes rather than raising, since these are labels, not hard
    physical cutoffs."""
    if wavelength_nm <= 0:
        raise ValueError("wavelength_nm must be positive")
    for region in SPECTRAL_REGIONS:
        if region.lower_nm <= wavelength_nm < region.upper_nm:
            return region.name
    return "Infrared"


# ---------------------------------------------------------------------------
# Unit conversion helpers
# ---------------------------------------------------------------------------

def ev_to_joule(energy_ev: float) -> float:
    return energy_ev * ELEMENTARY_CHARGE


def joule_to_ev(energy_j: float) -> float:
    return energy_j / ELEMENTARY_CHARGE


def nm_to_m(wavelength_nm: float) -> float:
    return wavelength_nm * 1e-9


def m_to_nm(wavelength_m: float) -> float:
    return wavelength_m * 1e9


def wavelength_nm_to_frequency_hz(wavelength_nm: float) -> float:
    if wavelength_nm <= 0:
        raise ValueError("wavelength_nm must be positive")
    return SPEED_OF_LIGHT / nm_to_m(wavelength_nm)


def frequency_hz_to_wavelength_nm(frequency_hz: float) -> float:
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    return m_to_nm(SPEED_OF_LIGHT / frequency_hz)


def energy_ev_to_frequency_hz(energy_ev: float) -> float:
    if energy_ev <= 0:
        raise ValueError("energy_ev must be positive")
    return ev_to_joule(energy_ev) / PLANCK_H


def frequency_hz_to_energy_ev(frequency_hz: float) -> float:
    if frequency_hz <= 0:
        raise ValueError("frequency_hz must be positive")
    return joule_to_ev(PLANCK_H * frequency_hz)


def energy_ev_to_wavelength_nm(energy_ev: float) -> float:
    """lambda = hc / delta_E"""
    if energy_ev <= 0:
        raise ValueError("energy_ev must be positive")
    return HC_EV_NM / energy_ev


def wavelength_nm_to_energy_ev(wavelength_nm: float) -> float:
    if wavelength_nm <= 0:
        raise ValueError("wavelength_nm must be positive")
    return HC_EV_NM / wavelength_nm


def kms_to_ms(velocity_kms: float) -> float:
    return velocity_kms * 1e3


def ms_to_kms(velocity_ms: float) -> float:
    return velocity_ms * 1e-3
