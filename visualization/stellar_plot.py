"""
visualization.stellar_plot
=============================

Renders the Stellar Spectrum Analyzer's overlay (brief section 12):
the observed spectrum plus markers at each expected hydrogen
wavelength, color-coded by whether a match was found.
"""

from __future__ import annotations

from spectroscopy.analyzer import HydrogenDetectionSummary, StellarSpectrum
from visualization.theme import (
    ACCENT_WHITE,
    CONTINUUM,
    LINE_MATCHED,
    LINE_UNMATCHED,
    TEXT_DIM,
    apply_dark_theme,
)


def plot_stellar_analysis(fig, ax, star: StellarSpectrum, summary: HydrogenDetectionSummary | None = None):
    ax.clear()

    ax.plot(star.wavelength_nm, star.intensity, color=ACCENT_WHITE, linewidth=1.1,
            zorder=3, label="Observed spectrum")
    ax.plot(star.wavelength_nm, star.continuum, color=CONTINUUM, linewidth=1.0,
            linestyle="--", zorder=2, label="Continuum (blackbody)")

    if summary is not None:
        for r in summary.results:
            color = LINE_MATCHED if r.matched else LINE_UNMATCHED
            ax.axvline(r.expected_air_nm, color=TEXT_DIM, linewidth=0.7, linestyle=":", alpha=0.6, zorder=1)
            if r.observed_nm is not None:
                ax.plot([r.observed_nm], [0.02], marker="^", markersize=8, color=color, zorder=5)
            ax.annotate(
                r.label.split(" (")[0],
                xy=(r.expected_air_nm, 1.02),
                fontsize=7,
                color=color,
                ha="center",
                rotation=90,
                va="bottom",
                xycoords=("data", "axes fraction"),
            )

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Relative Intensity")
    ax.set_title(f"Stellar Spectrum  (T = {star.temperature_k:.0f} K, "
                 f"v_rad = {star.radial_velocity_kms:+.0f} km/s)")
    ax.set_xlim(star.wavelength_nm.min(), star.wavelength_nm.max())
    ax.set_ylim(0, 1.15)
    ax.legend(loc="lower right", fontsize=7.5, facecolor="#0d1220", edgecolor="#1c2436",
              labelcolor=ACCENT_WHITE, framealpha=0.85)

    apply_dark_theme(fig, [ax])
    fig.tight_layout()
