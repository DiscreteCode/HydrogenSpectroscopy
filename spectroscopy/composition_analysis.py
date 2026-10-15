"""Blind line detection and demo-model abundance inference.

``analyze_composition`` sees ONLY ``wavelength_nm`` and ``intensity``. It never
reads the simulator's true continuum, true radial velocity, true line width or
true abundances. The pipeline is:

1. Estimate the continuum (asymmetric-clipped polynomial fit in log flux).
2. Estimate the radial velocity by scanning a Doppler shift that best aligns
   the known candidate lines (H computed by the quantum engine; He/Na/Ca/Fe
   from the cited reference database) with the observed absorption.
3. Jointly fit one Gaussian absorption depth per candidate line (plus a shared
   velocity and a shared line width) with bounded non-linear least squares.
   Per-line depth uncertainties come from the fit covariance.
4. A line is "detected" if its fitted depth is at least ``min_depth`` and at
   least ``min_significance`` times its uncertainty. Peaks found in the
   smoothed spectrum are matched to reference lines for the wavelength table.
5. Per-element depth is inverted through the SAME toy line-strength model the
   simulator uses (``spectroscopy.composition.model_line_depth``) to give an
   *inferred* relative abundance.

IMPORTANT LIMITATION: step 5 is only meaningful because the analyzer knows the
toy model that generated the data. It is a demonstration of the inference
workflow, NOT a real stellar abundance determination: real abundances require
curves of growth or model atmospheres (temperature, pressure, ionization,
oscillator strengths, microturbulence, NLTE...), none of which are modelled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.optimize import least_squares
from scipy.signal import find_peaks

from physics.constants import SPEED_OF_LIGHT
from spectroscopy.composition import (
    ELEMENT_ORDER, MAX_LINE_DEPTH, CandidateLine, candidate_lines,
    invert_model_line_depth,
)
from spectroscopy.element_database import ELEMENT_DATABASE

C_KMS = SPEED_OF_LIGHT / 1000.0


@dataclass(frozen=True)
class LineMatch:
    symbol: str
    name: str
    label: str
    source: str
    reference_nm: float            # rest standard-air wavelength (database / computed)
    expected_observed_nm: float    # reference shifted by the fitted velocity
    detected_wavelength_nm: float  # peak found in the data (NaN if no separate peak)
    fitted_depth: float            # fractional absorption depth (0..1)
    depth_sigma: float             # 1-sigma fit uncertainty on the depth
    significance: float            # fitted_depth / depth_sigma
    detected: bool
    blended: bool                  # another candidate line lies within ~3 fitted sigmas
    citation: str


@dataclass(frozen=True)
class ElementInference:
    symbol: str
    name: str
    source: str
    lines_detected: int
    lines_checked: int
    mean_depth: float
    inferred_percent: float
    inferred_sigma_percent: float  # statistical only; excludes model error
    detected: bool
    saturated: bool                # depth at the toy model's cap: lower bound only


@dataclass
class CompositionAnalysis:
    wavelength_nm: np.ndarray
    normalized_flux: np.ndarray
    continuum_estimate: np.ndarray
    fitted_model: np.ndarray       # fitted normalized flux
    radial_velocity_kms: float
    radial_velocity_sigma_kms: float
    line_sigma_nm: float
    noise_sigma: float             # rms residual of the fit, in intensity units
    matches: list[LineMatch] = field(default_factory=list)
    elements: list[ElementInference] = field(default_factory=list)
    fit_converged: bool = True
    notes: list[str] = field(default_factory=list)

    def element(self, symbol: str) -> ElementInference:
        for row in self.elements:
            if row.symbol == symbol:
                return row
        raise KeyError(symbol)


def estimate_continuum(wavelength_nm, intensity, degree: int = 7, iterations: int = 20,
                       lower_clip: float = 1.5) -> np.ndarray:
    """Polynomial continuum in log flux; points below the fit are iteratively
    rejected so absorption lines do not drag the continuum down."""
    wl = np.asarray(wavelength_nm, float)
    flux = np.clip(np.asarray(intensity, float), 1e-6, None)
    x = 2.0 * (wl - wl[0]) / (wl[-1] - wl[0]) - 1.0
    y = np.log(flux)
    keep = np.ones(wl.size, bool)
    coeffs = np.polyfit(x, y, degree)
    for _ in range(iterations):
        if keep.sum() < degree + 2:
            break
        coeffs = np.polyfit(x[keep], y[keep], degree)
        resid = y - np.polyval(coeffs, x)
        sigma = max(1.4826 * np.median(np.abs(resid[keep] - np.median(resid[keep]))), 1e-6)
        new_keep = (resid > -lower_clip * sigma) & (resid < 3.0 * sigma)
        if np.array_equal(new_keep, keep):
            break
        keep = new_keep
    return np.exp(np.polyval(coeffs, x))


def _absorption_model(wl, centers, depths, sigma):
    model = np.ones_like(wl)
    for c, d in zip(centers, depths):
        lo = np.searchsorted(wl, c - 6.0 * sigma)
        hi = np.searchsorted(wl, c + 6.0 * sigma)
        if hi > lo:
            seg = wl[lo:hi]
            model[lo:hi] *= 1.0 - d * np.exp(-0.5 * ((seg - c) / sigma) ** 2)
    return model


def _scan_velocity(wl, smooth_depth, rest, max_abs_rv):
    step = 0.04 / np.median(rest) * C_KMS  # ~0.04 nm at the median line
    trial = np.arange(-max_abs_rv, max_abs_rv + step, step)
    scores = np.empty(trial.size)
    for i, v in enumerate(trial):
        pos = rest * (1.0 + v / C_KMS)
        inside = (pos > wl[0]) & (pos < wl[-1])
        scores[i] = np.sum(np.clip(np.interp(pos[inside], wl, smooth_depth), 0, None))
    best = trial[int(np.argmax(scores))]
    fine = np.arange(best - step, best + step, step / 20.0)
    fine_scores = []
    for v in fine:
        pos = rest * (1.0 + v / C_KMS)
        inside = (pos > wl[0]) & (pos < wl[-1])
        fine_scores.append(np.sum(np.clip(np.interp(pos[inside], wl, smooth_depth), 0, None)))
    return float(fine[int(np.argmax(fine_scores))])


def analyze_composition(wavelength_nm, intensity, *, radial_velocity_kms: float | None = None,
                        max_abs_rv_kms: float = 400.0, min_significance: float = 5.0,
                        min_depth: float = 0.02, match_tolerance_nm: float = 0.4,
                        ) -> CompositionAnalysis:
    """Detect lines and infer demo-model relative abundances from intensity only.

    ``radial_velocity_kms`` is an optional starting guess (the fit is still
    free to move within +/-100 km/s). Leave it None to scan blindly.
    """
    wl = np.asarray(wavelength_nm, float)
    flux = np.asarray(intensity, float)
    if wl.ndim != 1 or wl.shape != flux.shape or wl.size < 50:
        raise ValueError('wavelength_nm and intensity must be 1-D arrays of equal length (>= 50 points)')
    if not (np.all(np.isfinite(wl)) and np.all(np.isfinite(flux))):
        raise ValueError('wavelength_nm and intensity must be finite')
    if np.any(np.diff(wl) <= 0):
        raise ValueError('wavelength_nm must be strictly increasing')
    if np.max(flux) <= 0:
        raise ValueError('intensity must contain positive values')
    if not np.isfinite(max_abs_rv_kms) or max_abs_rv_kms <= 0:
        raise ValueError('max_abs_rv_kms must be positive and finite')
    spacing = float(np.median(np.diff(wl)))

    continuum = estimate_continuum(wl, flux)
    normalized = flux / continuum
    depth = 1.0 - normalized
    smooth = gaussian_filter1d(depth, max(1.0, 0.08 / spacing))

    cands: list[CandidateLine] = candidate_lines()
    rest_all = np.array([c.rest_nm for c in cands])
    notes: list[str] = []

    # --- radial velocity (blind scan unless a starting guess is given) ---
    if radial_velocity_kms is None:
        v0 = _scan_velocity(wl, smooth, rest_all, max_abs_rv_kms)
        v_lo, v_hi = -max_abs_rv_kms, max_abs_rv_kms
    else:
        if not np.isfinite(radial_velocity_kms):
            raise ValueError('radial_velocity_kms must be finite')
        v0 = float(radial_velocity_kms)
        v_lo, v_hi = v0 - 100.0, v0 + 100.0

    # --- candidate lines that can fall inside the grid at v0 (small margin) ---
    margin = 1.0
    keep_idx = [i for i, c in enumerate(cands)
                if wl[0] - margin < c.rest_nm * (1 + v0 / C_KMS) < wl[-1] + margin]
    cands = [cands[i] for i in keep_idx]
    rest = np.array([c.rest_nm for c in cands])
    n = len(cands)
    if n == 0:
        raise ValueError('No candidate reference lines fall inside the supplied wavelength range')

    # --- initial line width from the strongest isolated-looking peaks ---
    sigma0 = 0.2
    pk, props = find_peaks(smooth, prominence=max(5 * np.std(smooth - np.median(smooth)) * 0.2, 0.03),
                           width=1, rel_height=0.5)
    if pk.size:
        order = np.argsort(props['prominences'])[::-1][:6]
        fwhm = float(np.median(props['widths'][order]) * spacing)
        sigma0 = float(np.clip(fwhm / 2.355, 0.05, 1.0))

    x_norm = 2.0 * (wl - wl[0]) / (wl[-1] - wl[0]) - 1.0

    def run_fit(cont, start, max_nfev):
        def residual(theta):
            model = _absorption_model(wl, rest * (1.0 + theta[0] / C_KMS), theta[2:], theta[1])
            return flux - cont * model
        return least_squares(residual, start, bounds=(lower, upper), x_scale=x_scale,
                             method='trf', max_nfev=max_nfev)

    x0 = np.concatenate([[np.clip(v0, v_lo, v_hi), sigma0], np.full(n, 0.05)])
    lower = np.concatenate([[v_lo, 0.03], np.zeros(n)])
    upper = np.concatenate([[v_hi, 1.5], np.full(n, 0.97)])
    x_scale = np.concatenate([[20.0, 0.05], np.full(n, 0.1)])
    sol = run_fit(continuum, x0, 60)
    # Second pass: line-crowded regions bias the clipped-polynomial continuum low.
    # Divide the fitted lines out, re-fit the continuum on the cleaned flux, refit.
    cleaned = flux / np.maximum(_absorption_model(
        wl, rest * (1.0 + sol.x[0] / C_KMS), sol.x[2:], sol.x[1]), 0.05)
    cont_coef = np.polyfit(x_norm, np.log(np.clip(cleaned, 1e-6, None)), 7)
    continuum = np.exp(np.polyval(cont_coef, x_norm))
    normalized = flux / continuum
    sol = run_fit(continuum, sol.x, 40)
    theta = sol.x
    v_fit, sig_fit, depths = float(theta[0]), float(theta[1]), theta[2:]
    resid = sol.fun
    dof = max(wl.size - theta.size, 1)
    noise = max(float(np.sqrt(np.sum(resid ** 2) / dof)), 1e-5)
    try:
        cov = np.linalg.pinv(sol.jac.T @ sol.jac) * noise ** 2
        sig_all = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        sig_all = np.full(theta.size, np.inf)
        notes.append('Fit covariance could not be computed; uncertainties unavailable.')
    v_sigma, depth_sigma = float(sig_all[0]), sig_all[2:]
    if not sol.success:
        notes.append('Least-squares fit did not report convergence; treat results with caution.')
    fitted_model = _absorption_model(wl, rest * (1.0 + v_fit / C_KMS), depths, sig_fit)

    # --- peaks in the data for the wavelength table ---
    depth_noise = noise / max(float(np.median(continuum)), 1e-9)
    smooth_noise = depth_noise / np.sqrt(max(sig_fit / spacing, 1.0))
    prom = max(5.0 * smooth_noise, 0.5 * min_depth)
    peaks, _ = find_peaks(smooth, prominence=prom, distance=max(1, int(0.15 / spacing)))
    peak_wl = wl[peaks]

    expected = rest * (1.0 + v_fit / C_KMS)
    matches: list[LineMatch] = []
    for i, c in enumerate(cands):
        d, ds = float(depths[i]), float(depth_sigma[i])
        sig_level = d / ds if ds > 0 else (np.inf if d > 0 else 0.0)
        detected = bool(d >= min_depth and sig_level >= min_significance)
        near = [j for j in range(n) if j != i and abs(expected[j] - expected[i]) < 3.0 * sig_fit]
        detected_wl = float('nan')
        if peak_wl.size and detected:
            k = int(np.argmin(np.abs(peak_wl - expected[i])))
            if abs(peak_wl[k] - expected[i]) <= match_tolerance_nm:
                detected_wl = float(peak_wl[k])
        matches.append(LineMatch(
            c.symbol, c.name, c.label, c.source, float(c.rest_nm), float(expected[i]), detected_wl,
            d, ds, float(sig_level), detected, bool(near), c.citation))

    # --- per-element inference through the demo toy model ---
    raw_a: dict[str, float] = {}
    raw_sig: dict[str, float] = {}
    rows: dict[str, dict] = {}
    for sym in ELEMENT_ORDER:
        mine = [m for m in matches if m.symbol == sym]
        det = [m for m in mine if m.detected]
        if det:
            w = np.array([1.0 / max(m.depth_sigma, 1e-4) ** 2 for m in det])
            dvals = np.array([m.fitted_depth for m in det])
            dmean = float(np.sum(w * dvals) / np.sum(w))
            dsig = float(1.0 / np.sqrt(np.sum(w)))
            a = invert_model_line_depth(sym, dmean)
            ratio = min(dmean / MAX_LINE_DEPTH, 0.99)
            # d(a)/d(depth) by central difference through the inverse model
            eps = 1e-4
            da = (invert_model_line_depth(sym, min(dmean + eps, 0.99 * MAX_LINE_DEPTH))
                  - invert_model_line_depth(sym, max(dmean - eps, 0.0))) / (2 * eps)
            asig = abs(da) * dsig
            saturated = ratio >= 0.93
        else:
            dmean, dsig, a, asig, saturated = 0.0, 0.0, 0.0, 0.0, False
        raw_a[sym], raw_sig[sym] = a, asig
        rows[sym] = dict(n_det=len(det), n=len(mine), dmean=dmean, saturated=saturated, det=bool(det))
    total = sum(raw_a.values())
    elements = []
    for sym in ELEMENT_ORDER:
        r = rows[sym]
        entry = ELEMENT_DATABASE[sym]
        pct = 100.0 * raw_a[sym] / total if total > 0 else 0.0
        sp = 100.0 * raw_sig[sym] / total if total > 0 else 0.0
        src = 'Quantum calculated' if sym == 'H' else 'Reference database'
        elements.append(ElementInference(sym, entry.name, src, r['n_det'], r['n'], r['dmean'],
                                         pct, sp, r['det'], r['saturated']))
    if any(e.saturated for e in elements):
        notes.append('At least one element is near the toy-model saturation depth; its inferred value is a lower bound / imprecise.')
    return CompositionAnalysis(wl, normalized, continuum, fitted_model, v_fit, v_sigma, sig_fit,
                               noise, matches, elements, bool(sol.success), notes)


def compare_input_and_inferred(analysis: CompositionAnalysis, input_percent: dict[str, float]):
    """Rows pairing SIMULATED INPUT with INFERRED abundance (both in demo % units)."""
    rows = []
    for e in analysis.elements:
        inp = float(input_percent.get(e.symbol, 0.0))
        rows.append({'symbol': e.symbol, 'name': e.name, 'input_percent': inp,
                     'inferred_percent': e.inferred_percent,
                     'difference_percent': e.inferred_percent - inp,
                     'detected': e.detected})
    return rows


def write_analysis_csv(handle, spectrum, analysis: CompositionAnalysis, *,
                       hide_solution: bool = False) -> None:
    """Write spectrum + analysis to an open text handle (``newline=''``).

    Sections: element summary, detected-line table, spectral data. SIMULATED
    INPUT abundances and INFERRED abundances are always separate columns.
    With ``hide_solution`` (unrevealed Mystery Star) every value that would
    reveal the hidden input, or the analysis built on it, is written as
    'Hidden' and the per-element truth columns are omitted.
    """
    import csv
    w = csv.writer(handle)
    hid = 'Hidden'
    w.writerow(['# Hydrogen Quantum Spectroscopy - synthetic stellar composition analysis'])
    w.writerow(['# SIMULATED INPUT abundances are the weights chosen for the simulation (demo units, normalized to 100).'])
    w.writerow(['# INFERRED abundances come from blind line fitting of the intensity through the SAME toy model;'])
    w.writerow(['# they are not measurements, and not real stellar abundances.'])
    w.writerow(['# Wavelengths: standard-air nm. Intensity: normalized to the blackbody peak (dimensionless).'])
    if not hide_solution:
        w.writerow(['# Simulation parameters', f'noise_sigma={spectrum.noise_level}',
                    f'line_sigma_nm={spectrum.line_sigma_nm}', f'radial_velocity_kms={spectrum.radial_velocity_kms}',
                    f'temperature_k={spectrum.temperature_k}'])
    w.writerow(['# Estimated by analysis', f'radial_velocity_kms={analysis.radial_velocity_kms:.3f}',
                f'radial_velocity_sigma_kms={analysis.radial_velocity_sigma_kms:.3f}',
                f'line_sigma_nm={analysis.line_sigma_nm:.4f}', f'noise_rms={analysis.noise_sigma:.5f}'])
    w.writerow([])
    w.writerow(['# SECTION: element summary'])
    w.writerow(['Element', 'Simulated input (%)', 'Lines detected', 'Lines checked',
                'Mean fitted depth (%)', 'Status', 'Inferred (%)', 'Inferred 1-sigma statistical (%)',
                'Inferred minus input (%)', 'Line source'])
    for e in analysis.elements:
        if hide_solution:
            w.writerow([e.name] + [hid] * 8 + [e.source])
        else:
            inp = spectrum.abundances.get(e.symbol, 0.0)
            w.writerow([e.name, f'{inp:.3f}', e.lines_detected, e.lines_checked,
                        f'{100 * e.mean_depth:.3f}', 'DETECTED' if e.detected else 'NOT DETECTED',
                        f'{e.inferred_percent:.3f}', f'{e.inferred_sigma_percent:.3f}',
                        f'{e.inferred_percent - inp:.3f}', e.source])
    w.writerow([])
    w.writerow(['# SECTION: detected lines'])
    w.writerow(['Symbol', 'Line', 'Reference wavelength (nm, air)', 'Expected observed wavelength (nm)',
                'Detected wavelength (nm)', 'Detected minus expected (nm)', 'Fitted depth (%)',
                'Depth 1-sigma (%)', 'Significance (sigma)', 'Detected', 'Blended', 'Line source', 'Citation'])
    for m in sorted(analysis.matches, key=lambda m: m.expected_observed_nm):
        has = np.isfinite(m.detected_wavelength_nm)
        w.writerow([m.symbol, m.label, f'{m.reference_nm:.4f}', f'{m.expected_observed_nm:.4f}',
                    f'{m.detected_wavelength_nm:.4f}' if has else '',
                    f'{m.detected_wavelength_nm - m.expected_observed_nm:.4f}' if has else '',
                    f'{100 * m.fitted_depth:.3f}', f'{100 * m.depth_sigma:.3f}',
                    f'{m.significance:.1f}', 'yes' if m.detected else 'no',
                    'yes' if m.blended else 'no', m.source, m.citation])
    w.writerow([])
    w.writerow(['# SECTION: spectrum'])
    cols = ['Wavelength (nm)', 'Observed intensity', 'Estimated continuum',
            'Normalized flux', 'Fitted model (normalized)']
    contrib = None
    if not hide_solution and spectrum.element_transmission:
        contrib = [(s, spectrum.element_transmission[s]) for s in ELEMENT_ORDER
                   if s in spectrum.element_transmission]
        cols += [f'{s} absorption (simulated truth, 1 - transmission)' for s, _ in contrib]
    w.writerow(cols)
    for i in range(analysis.wavelength_nm.size):
        row = [f'{analysis.wavelength_nm[i]:.5f}', f'{spectrum.intensity[i]:.6f}',
               f'{analysis.continuum_estimate[i]:.6f}', f'{analysis.normalized_flux[i]:.6f}',
               f'{analysis.fitted_model[i]:.6f}']
        if contrib:
            row += [f'{1.0 - t[i]:.6f}' for _, t in contrib]
        w.writerow(row)
