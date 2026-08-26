"""
physics.line_profiles
======================

Real spectral lines are never infinitely thin -- Doppler motion of
atoms, pressure broadening, and instrumental resolution all smear a
transition's theoretical wavelength lambda_0 into a finite-width
profile. This module turns a single (wavelength, intensity) pair into
an intensity curve I(lambda) over a wavelength grid.

The Gaussian profile is the primary, required profile (matches the
project spec):

    I(lambda) = A * exp( -(lambda - lambda_0)^2 / (2 * sigma^2) )

A Lorentzian option is also provided since it is the natural profile
for pressure/collisional broadening and costs nothing extra to expose,
but Gaussian remains the default everywhere in the UI.
"""

from __future__ import annotations

from enum import Enum

import numpy as np
import numpy.typing as npt


class ProfileKind(str, Enum):
    GAUSSIAN = "gaussian"
    LORENTZIAN = "lorentzian"


def gaussian_profile(
    wavelength_grid: npt.NDArray[np.floating],
    center_nm: float,
    amplitude: float,
    sigma_nm: float,
) -> npt.NDArray[np.floating]:
    """I(lambda) = A * exp(-(lambda - lambda_0)^2 / (2 sigma^2))"""
    if sigma_nm <= 0:
        raise ValueError(f"sigma_nm must be positive, got {sigma_nm}")
    return amplitude * np.exp(
        -((wavelength_grid - center_nm) ** 2) / (2.0 * sigma_nm ** 2)
    )


def lorentzian_profile(
    wavelength_grid: npt.NDArray[np.floating],
    center_nm: float,
    amplitude: float,
    gamma_nm: float,
) -> npt.NDArray[np.floating]:
    """I(lambda) = A * gamma^2 / ((lambda - lambda_0)^2 + gamma^2)

    gamma_nm is the half-width at half-maximum (HWHM).
    """
    if gamma_nm <= 0:
        raise ValueError(f"gamma_nm must be positive, got {gamma_nm}")
    return amplitude * (gamma_nm ** 2) / (
        (wavelength_grid - center_nm) ** 2 + gamma_nm ** 2
    )


def line_profile(
    kind: ProfileKind,
    wavelength_grid: npt.NDArray[np.floating],
    center_nm: float,
    amplitude: float,
    width_nm: float,
) -> npt.NDArray[np.floating]:
    """Dispatch helper so callers can select a profile by enum/string
    without an if/else at every call site."""
    if kind == ProfileKind.GAUSSIAN:
        return gaussian_profile(wavelength_grid, center_nm, amplitude, width_nm)
    if kind == ProfileKind.LORENTZIAN:
        return lorentzian_profile(wavelength_grid, center_nm, amplitude, width_nm)
    raise ValueError(f"Unknown profile kind: {kind}")


def fwhm_from_sigma(sigma_nm: float) -> float:
    """Full width at half maximum for a Gaussian, given sigma.
    FWHM = 2*sqrt(2*ln(2)) * sigma  ≈ 2.3548 * sigma"""
    return 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma_nm


def sigma_from_fwhm(fwhm_nm: float) -> float:
    """Inverse of fwhm_from_sigma -- convenient when a user specifies
    broadening in terms of the more intuitive FWHM."""
    return fwhm_nm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
