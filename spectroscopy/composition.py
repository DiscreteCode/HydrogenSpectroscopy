"""Educational multi-element stellar spectrum simulator.

Hydrogen wavelengths are computed by the project's quantum engine. He, Na,
Ca and Fe use the cited (NIST Handbook) reference-line subset in
element_database. Abundances control synthetic line depths through a
deliberately simple toy model (see ``model_line_depth``); they are NOT
inferred from real stellar data and are not physically calibrated
abundance measurements. Detection and inference from the generated
intensity live in ``spectroscopy.composition_analysis``.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from physics.blackbody import normalized_blackbody_continuum
from physics.doppler import doppler_shift_classical
from physics.line_profiles import gaussian_profile
from physics.spectral_series import get_series_transitions
from spectroscopy.element_database import ELEMENT_DATABASE, LineSource

ELEMENT_ORDER = ('H', 'He', 'Na', 'Ca', 'Fe')
DEFAULT_ABUNDANCES = {'H': 70.0, 'He': 25.0, 'Na': 2.0, 'Ca': 1.0, 'Fe': 2.0}
# Toy line-strength scale per element (dimensionless, demo only).
LINE_STRENGTH_SCALE = {'H': 0.82, 'He': 0.72, 'Na': 0.9, 'Ca': 0.78, 'Fe': 0.62}
DEPTH_COEFFICIENT = 0.65
MAX_LINE_DEPTH = 0.78


def model_line_depth(symbol: str, abundance_percent: float) -> float:
    """Toy model: depth = D_max * tanh(scale * 0.65 * sqrt(a / a_default) / D_max).

    For weak lines this is scale * 0.65 * sqrt(a / a_default); for strong
    lines it saturates smoothly below D_max (0.78) and stays invertible. It is
    NOT a curve of growth; it is a monotonic demo mapping so that abundance
    sliders visibly change line strength.
    """
    factor = abundance_percent / DEFAULT_ABUNDANCES[symbol]
    if factor <= 0:
        return 0.0
    x = LINE_STRENGTH_SCALE[symbol] * DEPTH_COEFFICIENT * np.sqrt(factor)
    return float(MAX_LINE_DEPTH * np.tanh(x / MAX_LINE_DEPTH))


def invert_model_line_depth(symbol: str, depth: float) -> float:
    """Inverse of ``model_line_depth``: abundance (% of the demo scale).

    Depths at/above 0.99 * D_max are clamped (the result is then only a lower bound).
    """
    if depth <= 0:
        return 0.0
    ratio = min(depth / MAX_LINE_DEPTH, 0.99)
    x = MAX_LINE_DEPTH * np.arctanh(ratio)
    factor = (x / (LINE_STRENGTH_SCALE[symbol] * DEPTH_COEFFICIENT)) ** 2
    return float(factor * DEFAULT_ABUNDANCES[symbol])


@dataclass(frozen=True)
class CandidateLine:
    symbol: str
    name: str
    rest_nm: float          # standard-air rest wavelength
    label: str
    source: str             # 'Quantum calculated' or 'Reference database'
    citation: str


def candidate_lines() -> list[CandidateLine]:
    """All lines the simulator can draw and the analyzer can look for."""
    lines = []
    for tr in get_series_transitions('Balmer', n_i_max=6):
        lines.append(CandidateLine('H', 'Hydrogen', float(tr.display_wavelength_nm), tr.label,
                                   'Quantum calculated',
                                   'Computed: Rydberg formula (physics.hydrogen); air wavelength via Edlen 1966'))
    for symbol in ('He', 'Na', 'Ca', 'Fe'):
        entry = ELEMENT_DATABASE[symbol]
        for ref in entry.reference_lines:
            lines.append(CandidateLine(symbol, entry.name, float(ref.wavelength_air_nm), ref.label,
                                       'Reference database', ref.citation))
    return lines


@dataclass(frozen=True)
class ElementLineResult:
    symbol: str
    name: str
    wavelength_nm: float
    label: str
    depth: float
    detected: bool

@dataclass
class CompositionSpectrum:
    wavelength_nm: np.ndarray
    intensity: np.ndarray
    continuum: np.ndarray
    abundances: dict[str, float]
    results: list[ElementLineResult]
    noise_level: float
    radial_velocity_kms: float
    # Per-element transmission (1 = no absorption) before noise; the product
    # over elements times the continuum equals the noiseless spectrum.
    element_transmission: dict[str, np.ndarray] | None = None
    temperature_k: float = 8500.0
    line_sigma_nm: float = 0.22


def generate_composition_spectrum(wavelength_nm, abundances=None, temperature_k=8500,
                                  radial_velocity_kms=0.0, noise_level=0.008,
                                  line_sigma_nm=0.22, random_seed=7):
    """Generate an illustrative synthetic spectrum with adjustable abundances.

    Abundances are relative input percentages and are normalized to 100. Line
    depths use an intentionally simple mapping for an interactive demo only.
    """
    wl = np.asarray(wavelength_nm, dtype=float)
    if wl.ndim != 1 or wl.size < 3 or not np.all(np.isfinite(wl)) or np.any(wl <= 0):
        raise ValueError('wavelength_nm must be a finite, positive 1-D grid')
    if noise_level < 0 or not np.isfinite(noise_level):
        raise ValueError('noise_level must be finite and non-negative')
    if not np.isfinite(temperature_k) or temperature_k <= 0:
        raise ValueError('temperature_k must be finite and positive')
    if not np.isfinite(radial_velocity_kms):
        raise ValueError('radial_velocity_kms must be finite')
    if not np.isfinite(line_sigma_nm) or line_sigma_nm <= 0:
        raise ValueError('line_sigma_nm must be finite and positive')
    defaults = DEFAULT_ABUNDANCES
    raw = {s: float((abundances or {}).get(s, d)) for s, d in defaults.items()}
    if any(not np.isfinite(v) or v < 0 for v in raw.values()) or sum(raw.values()) <= 0:
        raise ValueError('Abundances must be non-negative and at least one must be positive')
    total = sum(raw.values())
    normalized = {s: 100*v/total for s, v in raw.items()}
    continuum = normalized_blackbody_continuum(wl, float(temperature_k))
    intensity = continuum.copy()
    line_specs = [(c.symbol, c.name, c.rest_nm, c.label, LINE_STRENGTH_SCALE[c.symbol])
                  for c in candidate_lines()]
    transmission = {s_: np.ones_like(wl) for s_ in ELEMENT_ORDER}
    # Relative input abundance changes simulated line depth; it is not a
    # physically calibrated curve of growth and must not be read as one.
    for symbol, name, rest_nm, label, scale in line_specs:
        observed_nm = float(doppler_shift_classical(rest_nm, radial_velocity_kms))
        if wl[0] - 2 < observed_nm < wl[-1] + 2:
            depth = model_line_depth(symbol, normalized[symbol])
            if depth > 0:
                transmission[symbol] *= (1.0 - gaussian_profile(wl, observed_nm, depth, line_sigma_nm))
    for t in transmission.values():
        intensity *= t
    intensity = np.clip(intensity, 0, None)
    if noise_level:
        intensity = np.clip(intensity + np.random.default_rng(random_seed).normal(0, noise_level, wl.size), 0, None)
    # GROUND-TRUTH diagnostics: depth measured against the KNOWN synthetic
    # continuum. This is not detection; real detection from intensity alone is
    # spectroscopy.composition_analysis.analyze_composition.
    results = []
    for symbol, name, rest_nm, label, _ in line_specs:
        observed_nm = float(doppler_shift_classical(rest_nm, radial_velocity_kms))
        if observed_nm < wl[0] or observed_nm > wl[-1]:
            continue
        core = np.abs(wl - observed_nm) <= max(0.25, line_sigma_nm * 1.5)
        if not np.any(core):
            continue
        # Normalize by the known synthetic continuum rather than nearby sidebands:
        # reference lines can sit close together (e.g. He I and Na D), so sidebands
        # may accidentally include another element's absorption feature.
        relative_flux = intensity[core] / np.maximum(continuum[core], 1e-9)
        depth = max(0.0, 1.0 - float(np.median(relative_flux)))
        threshold = max(0.025, 3.0 * noise_level)
        results.append(ElementLineResult(symbol, name, observed_nm, label, depth,
                                         depth >= threshold))
    return CompositionSpectrum(wl, intensity, continuum, normalized, results,
                               float(noise_level), float(radial_velocity_kms),
                               transmission, float(temperature_k), float(line_sigma_nm))


def summarize_composition(spectrum: CompositionSpectrum):
    """Return one row per element with line hits, total reference lines, and status."""
    rows = []
    for symbol in ('H', 'He', 'Na', 'Ca', 'Fe'):
        entry = ELEMENT_DATABASE[symbol]
        lines = [r for r in spectrum.results if r.symbol == symbol]
        hits = sum(r.detected for r in lines)
        rows.append({'symbol': symbol, 'name': entry.name,
                     'abundance_percent': spectrum.abundances[symbol],
                     'lines_detected': hits, 'lines_checked': len(lines),
                     'mean_line_depth_percent': (100.0 * float(np.mean([line.depth for line in lines])) if lines else 0.0),
                     'status': 'DETECTED' if hits else 'NOT DETECTED',
                     'source': 'Quantum calculated' if entry.source == LineSource.QUANTUM_CALCULATED else 'Reference lines'})
    return rows
