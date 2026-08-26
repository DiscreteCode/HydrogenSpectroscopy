"""
visualization.energy_levels
=============================

Draws the interactive hydrogen energy-level diagram (brief section 5):
horizontal lines at each E_n, n labels, the ionization limit at 0 eV,
and (optionally) a highlighted transition arrow between two levels.
"""

from __future__ import annotations

from physics.hydrogen import energy_levels
from physics.transitions import Transition
from visualization.theme import ACCENT_CYAN, ACCENT_WHITE, GRID, TEXT, TEXT_DIM, apply_dark_theme


def plot_energy_levels(fig, ax, n_max: int, transition: Transition | None = None,
                        electron_position: float | None = None):
    """Draw the energy level diagram onto the given (fig, ax).

    ``electron_position`` (0..1), if given, draws a marker interpolated
    between the initial and final level of ``transition`` -- used by
    the GUI's transition-animation timer to show the electron "falling".
    """
    ax.clear()
    levels = energy_levels(n_max=n_max)

    x_min, x_max = 0.15, 0.85
    for level in levels:
        ax.hlines(level.energy_ev, x_min, x_max, color=TEXT_DIM, linewidth=1.4, zorder=2)
        ax.text(x_max + 0.02, level.energy_ev, f"n={level.n}", va="center",
                 fontsize=8, color=TEXT, transform=ax.get_yaxis_transform())
        ax.text(x_min - 0.03, level.energy_ev, f"{level.energy_ev:.2f} eV", va="center",
                 ha="right", fontsize=7.5, color=TEXT_DIM, transform=ax.get_yaxis_transform())

    # Ionization limit at E=0
    ax.axhline(0.0, color=GRID, linewidth=1.0, linestyle="--", zorder=1)
    ax.text(x_max + 0.02, 0.0, "Ionization limit (0 eV)", va="center", fontsize=7.5,
            color=TEXT_DIM, transform=ax.get_yaxis_transform())

    if transition is not None:
        e_i = next(l.energy_ev for l in levels if l.n == transition.n_initial) \
            if transition.n_initial <= n_max else -13.6 / transition.n_initial ** 2
        e_f = next(l.energy_ev for l in levels if l.n == transition.n_final) \
            if transition.n_final <= n_max else -13.6 / transition.n_final ** 2

        x_mid = (x_min + x_max) / 2
        ax.annotate(
            "", xy=(x_mid, e_f), xytext=(x_mid, e_i),
            arrowprops=dict(arrowstyle="-|>", color=ACCENT_CYAN, lw=2.2, mutation_scale=16),
            zorder=4,
        )
        ax.hlines(e_i, x_min, x_max, color=ACCENT_WHITE, linewidth=2.4, zorder=3)
        ax.hlines(e_f, x_min, x_max, color=ACCENT_WHITE, linewidth=2.4, zorder=3)

        if electron_position is not None:
            pos = min(1.0, max(0.0, electron_position))
            e_particle = e_i + (e_f - e_i) * pos
            ax.plot([x_mid], [e_particle], marker="o", markersize=9,
                     color=ACCENT_CYAN, zorder=6, markeredgecolor=ACCENT_WHITE, markeredgewidth=1.0)

    ax.set_ylabel("Energy (eV)")
    ax.set_xlim(0, 1.35)
    ax.set_xticks([])
    ax.set_ylim(min(levels[0].energy_ev * 1.08, -1.0), max(1.0, levels[-1].energy_ev + 1.0))
    ax.set_title(f"Hydrogen Energy Levels (n = 1 to {n_max})")
    apply_dark_theme(fig, [ax])
    fig.tight_layout()
