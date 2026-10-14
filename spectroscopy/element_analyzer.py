"""Element-aware line matching for the educational stellar spectrum workflow.

Hydrogen transitions are matched by the existing quantum-calculated pipeline.
He, Na, Ca and Fe use explicitly labeled reference wavelengths from
spectroscopy.element_database. Results are line-identification evidence, not
stellar abundance estimates.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import numpy.typing as npt

from spectroscopy.analyzer import DetectionResult, HydrogenDetectionSummary, match_hydrogen_lines
from spectroscopy.element_database import get_element, LineSource
from spectroscopy.peak_detection import find_absorption_features


def match_element_lines(
    wavelength_nm: npt.NDArray[np.floating],
    intensity: npt.NDArray[np.floating],
    element_symbol: str,
    continuum_level: float | npt.NDArray[np.floating] = 1.0,
    search_window_nm: float = 1.4,
    match_tolerance_nm: float = 0.8,
    detection_prominence: float = 0.018,
) -> HydrogenDetectionSummary:
    """Match detected absorption features against one element's line list."""
    entry = get_element(element_symbol)
    if entry.source == LineSource.QUANTUM_CALCULATED:
        return match_hydrogen_lines(
            wavelength_nm, intensity, continuum_level=continuum_level,
            series="Balmer", n_i_max=6, search_window_nm=search_window_nm,
            match_tolerance_nm=match_tolerance_nm,
        )

    features = find_absorption_features(
        wavelength_nm, intensity, continuum_level=continuum_level,
        prominence=detection_prominence,
    )
    # Assign each detected feature to at most one reference line, avoiding
    # duplicate credit when close doublets compete for the same absorption dip.
    candidates = []
    for index, line in enumerate(entry.reference_lines):
        expected = line.wavelength_air_nm
        nearby = [f for f in features if abs(f.wavelength_nm - expected) <= search_window_nm]
        if nearby:
            best = max(nearby, key=lambda f: (f.depth_or_height, -abs(f.wavelength_nm - expected)))
            candidates.append((abs(best.wavelength_nm - expected), index, best))
        else:
            candidates.append((float("inf"), index, None))
    used_features: set[int] = set()
    chosen = {}
    for _, index, feature in sorted(candidates, key=lambda item: item[0]):
        if feature is not None and feature.index not in used_features:
            chosen[index] = feature
            used_features.add(feature.index)

    results = []
    for index, line in enumerate(entry.reference_lines):
        feature = chosen.get(index)
        diff = (feature.wavelength_nm - line.wavelength_air_nm) if feature is not None else None
        matched = diff is not None and abs(diff) <= match_tolerance_nm
        closeness = max(0.0, 1.0 - abs(diff) / match_tolerance_nm) if matched and match_tolerance_nm > 0 else 0.0
        depth_score = min(1.0, feature.depth_or_height / 0.3) if feature is not None else 0.0
        confidence = float(np.clip(0.6 * closeness + 0.4 * depth_score, 0.0, 1.0)) if matched else 0.0
        results.append(DetectionResult(
            label=f"{entry.symbol} {line.label} [reference]",
            n_initial=0, n_final=0, expected_air_nm=line.wavelength_air_nm,
            observed_nm=feature.wavelength_nm if feature is not None else None,
            difference_nm=diff, matched=bool(matched), confidence=confidence,
        ))

    count = sum(r.matched for r in results)
    expected_count = len(results)
    detected = count >= 2
    if detected:
        message = f"{entry.name.upper()} IDENTIFIED — {count}/{expected_count} reference lines matched."
    elif count == 1:
        message = f"INCONCLUSIVE — 1/{expected_count} {entry.name} reference line matched; seek a consistent multi-line pattern."
    else:
        message = f"{entry.name.upper()} NOT IDENTIFIED — no reference line matched within tolerance."
    message += " Reference wavelengths are lookup data, not quantum-calculated in this app."
    return HydrogenDetectionSummary(results, detected, count, expected_count, None, None, message)
