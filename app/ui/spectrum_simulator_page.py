"""
app.ui.spectrum_simulator_page
=================================

The Spectrum Simulator (brief sections 7-9): pick a spectral series (or
use transitions added from the Explorer page), generate a synthetic
emission or absorption spectrum with configurable Gaussian line width
and resolution, and export the result.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from physics.hydrogen import MAX_SUPPORTED_N
from physics.spectral_series import get_series_final_n, get_series_transitions, list_series_names
from app.controllers.app_state import AppState
from app.widgets.common import card_frame, page_header, section_header
from app.widgets.mpl_canvas import MplCanvas
from spectroscopy.spectrum import (
    Spectrum,
    SpectrumMode,
    build_wavelength_grid,
    generate_spectrum,
)
from spectroscopy.io_utils import export_spectrum_csv
from visualization.spectrum_plot import plot_spectrum

SERIES_DEFAULT_RANGES_NM = {
    "Lyman": (90.0, 130.0),
    "Balmer": (370.0, 700.0),
    "Paschen": (800.0, 1950.0),
    "Brackett": (1400.0, 4200.0),
    "Pfund": (2200.0, 7500.0),
}


class SpectrumSimulatorPage(QWidget):
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.current_spectrum: Spectrum | None = None
        self._reveal_timer = QTimer(self)
        self._reveal_timer.timeout.connect(self._reveal_tick)
        self._reveal_progress = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "Spectrum Simulator",
            "Build a synthetic hydrogen emission or absorption spectrum from real computed "
            "transition wavelengths, with a configurable Gaussian line profile.",
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        controls_card = card_frame()
        controls_card.setMaximumWidth(340)
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.addWidget(section_header("Configuration"))

        grid = QGridLayout()
        row = 0
        grid.addWidget(QLabel("Series:"), row, 0)
        self.series_combo = QComboBox()
        self.series_combo.addItems(list_series_names())
        self.series_combo.setCurrentText("Balmer")
        self.series_combo.currentTextChanged.connect(self._on_series_changed)
        grid.addWidget(self.series_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Max n\u1d62:"), row, 0)
        self.n_i_max_spin = QSpinBox()
        self.n_i_max_spin.setRange(3, 15)
        self.n_i_max_spin.setValue(6)
        grid.addWidget(self.n_i_max_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Mode:"), row, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Emission", "Absorption"])
        grid.addWidget(self.mode_combo, row, 1)
        row += 1

        grid.addWidget(QLabel("Range min (nm):"), row, 0)
        self.range_min_spin = QDoubleSpinBox()
        self.range_min_spin.setRange(50.0, 9000.0)
        self.range_min_spin.setValue(370.0)
        grid.addWidget(self.range_min_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Range max (nm):"), row, 0)
        self.range_max_spin = QDoubleSpinBox()
        self.range_max_spin.setRange(60.0, 10000.0)
        self.range_max_spin.setValue(700.0)
        grid.addWidget(self.range_max_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Resolution (points):"), row, 0)
        self.resolution_spin = QSpinBox()
        self.resolution_spin.setRange(200, 20000)
        self.resolution_spin.setSingleStep(200)
        self.resolution_spin.setValue(4000)
        grid.addWidget(self.resolution_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Line width σ (nm):"), row, 0)
        self.sigma_spin = QDoubleSpinBox()
        self.sigma_spin.setRange(0.05, 20.0)
        self.sigma_spin.setSingleStep(0.1)
        self.sigma_spin.setValue(0.8)
        grid.addWidget(self.sigma_spin, row, 1)
        row += 1

        grid.addWidget(QLabel("Intensity scale:"), row, 0)
        self.intensity_spin = QDoubleSpinBox()
        self.intensity_spin.setRange(0.05, 5.0)
        self.intensity_spin.setSingleStep(0.1)
        self.intensity_spin.setValue(1.0)
        grid.addWidget(self.intensity_spin, row, 1)
        row += 1

        controls_layout.addLayout(grid)

        self.include_custom_check = QCheckBox("Include transitions added from Explorer")
        controls_layout.addWidget(self.include_custom_check)

        gen_btn = QPushButton("Generate Spectrum")
        gen_btn.setObjectName("primaryButton")
        gen_btn.clicked.connect(self.generate)
        controls_layout.addWidget(gen_btn)

        export_row = QHBoxLayout()
        export_png_btn = QPushButton("Export PNG")
        export_png_btn.clicked.connect(self._export_png)
        export_row.addWidget(export_png_btn)
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(self._export_csv)
        export_row.addWidget(export_csv_btn)
        controls_layout.addLayout(export_row)

        controls_layout.addStretch(1)
        body.addWidget(controls_card)

        plot_card = card_frame()
        plot_layout = QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(10, 10, 10, 10)
        self.canvas = MplCanvas(figsize=(8, 5.5))
        plot_layout.addWidget(self.canvas)
        body.addWidget(plot_card, stretch=1)

        self._on_series_changed(self.series_combo.currentText())

    def _on_series_changed(self, series_name: str):
        lo, hi = SERIES_DEFAULT_RANGES_NM.get(series_name, (370.0, 700.0))
        self.range_min_spin.setValue(lo)
        self.range_max_spin.setValue(hi)
        n_f = get_series_final_n(series_name)
        self.n_i_max_spin.setMinimum(n_f + 1)
        if self.n_i_max_spin.value() <= n_f:
            self.n_i_max_spin.setValue(n_f + 4)

    def generate(self):
        try:
            grid = build_wavelength_grid(
                self.range_min_spin.value(), self.range_max_spin.value(), self.resolution_spin.value()
            )
            transitions = get_series_transitions(self.series_combo.currentText(), self.n_i_max_spin.value())
            if self.include_custom_check.isChecked():
                transitions = list(transitions) + list(self.app_state.custom_transitions)

            mode = SpectrumMode.EMISSION if self.mode_combo.currentText() == "Emission" else SpectrumMode.ABSORPTION
            spectrum = generate_spectrum(
                transitions, mode, grid,
                sigma_nm=self.sigma_spin.value(),
                amplitude_scale=self.intensity_spin.value(),
                continuum=1.0,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot Generate Spectrum", str(exc))
            return

        self.current_spectrum = spectrum
        # Simple "lines appear sequentially" animation (brief section 16).
        self._reveal_progress = 0.0
        self._reveal_timer.start(60)

    def _reveal_tick(self):
        self._reveal_progress += 0.12
        if self._reveal_progress >= 1.0:
            self._reveal_progress = 1.0
            self._reveal_timer.stop()
        plot_spectrum(self.canvas.fig, self.canvas.ax, self.current_spectrum, reveal_frac=self._reveal_progress)
        self.canvas.redraw()

    def _export_png(self):
        if self.current_spectrum is None:
            QMessageBox.information(self, "Nothing to Export", "Generate a spectrum first.")
            return
        self.canvas.save_png_dialog(self, default_name="hydrogen_spectrum.png")

    def _export_csv(self):
        if self.current_spectrum is None:
            QMessageBox.information(self, "Nothing to Export", "Generate a spectrum first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Spectrum CSV", "hydrogen_spectrum.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            export_spectrum_csv(path, self.current_spectrum.wavelength_nm, self.current_spectrum.intensity)
            QMessageBox.information(self, "Export Complete", f"Spectrum saved to:\n{path}")
        except OSError as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))
