"""
scripts/generate_sample_spectra.py
====================================

Generates the built-in sample spectra shipped under data/sample_spectra/
so the application has something to show immediately, with zero
external files required (project brief section 13).

Every file here is produced by the SAME backend pipeline the GUI will
call (spectroscopy.spectrum / spectroscopy.analyzer) -- nothing is
hand-drawn. Re-run this script any time the physics engine or spectrum
generation logic changes, to keep the shipped samples consistent.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from physics.spectral_series import get_series_transitions  # noqa: E402
from spectroscopy import io_utils as io  # noqa: E402
from spectroscopy.analyzer import generate_synthetic_stellar_spectrum, match_hydrogen_lines  # noqa: E402
from spectroscopy.spectrum import (  # noqa: E402
    build_wavelength_grid,
    generate_emission_spectrum,
    make_spectral_lines,
)

OUT_DIR = REPO_ROOT / "data" / "sample_spectra"


def make_clean_hydrogen_emission_spectrum() -> None:
    """A pure laboratory-style hydrogen emission spectrum: the Balmer
    series (n=3..6 -> n=2), nothing else. This is what the Spectrum
    Simulator / Transition Explorer pages show as the 'reference'."""
    transitions = get_series_transitions("Balmer", n_i_max=6)
    grid = build_wavelength_grid(380.0, 700.0, 6000)
    lines = make_spectral_lines(transitions, sigma_nm=0.6)
    spectrum = generate_emission_spectrum(lines, grid)
    path = OUT_DIR / "hydrogen_balmer_emission.csv"
    io.export_spectrum_csv(path, spectrum.wavelength_nm, spectrum.intensity)
    print(f"wrote {path}  ({len(spectrum)} points, mode={spectrum.mode.value})")


def make_noisy_stellar_spectrum() -> None:
    """A synthetic star at rest (no radial velocity) with realistic
    photon noise -- the 'easy' stellar-detection demo case."""
    grid = build_wavelength_grid(380.0, 700.0, 6000)
    star = generate_synthetic_stellar_spectrum(
        grid,
        temperature_k=9000.0,
        radial_velocity_kms=0.0,
        noise_level=0.015,
        h_line_strength=0.7,
        random_seed=42,
    )
    path = OUT_DIR / "stellar_noisy_at_rest.csv"
    io.export_spectrum_csv(path, star.wavelength_nm, star.intensity)
    summary = match_hydrogen_lines(star.wavelength_nm, star.intensity, continuum_level=star.continuum)
    print(f"wrote {path}  (detected={summary.detected}, {summary.num_matched}/{summary.num_expected} matched)")


def make_doppler_shifted_stellar_spectrum() -> None:
    """A synthetic star receding at +180 km/s -- demonstrates redshifted
    hydrogen lines and lets the analyzer's implied-velocity readout be
    exercised against a known ground truth."""
    grid = build_wavelength_grid(380.0, 700.0, 6000)
    star = generate_synthetic_stellar_spectrum(
        grid,
        temperature_k=8500.0,
        radial_velocity_kms=180.0,
        noise_level=0.01,
        h_line_strength=0.7,
        random_seed=7,
    )
    path = OUT_DIR / "stellar_doppler_shifted_180kms.csv"
    io.export_spectrum_csv(path, star.wavelength_nm, star.intensity)
    summary = match_hydrogen_lines(star.wavelength_nm, star.intensity, continuum_level=star.continuum)
    print(
        f"wrote {path}  (detected={summary.detected}, "
        f"implied_v={summary.mean_velocity_kms:.1f} km/s, true_v=180.0 km/s)"
    )


def make_no_hydrogen_control_spectrum() -> None:
    """A flat, featureless continuum -- a negative control so users can
    see the analyzer correctly report NOT DETECTED on a star with no
    hydrogen signature, not just always say yes."""
    import numpy as np
    from physics.blackbody import normalized_blackbody_continuum

    grid = build_wavelength_grid(380.0, 700.0, 6000)
    continuum = normalized_blackbody_continuum(grid, 9000.0)
    rng = np.random.default_rng(99)
    intensity = continuum + rng.normal(0.0, 0.01, size=continuum.shape)
    intensity = np.clip(intensity, 0.0, None)
    path = OUT_DIR / "stellar_no_hydrogen_control.csv"
    io.export_spectrum_csv(path, grid, intensity)
    summary = match_hydrogen_lines(grid, intensity, continuum_level=continuum)
    print(f"wrote {path}  (detected={summary.detected}, {summary.num_matched}/{summary.num_expected} matched)")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    make_clean_hydrogen_emission_spectrum()
    make_noisy_stellar_spectrum()
    make_doppler_shifted_stellar_spectrum()
    make_no_hydrogen_control_spectrum()
