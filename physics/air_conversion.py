"""
physics.air_conversion
=======================

A subtlety that trips up almost every student (and plenty of textbooks):
the Rydberg formula, built from fundamental constants alone, predicts
the *vacuum* wavelength of a transition. There is no atmosphere in
``E = hc/lambda``. But nearly every commonly quoted hydrogen-line value
you find in textbooks (Hα "= 656.3 nm") is actually the wavelength as
measured through standard air, which has a refractive index very
slightly above 1.

    lambda_air = lambda_vacuum / n_air(lambda_vacuum)

For Hα this is a ~0.18 nm difference (656.46 nm vacuum vs 656.28 nm
air) -- small, but not rounding-error small, and it is exactly why a
naive "reproduce the textbook number to 3 decimal places" check can
look wrong even though the underlying physics is right.

This module implements the standard Edlen (1966) dispersion formula for
the refractive index of standard air (15C, 101325 Pa, 0.03% CO2),
which is the formula conventionally used for this conversion in
spectroscopy and remains accurate to ~1e-8 in n across the near-UV to
near-IR.

Reference
---------
B. Edlen, "The Refractive Index of Air", Metrologia, 2, 71 (1966).
Valid range (as conventionally applied): ~200 nm - 1700 nm. Outside
this range atmospheric transmission itself becomes the dominant
consideration (e.g. the atmosphere is opaque through much of the UV
and has strong molecular absorption bands in the IR), so an air
wavelength is not a physically meaningful quantity to quote anyway --
this module returns None in that case rather than extrapolating a
formula past its validity.
"""

from __future__ import annotations

EDLEN_VALID_RANGE_NM: tuple[float, float] = (200.0, 1700.0)


def refractive_index_standard_air(vacuum_wavelength_nm: float) -> float | None:
    """Edlen (1966) refractive index of standard air at the given
    VACUUM wavelength. Returns None if outside the formula's validity
    range rather than silently extrapolating."""
    if vacuum_wavelength_nm <= 0:
        raise ValueError("vacuum_wavelength_nm must be positive")
    lo, hi = EDLEN_VALID_RANGE_NM
    if not (lo <= vacuum_wavelength_nm <= hi):
        return None

    sigma = 1.0 / (vacuum_wavelength_nm / 1000.0)  # vacuum wavenumber, 1/micrometer
    sigma_sq = sigma * sigma
    n_minus_1 = (
        8342.13
        + 2406030.0 / (130.0 - sigma_sq)
        + 15997.0 / (38.9 - sigma_sq)
    ) * 1e-8
    return 1.0 + n_minus_1


def vacuum_to_air_nm(vacuum_wavelength_nm: float) -> float | None:
    """Convert a vacuum wavelength to the standard-air wavelength that
    a lab spectrometer (or the Earth's atmosphere) would actually
    disperse. Returns None outside the formula's validity range."""
    n = refractive_index_standard_air(vacuum_wavelength_nm)
    if n is None:
        return None
    return vacuum_wavelength_nm / n


def air_to_vacuum_nm(air_wavelength_nm: float) -> float | None:
    """Inverse of vacuum_to_air_nm. n varies extremely slowly with
    wavelength (parts per thousand), so two fixed-point iterations
    converge to double-precision accuracy -- no root-finder needed."""
    if air_wavelength_nm <= 0:
        raise ValueError("air_wavelength_nm must be positive")

    estimate = air_wavelength_nm
    for _ in range(4):
        n = refractive_index_standard_air(estimate)
        if n is None:
            return None
        estimate = air_wavelength_nm * n
    return estimate
