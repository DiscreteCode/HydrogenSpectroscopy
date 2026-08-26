"""
spectroscopy.peak_detection
=============================

Finds spectral features (emission peaks or absorption dips) in a
wavelength/intensity array using scipy.signal.find_peaks. This module
knows nothing about hydrogen specifically -- it is a generic
"find local features in this curve" tool. physics-aware matching
against expected hydrogen wavelengths happens one layer up, in
spectroscopy.analyzer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.signal import find_peaks


@dataclass(frozen=True)
class DetectedFeature:
    wavelength_nm: float
    depth_or_height: float   # absorption depth (continuum - intensity) or emission height
    prominence: float
    width_nm: float | None   # None if width wasn't requested/computable
    index: int


def _features_from_curve(
    curve: npt.NDArray[np.floating],
    wavelength_nm: npt.NDArray[np.floating],
    prominence: float | None,
    distance: float | None,
    width: float | None,
    height: float | None,
) -> list[tuple[int, float, float | None]]:
    """Shared scipy.signal.find_peaks wrapper. ``distance``/``width``
    are accepted in nm (the natural unit for a spectroscopist) and
    converted to samples internally, since find_peaks itself only
    understands array-index units."""
    n = len(wavelength_nm)
    if n < 3:
        return []
    spacing_nm = float(np.mean(np.diff(wavelength_nm))) or 1e-9

    distance_samples = max(1, int(round(distance / spacing_nm))) if distance else None
    width_samples = max(1, int(round(width / spacing_nm))) if width else None
    # Always request width computation (0 = no real constraint) so
    # DetectedFeature.width_nm is populated even when the caller didn't
    # ask for width-based filtering -- it's still useful information.
    width_param = width_samples if width_samples else 0

    peak_indices, properties = find_peaks(
        curve,
        prominence=prominence,
        distance=distance_samples,
        width=width_param,
        height=height,
    )
    prominences = properties.get("prominences")
    widths = properties.get("widths")
    out = []
    for j, i in enumerate(peak_indices):
        prom = float(prominences[j]) if prominences is not None else 0.0
        width_nm = float(widths[j]) * spacing_nm if widths is not None else None
        out.append((int(i), prom, width_nm))
    return out


def find_absorption_features(
    wavelength_nm: npt.NDArray[np.floating],
    intensity: npt.NDArray[np.floating],
    continuum_level: "float | npt.NDArray[np.floating]" = 1.0,
    prominence: float | None = 0.02,
    distance_nm: float | None = None,
    width_nm: float | None = None,
    height: float | None = None,
) -> list[DetectedFeature]:
    """Detect absorption dips by finding peaks in (continuum - intensity).

    ``distance_nm`` enforces a minimum separation between reported
    features (useful for noisy spectra producing spurious close-together
    detections); ``width_nm`` requires a minimum feature width in nm."""
    depth_curve = continuum_level - intensity
    raw = _features_from_curve(depth_curve, wavelength_nm, prominence, distance_nm, width_nm, height)
    features = [
        DetectedFeature(
            wavelength_nm=float(wavelength_nm[i]),
            depth_or_height=float(depth_curve[i]),
            prominence=prom,
            width_nm=w,
            index=i,
        )
        for i, prom, w in raw
    ]
    return sorted(features, key=lambda f: f.wavelength_nm)


def find_emission_features(
    wavelength_nm: npt.NDArray[np.floating],
    intensity: npt.NDArray[np.floating],
    prominence: float | None = 0.05,
    distance_nm: float | None = None,
    width_nm: float | None = None,
    height: float | None = None,
) -> list[DetectedFeature]:
    """Detect emission peaks directly in the intensity curve."""
    raw = _features_from_curve(intensity, wavelength_nm, prominence, distance_nm, width_nm, height)
    features = [
        DetectedFeature(
            wavelength_nm=float(wavelength_nm[i]),
            depth_or_height=float(intensity[i]),
            prominence=prom,
            width_nm=w,
            index=i,
        )
        for i, prom, w in raw
    ]
    return sorted(features, key=lambda f: f.wavelength_nm)


def estimate_local_continuum(
    wavelength_nm: npt.NDArray[np.floating],
    intensity: npt.NDArray[np.floating],
    window_frac: float = 0.05,
) -> npt.NDArray[np.floating]:
    """A simple, robust continuum estimate for spectra that don't carry
    a known analytic continuum (e.g. an imported CSV file): a rolling
    maximum-ish percentile filter. This is intentionally simple --
    real continuum normalization is a research topic in itself and out
    of scope for this app (see brief section 2) -- it only needs to be
    good enough to let peak_detection find dips relative to *something*
    reasonable.
    """
    n = len(intensity)
    window = max(5, int(n * window_frac))
    continuum = np.empty_like(intensity)
    half = window // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        continuum[i] = np.percentile(intensity[lo:hi], 90)
    return continuum
