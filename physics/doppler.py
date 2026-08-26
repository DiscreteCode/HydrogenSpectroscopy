"""
physics.doppler
================

Radial-velocity Doppler shifting of spectral lines, as used to
interpret stellar spectra (a star moving away from us redshifts its
lines; moving toward us blueshifts them).

Two models are provided:

1. ``doppler_shift_classical`` -- the standard educational
   approximation, valid whenever v << c (true for essentially all
   stellar radial velocities, which rarely exceed a few hundred km/s,
   i.e. v/c < 0.001):

       delta_lambda / lambda = v / c

   This is the formula referenced in the project brief and is what the
   Stellar Spectrum Analysis UI uses by default.

2. ``doppler_shift_relativistic`` -- the exact special-relativistic
   formula, included so the "we are not claiming full relativistic
   accuracy unless it's actually implemented" caveat in the brief can
   be answered honestly: the exact model IS implemented and available,
   it is simply not necessary at stellar radial-velocity scales, where
   it and the classical formula agree to ~1 part in 10^6.

Sign convention: v > 0 means the source is receding (redshift,
lambda_observed > lambda_rest). v < 0 means approaching (blueshift).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from physics.constants import SPEED_OF_LIGHT


@dataclass(frozen=True)
class DopplerResult:
    rest_wavelength_nm: float
    observed_wavelength_nm: float
    velocity_kms: float
    beta: float  # v/c, signed
    relativistic: bool


def _velocity_to_beta(velocity_kms: float) -> float:
    beta = (velocity_kms * 1e3) / SPEED_OF_LIGHT
    if abs(beta) >= 1.0:
        raise ValueError(
            f"Radial velocity {velocity_kms} km/s exceeds the speed of light "
            "and is not physical."
        )
    return beta


def doppler_shift_classical(
    rest_wavelength_nm: "float | npt.NDArray[np.floating]",
    velocity_kms: float,
) -> "float | npt.NDArray[np.floating]":
    """lambda_observed = lambda_rest * (1 + v/c), valid for |v| << c."""
    beta = _velocity_to_beta(velocity_kms)
    return rest_wavelength_nm * (1.0 + beta)


def doppler_shift_relativistic(
    rest_wavelength_nm: "float | npt.NDArray[np.floating]",
    velocity_kms: float,
) -> "float | npt.NDArray[np.floating]":
    """Exact relativistic Doppler formula for radial motion:
    lambda_observed = lambda_rest * sqrt((1+beta)/(1-beta))"""
    beta = _velocity_to_beta(velocity_kms)
    return rest_wavelength_nm * np.sqrt((1.0 + beta) / (1.0 - beta))


def doppler_shift(
    rest_wavelength_nm: "float | npt.NDArray[np.floating]",
    velocity_kms: float,
    relativistic: bool = False,
) -> "float | npt.NDArray[np.floating]":
    if relativistic:
        return doppler_shift_relativistic(rest_wavelength_nm, velocity_kms)
    return doppler_shift_classical(rest_wavelength_nm, velocity_kms)


def velocity_from_shift_kms(
    rest_wavelength_nm: float,
    observed_wavelength_nm: float,
    relativistic: bool = False,
) -> float:
    """Inverse problem: given a rest and an observed wavelength, infer
    the radial velocity that would produce that shift. This is exactly
    what an astronomer does when they see a hydrogen line sitting at
    the "wrong" wavelength in a stellar spectrum."""
    if rest_wavelength_nm <= 0 or observed_wavelength_nm <= 0:
        raise ValueError("Wavelengths must be positive")

    if not relativistic:
        beta = (observed_wavelength_nm / rest_wavelength_nm) - 1.0
    else:
        ratio_sq = (observed_wavelength_nm / rest_wavelength_nm) ** 2
        beta = (ratio_sq - 1.0) / (ratio_sq + 1.0)

    return beta * (SPEED_OF_LIGHT / 1e3)  # -> km/s


def doppler_result(
    rest_wavelength_nm: float,
    velocity_kms: float,
    relativistic: bool = False,
) -> DopplerResult:
    observed = doppler_shift(rest_wavelength_nm, velocity_kms, relativistic=relativistic)
    beta = _velocity_to_beta(velocity_kms)
    return DopplerResult(
        rest_wavelength_nm=rest_wavelength_nm,
        observed_wavelength_nm=float(observed),
        velocity_kms=velocity_kms,
        beta=beta,
        relativistic=relativistic,
    )
