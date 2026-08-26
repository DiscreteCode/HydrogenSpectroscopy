"""
spectroscopy.analyzer
=======================

The flagship pipeline described in project brief sections 10-12 and 32:

    synthetic (or imported) stellar spectrum
        -> detect absorption features
        -> compare against expected hydrogen wavelengths
        -> report matches, offsets, and an overall verdict

This module deliberately does NOT attempt a real stellar-atmosphere
model (see brief section 2). ``generate_synthetic_stellar_spectrum``
produces a blackbody continuum (physics.blackbody) with Balmer
absorption lines subtracted, an optional Doppler shift
(physics.doppler), and optional Gaussian noise -- enough to
demonstrate the matching pipeline convincingly without overclaiming
astrophysical realism.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from physics.blackbody import normalized_blackbody_continuum
from physics.doppler import doppler_shift_classical
from physics.line_profiles import gaussian_profile
from physics.spectral_series import get_series_transitions
from physics.transitions import Transition
from spectroscopy.peak_detection import DetectedFeature, find_absorption_features


@dataclass
class StellarSpectrum:
    wavelength_nm: npt.NDArray[np.floating]
    intensity: npt.NDArray[np.floating]
    continuum: npt.NDArray[np.floating]
    temperature_k: float
    radial_velocity_kms: float
    noise_level: float
    h_line_strength: float
    series_used: str


@dataclass(frozen=True)
class DetectionResult:
    label: str                  # e.g. "H-alpha (3->2)"
    n_initial: int
    n_final: int
    expected_air_nm: float
    observed_nm: float | None
    difference_nm: float | None
    matched: bool
    confidence: float           # 0..1

    @property
    def implied_velocity_kms(self) -> float | None:
        """If matched, the radial velocity implied by the wavelength
        offset -- i.e. what an astronomer would report as the
        star's Doppler shift based on this single line."""
        if self.observed_nm is None:
            return None
        from physics.doppler import velocity_from_shift_kms
        return velocity_from_shift_kms(self.expected_air_nm, self.observed_nm)


@dataclass
class HydrogenDetectionSummary:
    results: list[DetectionResult]
    detected: bool
    num_matched: int
    num_expected: int
    mean_offset_nm: float | None
    mean_velocity_kms: float | None
    message: str


def generate_synthetic_stellar_spectrum(
    wavelength_grid: npt.NDArray[np.floating],
    temperature_k: float = 9000.0,
    radial_velocity_kms: float = 0.0,
    noise_level: float = 0.02,
    h_line_strength: float = 0.6,
    series: str = "Balmer",
    n_i_max: int = 6,
    line_sigma_nm: float = 1.2,
    random_seed: int | None = None,
) -> StellarSpectrum:
    """Build a synthetic stellar absorption spectrum: blackbody
    continuum, Doppler-shifted hydrogen absorption lines, optional
    Gaussian instrumental/photon noise."""
    if not (0.0 <= h_line_strength <= 2.0):
        raise ValueError("h_line_strength should be in [0, 2] for a physically sane depth")
    if noise_level < 0:
        raise ValueError("noise_level must be >= 0")

    continuum = normalized_blackbody_continuum(wavelength_grid, temperature_k)

    transitions = get_series_transitions(series, n_i_max=n_i_max)
    intensity = continuum.copy()
    for tr in transitions:
        rest_nm = tr.display_wavelength_nm
        observed_nm = doppler_shift_classical(rest_nm, radial_velocity_kms)
        # Fainter for higher members of the series, same illustrative
        # falloff used in spectroscopy.spectrum, scaled by user strength.
        #
        # Depth is applied as a FRACTION of the *local* continuum
        # (intensity *= 1 - dip_fraction * gaussian_shape) rather than a
        # flat subtracted amplitude. The blackbody continuum is sloped,
        # not flat, so a flat subtraction can drive intensity to zero
        # over a whole plateau wherever the local continuum dips below
        # the line depth -- which flattens the line's true (Gaussian)
        # shape and biases the recovered line center, corrupting the
        # Doppler-velocity measurement. A fractional multiplicative
        # dip is bounded in (0, continuum] everywhere and keeps the
        # line's true Gaussian centroid intact.
        dip_fraction = min(0.92, h_line_strength * ((tr.n_final + 1) / tr.n_initial) ** 3)
        dip_shape = gaussian_profile(wavelength_grid, observed_nm, dip_fraction, line_sigma_nm)
        intensity = intensity * (1.0 - dip_shape)

    intensity = np.clip(intensity, a_min=0.0, a_max=None)

    if noise_level > 0:
        rng = np.random.default_rng(random_seed)
        intensity = intensity + rng.normal(0.0, noise_level, size=intensity.shape)
        intensity = np.clip(intensity, a_min=0.0, a_max=None)

    return StellarSpectrum(
        wavelength_nm=wavelength_grid,
        intensity=intensity,
        continuum=continuum,
        temperature_k=temperature_k,
        radial_velocity_kms=radial_velocity_kms,
        noise_level=noise_level,
        h_line_strength=h_line_strength,
        series_used=series,
    )


def _label_for_transition(tr: Transition) -> str:
    greek = {1: "alpha", 2: "beta", 3: "gamma", 4: "delta", 5: "epsilon"}
    step = tr.n_initial - tr.n_final
    suffix = greek.get(step, f"({tr.n_initial}->{tr.n_final})")
    return f"H-{suffix} ({tr.series}, {tr.n_initial}->{tr.n_final})" if tr.series else tr.label


def _estimate_noise_sigma(intensity: npt.NDArray[np.floating]) -> float:
    """Robust point-to-point noise estimate, insensitive to both the
    spectrum's slowly-varying continuum shape and to any narrow
    absorption/emission lines (which only perturb a handful of
    points -- the median is robust to that).

    Uses the median absolute deviation (MAD) of the first-difference
    series: for i.i.d. Gaussian noise of standard deviation sigma, the
    difference series has standard deviation sigma*sqrt(2), and
    MAD-to-sigma for a normal distribution is a factor of 1/0.6745.
    """
    diffs = np.diff(intensity)
    if diffs.size == 0:
        return 0.0
    mad = np.median(np.abs(diffs - np.median(diffs)))
    sigma_of_diff = mad / 0.6745
    return float(sigma_of_diff / np.sqrt(2.0))


def match_hydrogen_lines(
    wavelength_nm: npt.NDArray[np.floating],
    intensity: npt.NDArray[np.floating],
    continuum_level: float | npt.NDArray[np.floating] = 1.0,
    series: str = "Balmer",
    n_i_max: int = 6,
    search_window_nm: float = 3.0,
    detection_prominence: float | None = None,
    prominence_noise_sigma: float = 5.0,
    match_tolerance_nm: float = 1.0,
) -> HydrogenDetectionSummary:
    """The core identification algorithm (brief section 12):

    1. Compute expected hydrogen wavelengths for the chosen series.
    2. Detect absorption features in the observed spectrum, using a
       detection threshold that adapts to the spectrum's own noise
       level unless the caller pins one explicitly (see
       ``detection_prominence``).
    3. For each expected line, among detected features within
       ``search_window_nm``, take the DEEPEST one -- not merely the
       nearest. This matters once Doppler shifts are in play: a real
       hydrogen line is, by construction, far deeper than any noise
       fluctuation, so "deepest in the window" reliably finds the true
       shifted line instead of latching onto a shallow noise wiggle
       that happens to sit closer to the unshifted rest wavelength.
    4. Report a match if the offset is within ``match_tolerance_nm``.
    5. Summarize into an overall "hydrogen detected" verdict.

    ``detection_prominence``: if None (the default), a statistically
    motivated threshold is estimated from the spectrum itself
    (``prominence_noise_sigma`` standard deviations above the
    estimated noise floor, via a robust MAD-based estimator) rather
    than using one fixed absolute number for every spectrum. This is
    what keeps a flat, hydrogen-free, but noisy spectrum from
    accumulating spurious "matches" purely from noise clearing an
    overly permissive fixed bar -- pass an explicit float to override.
    """
    continuum_scalar = (
        float(np.mean(continuum_level)) if not np.isscalar(continuum_level) else float(continuum_level)
    )

    if detection_prominence is None:
        noise_sigma = _estimate_noise_sigma(intensity)
        detection_prominence = max(0.01, prominence_noise_sigma * noise_sigma)

    detected_features = find_absorption_features(
        wavelength_nm, intensity, continuum_level=continuum_level, prominence=detection_prominence
    )

    expected_transitions = get_series_transitions(series, n_i_max=n_i_max)

    results: list[DetectionResult] = []
    for tr in expected_transitions:
        expected_nm = tr.display_wavelength_nm
        candidates = [
            f for f in detected_features if abs(f.wavelength_nm - expected_nm) <= search_window_nm
        ]
        if candidates:
            # Deepest candidate wins (see docstring) -- ties broken by
            # closeness to the expected wavelength.
            best = max(
                candidates,
                key=lambda f: (f.depth_or_height, -abs(f.wavelength_nm - expected_nm)),
            )
            diff = best.wavelength_nm - expected_nm
            matched = abs(diff) <= match_tolerance_nm
            # Confidence blends how close the match is and how deep
            # (prominent) the detected feature is -- both simple,
            # transparent heuristics, not a statistical significance test.
            closeness = max(0.0, 1.0 - abs(diff) / match_tolerance_nm) if match_tolerance_nm > 0 else 0.0
            depth_score = min(1.0, best.depth_or_height / max(1e-6, 0.3 * continuum_scalar))
            confidence = float(np.clip(0.6 * closeness + 0.4 * depth_score, 0.0, 1.0)) if matched else float(
                np.clip(0.3 * closeness, 0.0, 0.3)
            )
            results.append(
                DetectionResult(
                    label=_label_for_transition(tr),
                    n_initial=tr.n_initial,
                    n_final=tr.n_final,
                    expected_air_nm=expected_nm,
                    observed_nm=best.wavelength_nm,
                    difference_nm=diff,
                    matched=matched,
                    confidence=confidence,
                )
            )
        else:
            results.append(
                DetectionResult(
                    label=_label_for_transition(tr),
                    n_initial=tr.n_initial,
                    n_final=tr.n_final,
                    expected_air_nm=expected_nm,
                    observed_nm=None,
                    difference_nm=None,
                    matched=False,
                    confidence=0.0,
                )
            )

    num_matched = sum(1 for r in results if r.matched)
    num_expected = len(results)
    matched_diffs = [r.difference_nm for r in results if r.matched and r.difference_nm is not None]
    mean_offset = float(np.mean(matched_diffs)) if matched_diffs else None

    matched_velocities = [
        r.implied_velocity_kms for r in results if r.matched and r.implied_velocity_kms is not None
    ]
    mean_velocity = float(np.mean(matched_velocities)) if matched_velocities else None

    # Detection threshold: require at least 2 matched lines (a single
    # coincidental dip near one expected wavelength isn't convincing;
    # a consistent multi-line pattern is exactly what real spectroscopists
    # look for).
    detected = num_matched >= 2

    if detected:
        message = (
            f"HYDROGEN DETECTED — {num_matched}/{num_expected} {series} series lines "
            f"matched within {match_tolerance_nm:g} nm."
        )
        if mean_velocity is not None:
            direction = "receding (redshifted)" if mean_velocity > 0 else "approaching (blueshifted)"
            message += f" Implied radial velocity: {mean_velocity:+.1f} km/s ({direction})."
    elif num_matched == 1:
        message = (
            f"INCONCLUSIVE — only 1/{num_expected} expected {series} line matched. "
            "A single coincidental feature isn't strong evidence; more matching lines "
            "are needed to confidently identify hydrogen."
        )
    else:
        message = (
            f"HYDROGEN NOT DETECTED — 0/{num_expected} expected {series} series lines "
            "were found within tolerance."
        )

    return HydrogenDetectionSummary(
        results=results,
        detected=detected,
        num_matched=num_matched,
        num_expected=num_expected,
        mean_offset_nm=mean_offset,
        mean_velocity_kms=mean_velocity,
        message=message,
    )
