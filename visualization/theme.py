"""
visualization.theme
=====================

Single source of truth for the app's visual identity: a dark
astronomical/scientific instrument look (brief section 14), applied
consistently across every matplotlib figure so the Energy Level
diagram, spectrum plots, and stellar overlay all feel like one
application rather than three different demos stitched together.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")  # safe default; app/widgets/mpl_canvas.py owns the Qt backend wiring

import matplotlib.pyplot as plt

BG_FIGURE = "#0a0e17"
BG_AXES = "#0d1220"
GRID = "#1c2436"
TEXT = "#c9d3e6"
TEXT_DIM = "#7c869c"
ACCENT_BLUE = "#4f8fe8"
ACCENT_PURPLE = "#9d7ce8"
ACCENT_CYAN = "#4fd1e8"
ACCENT_WHITE = "#f2f5fb"
LINE_MATCHED = "#39d98a"
LINE_UNMATCHED = "#e85f5f"
CONTINUUM = "#3d4a68"

SERIES_COLORS = {
    "Lyman": "#9d7ce8",
    "Balmer": "#4fd1e8",
    "Paschen": "#e8a94f",
    "Brackett": "#e85f9d",
    "Pfund": "#7ce89d",
}


def apply_dark_theme(fig, ax_list=None):
    """Apply the app's dark theme to a Figure and its Axes in place."""
    fig.patch.set_facecolor(BG_FIGURE)
    axes = ax_list if ax_list is not None else fig.get_axes()
    for ax in axes:
        ax.set_facecolor(BG_AXES)
        ax.tick_params(colors=TEXT_DIM, labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.7)
        ax.xaxis.label.set_color(TEXT)
        ax.yaxis.label.set_color(TEXT)
        ax.title.set_color(ACCENT_WHITE)
    return fig


def new_dark_figure(figsize=(6, 4), dpi=100):
    fig = plt.Figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111)
    apply_dark_theme(fig, [ax])
    fig.tight_layout()
    return fig, ax
