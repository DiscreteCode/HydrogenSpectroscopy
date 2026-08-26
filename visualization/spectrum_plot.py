"""
visualization.spectrum_plot
==============================

Renders a spectroscopy.spectrum.Spectrum: bright lines on black for
emission, dark absorption dips on a continuum for absorption (brief
section 9), with each line's wavelength/series annotated.
"""

from __future__ import annotations

from spectroscopy.spectrum import Spectrum, SpectrumMode
from visualization.theme import (
    ACCENT_WHITE,
    CONTINUUM,
    SERIES_COLORS,
    TEXT_DIM,
    apply_dark_theme,
)


def plot_spectrum(fig, ax, spectrum: Spectrum, show_labels: bool = True, reveal_frac: float = 1.0):
    """Draw the spectrum. ``reveal_frac`` in (0, 1] optionally reveals
    only the lines up to that fraction (used for the "lines appear
    sequentially" animation, brief section 16)."""
    ax.clear()

    color = ACCENT_WHITE if spectrum.mode == SpectrumMode.EMISSION else CONTINUUM
    ax.plot(spectrum.wavelength_nm, spectrum.intensity, color=color, linewidth=1.3, zorder=2)

    if spectrum.mode == SpectrumMode.EMISSION:
        ax.fill_between(spectrum.wavelength_nm, 0, spectrum.intensity, color=ACCENT_WHITE, alpha=0.08)
    else:
        ax.fill_between(spectrum.wavelength_nm, spectrum.intensity, spectrum.continuum_level,
                         color="#e85f5f", alpha=0.12)

    lines_to_show = spectrum.lines
    if reveal_frac < 1.0:
        count = max(0, int(len(spectrum.lines) * reveal_frac))
        lines_to_show = spectrum.lines[:count]

    if show_labels:
        for line in lines_to_show:
            series_color = SERIES_COLORS.get(line.transition.series or "", "#e8d24f")
            ax.axvline(line.wavelength_nm, color=series_color, linewidth=0.8, alpha=0.5, zorder=1)
            y_pos = ax.get_ylim()[1] * 0.92 if spectrum.mode == SpectrumMode.EMISSION else 0.04
            ax.annotate(
                f"{line.wavelength_nm:.1f}",
                xy=(line.wavelength_nm, y_pos),
                fontsize=7,
                color=series_color,
                ha="center",
                rotation=90,
                va="top" if spectrum.mode == SpectrumMode.EMISSION else "bottom",
            )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Relative Intensity")
    mode_label = "Emission" if spectrum.mode == SpectrumMode.EMISSION else "Absorption"
    ax.set_title(f"Hydrogen {mode_label} Spectrum")
    ax.set_xlim(spectrum.wavelength_nm.min(), spectrum.wavelength_nm.max())
    if spectrum.mode == SpectrumMode.ABSORPTION:
        ax.set_ylim(0, max(1.05, spectrum.continuum_level * 1.1))
    else:
        ax.set_ylim(0, max(spectrum.intensity.max() * 1.15, 0.01))

    apply_dark_theme(fig, [ax])
    fig.tight_layout()
