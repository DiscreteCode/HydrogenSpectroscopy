"""
spectroscopy.spectrum
======================

Turns a list of physics.transitions.Transition objects into an actual
plottable Spectrum: a (wavelength, intensity) curve built by summing
Gaussian line profiles (physics.line_profiles) at each transition's
wavelength.

Two spectrum "modes" are supported, matching project brief section 9:

- Emission:   baseline 0, bright peaks at each transition wavelength.
- Absorption: baseline continuum (1.0, or a supplied continuum shape),
              with dips subtracted at each transition wavelength.

A note on line intensities: this app does NOT compute quantum
mechanical transition probabilities (Einstein A-coefficients / oscillator
strengths) -- doing so correctly requires dipole matrix elements well
beyond the "quantized energy levels -> photon wavelengths" scope the
brief asks for. Default relative amplitudes use a simple, clearly
documented illustrative falloff (~1/n_i^3) so higher-series-member
lines look qualitatively fainter, matching real spectra's appearance,
without claiming quantitative accuracy. Users can override amplitudes
manually via the UI at any point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import numpy.typing as npt

from physics.line_profiles import gaussian_profile
from physics.transitions import Transition


class SpectrumMode(str, Enum):
    EMISSION = "emission"
    ABSORPTION = "absorption"


class SpectrumValidationError(ValueError):
    """Raised when a Spectrum is constructed from malformed data
    (mismatched array lengths, non-finite values, non-positive
    wavelengths, or an empty spectrum). Spectrum never silently accepts
    bad data -- callers (CSV import, GUI forms) should catch this and
    show a clear message rather than letting a broken array propagate
    into plotting/analysis code."""


@dataclass(frozen=True)
class SpectralLine:
    """One line contributing to a Spectrum -- pairs a physics
    Transition with the display choices (amplitude/width) used to
    render it."""

    transition: Transition
    amplitude: float
    sigma_nm: float

    @property
    def wavelength_nm(self) -> float:
        """The wavelength actually used for plotting -- the
        air-wavelength when defined (matches how real, ground-based
        spectra are conventionally displayed), otherwise vacuum."""
        return self.transition.display_wavelength_nm


@dataclass
class Spectrum:
    """A complete synthetic (or imported) spectrum: a wavelength grid,
    the resulting intensity curve, and the individual lines that were
    summed to produce it (kept around for annotation / legends /
    export -- empty for an imported/experimental spectrum, which has
    no known line list).

    Validated on construction (section 1 of the backend spec): array
    lengths must match, all values must be finite, wavelengths must be
    positive, and the spectrum must be non-empty. The wavelength axis
    is always stored sorted ascending -- callers never need to
    remember to sort before passing a Spectrum to anything downstream
    (peak detection, plotting, resampling all assume this).
    """

    wavelength_nm: npt.NDArray[np.floating]
    intensity: npt.NDArray[np.floating]
    mode: SpectrumMode
    lines: list[SpectralLine] = field(default_factory=list)
    continuum_level: float = 1.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.wavelength_nm = np.asarray(self.wavelength_nm, dtype=float)
        self.intensity = np.asarray(self.intensity, dtype=float)

        if self.wavelength_nm.ndim != 1 or self.intensity.ndim != 1:
            raise SpectrumValidationError("wavelength_nm and intensity must be 1D arrays")
        if self.wavelength_nm.shape != self.intensity.shape:
            raise SpectrumValidationError(
                f"wavelength_nm (len={self.wavelength_nm.size}) and intensity "
                f"(len={self.intensity.size}) must be the same length"
            )
        if self.wavelength_nm.size == 0:
            raise SpectrumValidationError("Spectrum cannot be empty")
        if not np.all(np.isfinite(self.wavelength_nm)):
            raise SpectrumValidationError("wavelength_nm contains NaN/inf values")
        if not np.all(np.isfinite(self.intensity)):
            raise SpectrumValidationError("intensity contains NaN/inf values")
        if np.any(self.wavelength_nm <= 0):
            raise SpectrumValidationError("wavelength_nm must be strictly positive")

        # Always store sorted ascending -- silently reordering isn't
        # "accepting malformed data" (the data is fine, just unordered);
        # it's what lets every downstream consumer assume a monotonic
        # axis without re-checking.
        if not np.all(np.diff(self.wavelength_nm) >= 0):
            order = np.argsort(self.wavelength_nm)
            self.wavelength_nm = self.wavelength_nm[order]
            self.intensity = self.intensity[order]

    def __len__(self) -> int:
        return self.wavelength_nm.size

    @property
    def wavelength_range_nm(self) -> tuple[float, float]:
        return float(self.wavelength_nm[0]), float(self.wavelength_nm[-1])

    def copy(self) -> "Spectrum":
        return Spectrum(
            wavelength_nm=self.wavelength_nm.copy(),
            intensity=self.intensity.copy(),
            mode=self.mode,
            lines=list(self.lines),
            continuum_level=self.continuum_level,
            metadata=dict(self.metadata),
        )

    def sort_by_wavelength(self) -> "Spectrum":
        """Returns a copy sorted by wavelength. Construction already
        guarantees this, so this is mainly useful after manually
        mutating .intensity/.wavelength_nm in place, or simply to make
        the sortedness guarantee explicit/discoverable at a call site."""
        result = self.copy()
        order = np.argsort(result.wavelength_nm)
        result.wavelength_nm = result.wavelength_nm[order]
        result.intensity = result.intensity[order]
        return result

    def select_range(self, min_nm: float, max_nm: float) -> "Spectrum":
        """Return a new Spectrum restricted to [min_nm, max_nm]."""
        if max_nm <= min_nm:
            raise ValueError(f"max_nm ({max_nm}) must exceed min_nm ({min_nm})")
        mask = (self.wavelength_nm >= min_nm) & (self.wavelength_nm <= max_nm)
        if not np.any(mask):
            raise ValueError(
                f"No samples fall within [{min_nm}, {max_nm}] nm "
                f"(spectrum covers {self.wavelength_range_nm})"
            )
        return Spectrum(
            wavelength_nm=self.wavelength_nm[mask],
            intensity=self.intensity[mask],
            mode=self.mode,
            lines=list(self.lines),
            continuum_level=self.continuum_level,
            metadata=dict(self.metadata),
        )

    def normalize(self, method: str = "max") -> "Spectrum":
        """Return a new Spectrum with intensity rescaled.

        method="max":  divide by the maximum intensity (result peaks at 1.0)
        method="area": divide by the integral (trapezoidal), i.e. unit area
        """
        result = self.copy()
        if method == "max":
            peak = np.max(np.abs(result.intensity))
            if peak <= 0:
                raise ValueError("Cannot normalize by max: spectrum peak is <= 0")
            result.intensity = result.intensity / peak
        elif method == "area":
            area = np.trapezoid(result.intensity, result.wavelength_nm)
            if area <= 0:
                raise ValueError("Cannot normalize by area: integrated area is <= 0")
            result.intensity = result.intensity / area
        else:
            raise ValueError(f"Unknown normalization method '{method}' (use 'max' or 'area')")
        return result

    def resample(self, new_wavelength_nm: npt.NDArray[np.floating]) -> "Spectrum":
        """Linearly interpolate onto a new wavelength grid (e.g. to put
        an imported spectrum on the same axis as a generated reference
        spectrum before overlaying/comparing them). Points outside the
        original coverage are filled with the nearest edge value rather
        than extrapolated."""
        new_wavelength_nm = np.asarray(new_wavelength_nm, dtype=float)
        if new_wavelength_nm.size == 0:
            raise ValueError("new_wavelength_nm cannot be empty")
        new_intensity = np.interp(
            new_wavelength_nm, self.wavelength_nm, self.intensity,
            left=self.intensity[0], right=self.intensity[-1],
        )
        return Spectrum(
            wavelength_nm=new_wavelength_nm,
            intensity=new_intensity,
            mode=self.mode,
            lines=list(self.lines),
            continuum_level=self.continuum_level,
            metadata=dict(self.metadata),
        )

    def as_csv_rows(self) -> list[tuple[float, float]]:
        return list(zip(self.wavelength_nm.tolist(), self.intensity.tolist()))

    @classmethod
    def from_arrays(
        cls,
        wavelength_nm: npt.NDArray[np.floating],
        intensity: npt.NDArray[np.floating],
        mode: "SpectrumMode | str" = SpectrumMode.ABSORPTION,
        metadata: dict | None = None,
    ) -> "Spectrum":
        """Convenience constructor for wrapping externally-sourced
        arrays (e.g. from spectroscopy.io_utils.load_spectrum_csv) as a
        validated Spectrum, without needing a line list."""
        if isinstance(mode, str):
            mode = SpectrumMode(mode)
        return cls(
            wavelength_nm=wavelength_nm,
            intensity=intensity,
            mode=mode,
            lines=[],
            metadata=metadata or {},
        )


def build_wavelength_grid(
    min_nm: float, max_nm: float, num_points: int = 4000
) -> npt.NDArray[np.floating]:
    if min_nm <= 0 or max_nm <= 0:
        raise ValueError("Wavelength range bounds must be positive")
    if max_nm <= min_nm:
        raise ValueError(f"max_nm ({max_nm}) must exceed min_nm ({min_nm})")
    if num_points < 10:
        raise ValueError(f"num_points must be at least 10, got {num_points}")
    return np.linspace(min_nm, max_nm, num_points)


def default_relative_amplitude(transition: Transition) -> float:
    """Illustrative-only intensity falloff so a Balmer series plot
    looks qualitatively like a real one (H-alpha brightest, higher
    members progressively fainter) without claiming to be a real
    computed oscillator strength. Normalized so the lowest-n_i member
    of a series (typically the brightest in practice) is near 1.0."""
    n_i = transition.n_initial
    n_f = transition.n_final
    return ((n_f + 1) / n_i) ** 3


def make_spectral_lines(
    transitions: list[Transition],
    sigma_nm: float = 0.8,
    amplitude_scale: float = 1.0,
    amplitudes: list[float] | None = None,
) -> list[SpectralLine]:
    if amplitudes is not None and len(amplitudes) != len(transitions):
        raise ValueError("amplitudes list must match transitions list length")
    lines = []
    for i, tr in enumerate(transitions):
        amp = amplitudes[i] if amplitudes else default_relative_amplitude(tr) * amplitude_scale
        lines.append(SpectralLine(transition=tr, amplitude=amp, sigma_nm=sigma_nm))
    return lines


def generate_emission_spectrum(
    lines: list[SpectralLine],
    wavelength_grid: npt.NDArray[np.floating],
) -> Spectrum:
    """Sum of Gaussian emission peaks on a zero baseline."""
    intensity = np.zeros_like(wavelength_grid)
    for line in lines:
        intensity += gaussian_profile(
            wavelength_grid, line.wavelength_nm, line.amplitude, line.sigma_nm
        )
    return Spectrum(
        wavelength_nm=wavelength_grid,
        intensity=intensity,
        mode=SpectrumMode.EMISSION,
        lines=lines,
        continuum_level=0.0,
    )


def generate_absorption_spectrum(
    lines: list[SpectralLine],
    wavelength_grid: npt.NDArray[np.floating],
    continuum: npt.NDArray[np.floating] | float = 1.0,
) -> Spectrum:
    """Continuum minus a sum of Gaussian absorption dips, clipped so
    intensity never goes negative (a real spectrograph can't measure
    negative flux)."""
    if np.isscalar(continuum):
        continuum_arr = np.full_like(wavelength_grid, float(continuum))
    else:
        continuum_arr = np.asarray(continuum, dtype=float)
        if continuum_arr.shape != wavelength_grid.shape:
            raise ValueError("continuum array must match wavelength_grid shape")

    intensity = continuum_arr.copy()
    for line in lines:
        intensity -= gaussian_profile(
            wavelength_grid, line.wavelength_nm, line.amplitude, line.sigma_nm
        )
    intensity = np.clip(intensity, a_min=0.0, a_max=None)

    return Spectrum(
        wavelength_nm=wavelength_grid,
        intensity=intensity,
        mode=SpectrumMode.ABSORPTION,
        lines=lines,
        continuum_level=float(np.mean(continuum_arr)),
    )


def generate_spectrum(
    transitions: list[Transition],
    mode: SpectrumMode,
    wavelength_grid: npt.NDArray[np.floating],
    sigma_nm: float = 0.8,
    amplitude_scale: float = 1.0,
    continuum: npt.NDArray[np.floating] | float = 1.0,
) -> Spectrum:
    """Convenience one-call entry point used by the GUI: transitions in,
    fully rendered Spectrum out."""
    lines = make_spectral_lines(transitions, sigma_nm=sigma_nm, amplitude_scale=amplitude_scale)
    if mode == SpectrumMode.EMISSION:
        return generate_emission_spectrum(lines, wavelength_grid)
    return generate_absorption_spectrum(lines, wavelength_grid, continuum=continuum)
