"""
app.ui.stellar_analysis_page
===============================

The flagship demonstration page: simulate or load a stellar spectrum, select
one of five elements, and compare the observed line pattern with its references.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.paths import resource_path
from app.widgets.common import card_frame, page_header, section_header
from app.widgets.mpl_canvas import MplCanvas
from physics.doppler import doppler_result
from physics.transitions import compute_emission_transition
from spectroscopy.analyzer import HydrogenDetectionSummary, StellarSpectrum
from spectroscopy.composition import generate_composition_spectrum
from spectroscopy.element_database import ELEMENT_DATABASE, LineSource
from spectroscopy.element_analyzer import match_element_lines
from spectroscopy.io_utils import (
    SpectrumImportError,
    export_detection_report_txt,
    export_detection_results_csv,
    load_spectrum_csv,
)
from spectroscopy.spectrum import build_wavelength_grid
from visualization.stellar_plot import plot_stellar_analysis

DATA_DIR = resource_path("data", "sample_spectra")


class StellarAnalysisPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_star: StellarSpectrum | None = None
        self.current_summary: HydrogenDetectionSummary | None = None
        self.current_star_label = "Synthetic Star"
        self._pipeline_timer = QTimer(self)
        self._pipeline_timer.timeout.connect(self._pipeline_tick)
        self._pipeline_stage = 0
        self._pipeline_stages = [
            "Observed spectrum acquired…",
            "Searching for absorption features…",
            "Comparing against selected-element line references…",
            "Finalizing verdict…",
        ]

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "Stellar Spectrum Analysis",
            "Simulate or load a spectrum, then test for hydrogen, helium, sodium, calcium, or iron "
            "using quantum-calculated hydrogen lines and clearly labeled reference lines for other elements.",
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        # --- Left: controls ---
        controls_card = card_frame()
        controls_card.setMaximumWidth(340)
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.addWidget(section_header("Simulate a Star"))

        self.temp_label = QLabel("Temperature: 9000 K")
        controls_layout.addWidget(self.temp_label)
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(3000, 30000)
        self.temp_slider.setSingleStep(100)
        self.temp_slider.setValue(9000)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"Temperature: {v} K"))
        controls_layout.addWidget(self.temp_slider)

        self.vel_label = QLabel("Radial velocity: 0 km/s")
        controls_layout.addWidget(self.vel_label)
        self.vel_slider = QSlider(Qt.Horizontal)
        self.vel_slider.setRange(-400, 400)
        self.vel_slider.setValue(0)
        self.vel_slider.valueChanged.connect(self._on_velocity_changed)
        controls_layout.addWidget(self.vel_slider)

        # H-alpha (3->2) rest wavelength, computed once from the physics
        # engine, used only to give a live, concrete example of the
        # Doppler shift the velocity slider will apply to the whole
        # simulated spectrum -- the shift itself always comes from
        # physics.doppler, never re-derived here.
        self._h_alpha_rest_nm = compute_emission_transition(3, 2).wavelength_air_nm
        self.doppler_readout = QLabel("")
        self.doppler_readout.setWordWrap(True)
        self.doppler_readout.setStyleSheet("color: #4fd1e8; font-size: 10.5px;")
        controls_layout.addWidget(self.doppler_readout)
        self._on_velocity_changed(self.vel_slider.value())

        self.noise_label = QLabel("Noise: 2%")
        controls_layout.addWidget(self.noise_label)
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(0, 100)
        self.noise_slider.setValue(20)
        self.noise_slider.valueChanged.connect(lambda v: self.noise_label.setText(f"Noise: {v / 10:.1f}%"))
        controls_layout.addWidget(self.noise_slider)

        self.strength_label = QLabel("Hydrogen contribution: 70%")
        controls_layout.addWidget(self.strength_label)
        self.strength_slider = QSlider(Qt.Horizontal)
        self.strength_slider.setRange(0, 100)
        self.strength_slider.setValue(70)
        self.strength_slider.valueChanged.connect(lambda v: self.strength_label.setText(f"Hydrogen contribution: {v}%"))
        controls_layout.addWidget(self.strength_slider)

        gen_btn = QPushButton("Generate Synthetic Stellar Spectrum")
        gen_btn.setObjectName("primaryButton")
        gen_btn.clicked.connect(self._generate_synthetic)
        controls_layout.addWidget(gen_btn)

        controls_layout.addWidget(section_header("Or Use Real/Sample Data"))
        sample_row = QHBoxLayout()
        self.sample_combo = QComboBox()
        self.sample_combo.addItem("(choose a sample)")
        if DATA_DIR.exists():
            for f in sorted(DATA_DIR.glob("*.csv")):
                self.sample_combo.addItem(f.name)
        sample_row.addWidget(self.sample_combo)
        load_sample_btn = QPushButton("Load")
        load_sample_btn.clicked.connect(self._load_sample)
        sample_row.addWidget(load_sample_btn)
        controls_layout.addLayout(sample_row)

        load_csv_btn = QPushButton("Load Spectrum from CSV / TXT…")
        load_csv_btn.clicked.connect(self._load_csv)
        controls_layout.addWidget(load_csv_btn)

        controls_layout.addWidget(section_header("Identify an Element"))
        self.element_combo = QComboBox()
        for symbol, entry in ELEMENT_DATABASE.items():
            source_label = "quantum model" if entry.source == LineSource.QUANTUM_CALCULATED else "reference lines"
            self.element_combo.addItem(f"{entry.name} ({symbol}) · {source_label}", symbol)
        self.element_combo.setCurrentIndex(0)
        controls_layout.addWidget(self.element_combo)

        controls_layout.addWidget(section_header("Analyze"))
        self.analyze_btn = QPushButton("Run Element Detection")
        self.analyze_btn.setObjectName("accentButton")
        self.analyze_btn.clicked.connect(self._run_analysis)
        self.analyze_btn.setEnabled(False)
        controls_layout.addWidget(self.analyze_btn)

        self.pipeline_status = QLabel("")
        self.pipeline_status.setWordWrap(True)
        self.pipeline_status.setStyleSheet("color: #4fd1e8; font-size: 11px;")
        controls_layout.addWidget(self.pipeline_status)

        controls_layout.addStretch(1)
        body.addWidget(controls_card)

        # --- Right: plot + verdict + table ---
        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        body.addLayout(right_col, stretch=1)

        plot_card = card_frame()
        plot_layout = QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(10, 10, 10, 10)
        self.canvas = MplCanvas(figsize=(8, 4.2))
        plot_layout.addWidget(self.canvas)
        right_col.addWidget(plot_card, stretch=1)

        self.verdict_label = QLabel("Generate or load a spectrum, then run detection.")
        self.verdict_label.setWordWrap(True)
        self.verdict_label.setAlignment(Qt.AlignCenter)
        self.verdict_label.setStyleSheet(
            "font-size: 16px; font-weight: 700; padding: 10px; border-radius: 8px; "
            "background-color: #131a2b; color: #97a3ba;"
        )
        right_col.addWidget(self.verdict_label)

        table_card = card_frame()
        table_layout = QVBoxLayout(table_card)
        header_row = QHBoxLayout()
        header_row.addWidget(section_header("Detection Report"))
        header_row.addStretch(1)
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(self._export_csv)
        header_row.addWidget(export_csv_btn)
        export_txt_btn = QPushButton("Export Report (TXT)")
        export_txt_btn.clicked.connect(self._export_txt)
        header_row.addWidget(export_txt_btn)
        table_layout.addLayout(header_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Element / line", "Expected (nm)", "Observed (nm)", "Δ (nm)", "Match"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.table)
        right_col.addWidget(table_card)

    def _on_velocity_changed(self, v: int):
        self.vel_label.setText(f"Radial velocity: {v:+d} km/s")
        result = doppler_result(self._h_alpha_rest_nm, float(v))
        direction = "redshift" if v > 0 else ("blueshift" if v < 0 else "no shift")
        self.doppler_readout.setText(
            f"H\u03b1 rest {result.rest_wavelength_nm:.2f} nm \u2192 observed "
            f"{result.observed_wavelength_nm:.2f} nm ({direction})"
        )

    # -- data acquisition -------------------------------------------------

    def _generate_synthetic(self):
        grid = build_wavelength_grid(380.0, 700.0, 8000)
        # Generate a combined spectrum so each selectable element has lines to test.
        # The H control is a relative demo input, not an abundance measurement.
        composition = generate_composition_spectrum(
            grid,
            abundances={"H": float(self.strength_slider.value()), "He": 25, "Na": 2, "Ca": 1, "Fe": 2},
            temperature_k=float(self.temp_slider.value()),
            radial_velocity_kms=float(self.vel_slider.value()),
            noise_level=self.noise_slider.value() / 1000.0,
            random_seed=7,
        )
        star = StellarSpectrum(
            wavelength_nm=composition.wavelength_nm,
            intensity=composition.intensity,
            continuum=composition.continuum,
            temperature_k=float(self.temp_slider.value()),
            radial_velocity_kms=float(self.vel_slider.value()),
            noise_level=self.noise_slider.value() / 1000.0,
            h_line_strength=self.strength_slider.value() / 100.0,
            series_used="Balmer + reference elements",
        )
        self.current_star = star
        self.current_star_label = f"Synthetic Star (T={star.temperature_k:.0f} K)"
        self.current_summary = None
        self.analyze_btn.setEnabled(True)
        plot_stellar_analysis(self.canvas.fig, self.canvas.ax, star, None)
        self.canvas.redraw()
        self._reset_verdict()

    def _load_sample(self):
        name = self.sample_combo.currentText()
        if not name or name.startswith("("):
            QMessageBox.information(self, "Choose a Sample", "Pick a sample spectrum from the list first.")
            return
        self._load_csv_path(DATA_DIR / name)

    def _load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Stellar Spectrum", "", "Spectra (*.csv *.txt *.tsv);;All Files (*)")
        if not path:
            return
        self._load_csv_path(Path(path))

    def _load_csv_path(self, path: Path):
        try:
            wl, intensity, header = load_spectrum_csv(path)
        except SpectrumImportError as exc:
            QMessageBox.warning(self, "Could Not Load Spectrum", str(exc))
            return

        # Wrap the imported curve in a StellarSpectrum so downstream
        # plotting/analysis code has one consistent type to work with.
        # We don't know the true continuum for real/imported data, so
        # we estimate it for display purposes only (see peak_detection
        # .estimate_local_continuum) -- matching itself uses the
        # spectrum's own intensity, not this estimate.
        from spectroscopy.peak_detection import estimate_local_continuum
        continuum = estimate_local_continuum(wl, intensity)

        self.current_star = StellarSpectrum(
            wavelength_nm=wl, intensity=intensity, continuum=continuum,
            temperature_k=float("nan"), radial_velocity_kms=0.0,
            noise_level=0.0, h_line_strength=0.0, series_used="Balmer",
        )
        self.current_star_label = f"Loaded: {path.name}"
        self.current_summary = None
        self.analyze_btn.setEnabled(True)
        plot_stellar_analysis(self.canvas.fig, self.canvas.ax, self.current_star, None)
        self.canvas.redraw()
        self._reset_verdict()

    # -- analysis -------------------------------------------------

    def _run_analysis(self):
        if self.current_star is None:
            return
        self.analyze_btn.setEnabled(False)
        self._pipeline_stage = 0
        self.pipeline_status.setText(self._pipeline_stages[0])
        self._pipeline_timer.start(280)

    def _pipeline_tick(self):
        self._pipeline_stage += 1
        if self._pipeline_stage >= len(self._pipeline_stages):
            self._pipeline_timer.stop()
            self._finish_analysis()
            return
        self.pipeline_status.setText(self._pipeline_stages[self._pipeline_stage])

    def _finish_analysis(self):
        star = self.current_star
        continuum_for_matching = star.continuum if not _all_nan(star.continuum) else 1.0
        symbol = self.element_combo.currentData()
        summary = match_element_lines(
            star.wavelength_nm, star.intensity, symbol,
            continuum_level=continuum_for_matching,
        )
        self.current_summary = summary
        self.analyze_btn.setEnabled(True)
        self.pipeline_status.setText(f"Analysis complete · {self.element_combo.currentText()}")

        plot_stellar_analysis(self.canvas.fig, self.canvas.ax, star, summary)
        self.canvas.redraw()
        self._populate_table(summary)
        self._show_verdict(summary)

    def _populate_table(self, summary: HydrogenDetectionSummary):
        self.table.setRowCount(len(summary.results))
        for row, r in enumerate(summary.results):
            self.table.setItem(row, 0, QTableWidgetItem(r.label))
            self.table.setItem(row, 1, QTableWidgetItem(f"{r.expected_air_nm:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{r.observed_nm:.2f}" if r.observed_nm is not None else "—"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{r.difference_nm:+.2f}" if r.difference_nm is not None else "—"))
            match_item = QTableWidgetItem("✓ YES" if r.matched else "✗ NO")
            match_item.setForeground(Qt.green if r.matched else Qt.red)
            self.table.setItem(row, 4, match_item)

    def _show_verdict(self, summary: HydrogenDetectionSummary):
        if summary.detected:
            style = "background-color: #12331f; color: #39d98a; border: 1px solid #39d98a;"
        elif summary.num_matched == 1:
            style = "background-color: #332c12; color: #e8c04f; border: 1px solid #e8c04f;"
        else:
            style = "background-color: #331515; color: #e85f5f; border: 1px solid #e85f5f;"
        self.verdict_label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; padding: 10px; border-radius: 8px; {style}"
        )
        self.verdict_label.setText(summary.message)

    def _reset_verdict(self):
        self.verdict_label.setText("Spectrum ready. Select an element and click 'Run Element Detection'.")
        self.verdict_label.setStyleSheet(
            "font-size: 15px; font-weight: 700; padding: 10px; border-radius: 8px; "
            "background-color: #131a2b; color: #97a3ba;"
        )
        self.table.setRowCount(0)
        self.pipeline_status.setText("")

    # -- export -------------------------------------------------

    def _export_csv(self):
        if self.current_summary is None:
            QMessageBox.information(self, "Nothing to Export", "Run detection first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Detection Results", "detection_results.csv", "CSV (*.csv)")
        if not path:
            return
        export_detection_results_csv(path, self.current_summary.results)
        QMessageBox.information(self, "Export Complete", f"Results saved to:\n{path}")

    def _export_txt(self):
        if self.current_summary is None:
            QMessageBox.information(self, "Nothing to Export", "Run detection first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Detection Report", "detection_report.txt", "Text (*.txt)")
        if not path:
            return
        export_detection_report_txt(path, self.current_summary, star_label=self.current_star_label)
        QMessageBox.information(self, "Export Complete", f"Report saved to:\n{path}")


def _all_nan(arr) -> bool:
    import numpy as np
    return bool(np.all(np.isnan(arr)))
