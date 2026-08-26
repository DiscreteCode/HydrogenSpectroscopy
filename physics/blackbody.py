"""
physics.blackbody
==================

Planck's law for blackbody spectral radiance, used only to give the
Stellar Spectrum Simulator a physically motivated continuum shape that
responds to a "temperature" slider. This is standard, foundational
quantum physics (Planck's 1900 quantization of radiation is the
historical starting point for everything else in this app) and is
NOT a stellar-atmosphere model -- real stellar continua also depend on
opacity, limb darkening, etc., which are deliberately out of scope
(see project brief section 2/10). We use the blackbody curve exactly
as the brief asks: to show that a real star's continuum differs from
an idealized flat backdrop, nothing more.

    B_lambda(T) = (2hc^2 / lambda^5) * 1 / (exp(hc / (lambda*k_B*T)) - 1)
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from physics.constants import PLANCK_H, SPEED_OF_LIGHT

BOLTZMANN_K = 1.380649e-23  # J/K, exact SI 2019 value


def planck_spectral_radiance(
    wavelength_nm: "npt.NDArray[np.floating] | float",
    temperature_k: float,
) -> "npt.NDArray[np.floating] | float":
    """B_lambda(T) in SI units (W / (m^2 * sr * m)). Only relative
    shape matters for this app; callers normalize as needed."""
    if temperature_k <= 0:
        raise ValueError(f"temperature_k must be positive, got {temperature_k}")

    wavelength_m = np.asarray(wavelength_nm, dtype=float) * 1e-9
    # Guard against overflow in exp() for very short wavelengths /
    # very low temperatures by clipping the exponent.
    exponent = np.clip(
        (PLANCK_H * SPEED_OF_LIGHT) / (wavelength_m * BOLTZMANN_K * temperature_k),
        a_min=None,
        a_max=700.0,  # exp(700) is near float64's max; well past anything physical here
    )
    numerator = 2.0 * PLANCK_H * SPEED_OF_LIGHT ** 2
    denominator = (wavelength_m ** 5) * (np.exp(exponent) - 1.0)
    return numerator / denominator


def normalized_blackbody_continuum(
    wavelength_nm: npt.NDArray[np.floating],
    temperature_k: float,
) -> npt.NDArray[np.floating]:
    """Blackbody curve normalized to peak at 1.0 -- convenient as a
    dimensionless "continuum level" for synthetic stellar spectra,
    where absolute flux units aren't meaningful for this app's
    educational purposes."""
    radiance = planck_spectral_radiance(wavelength_nm, temperature_k)
    peak = np.max(radiance)
    if peak <= 0 or not np.isfinite(peak):
        raise ValueError("Blackbody continuum computation produced a non-positive peak")
    return radiance / peak


def wien_peak_wavelength_nm(temperature_k: float) -> float:
    """Wien's displacement law: lambda_peak * T = b. Useful as a
    sanity-check / educational readout alongside the continuum plot."""
    if temperature_k <= 0:
        raise ValueError(f"temperature_k must be positive, got {temperature_k}")
    wien_b = 2.897771955e-3  # m*K
    return (wien_b / temperature_k) * 1e9
