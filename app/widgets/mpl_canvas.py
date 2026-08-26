"""
app.widgets.mpl_canvas
========================

Thin wrapper around matplotlib's Qt backend so every page embeds plots
the same way, with the same dark theme and a consistent
save-to-PNG action.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from PySide6.QtWidgets import QFileDialog, QMessageBox, QVBoxLayout, QWidget

from visualization.theme import BG_FIGURE, new_dark_figure


class MplCanvas(QWidget):
    """A QWidget containing one dark-themed matplotlib Figure/Axes,
    ready to be drawn into by visualization.* plotting functions."""

    def __init__(self, figsize=(6, 4), dpi=100, parent=None):
        super().__init__(parent)
        self.fig, self.ax = new_dark_figure(figsize=figsize, dpi=dpi)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setStyleSheet(f"background-color: {BG_FIGURE};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def redraw(self):
        self.canvas.draw_idle()

    def save_png_dialog(self, parent, default_name: str = "plot.png"):
        path, _ = QFileDialog.getSaveFileName(parent, "Export Plot as PNG", default_name, "PNG Image (*.png)")
        if not path:
            return
        try:
            self.fig.savefig(path, facecolor=self.fig.get_facecolor(), dpi=150)
            QMessageBox.information(parent, "Export Complete", f"Plot saved to:\n{path}")
        except OSError as exc:
            QMessageBox.warning(parent, "Export Failed", f"Could not save the plot:\n{exc}")
