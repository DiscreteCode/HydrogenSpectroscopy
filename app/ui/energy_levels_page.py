"""
app.ui.energy_levels_page
============================

Combines the Quantum Energy Level Module (brief section 5) and the
Transition Explorer (brief section 6) into one page: pick n_initial /
n_final (or a named series), see the energy-level diagram highlight
the transition, calculate delta_E / frequency / wavelength, watch a
simple electron-drop + photon-emission animation, and optionally add
the transition to the Spectrum Simulator's working set.

Combining these two brief sections into one page (rather than two
separate ones) is a deliberate simplicity choice: they share the same
n_i/n_f state and the same diagram, and splitting them would mean
either duplicating that state or wiring cross-page signals for no
real benefit to the user.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from physics.hydrogen import MAX_SUPPORTED_N
from physics.spectral_series import list_series_names
from physics.transitions import Transition, compute_emission_transition
from app.controllers.app_state import AppState
from app.widgets.common import StatCard, card_frame, page_header, section_header
from app.widgets.mpl_canvas import MplCanvas
from visualization.energy_levels import plot_energy_levels

DIAGRAM_N_MAX_LIMIT = 12  # beyond this the diagram gets too crowded to read


class EnergyLevelsPage(QWidget):
    def __init__(self, app_state: AppState, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.current_transition: Transition | None = None
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animation_tick)
        self._anim_progress = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "Quantum Energy Levels & Transition Explorer",
            "Select an electron transition to see the quantized energy levels, the photon "
            "it emits, and the resulting spectral line wavelength — all computed live from "
            "E_n = −13.6 eV / n².",
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        # --- Left: diagram ---
        diagram_card = card_frame()
        diagram_layout = QVBoxLayout(diagram_card)
        diagram_layout.setContentsMargins(10, 10, 10, 10)

        diagram_controls = QHBoxLayout()
        diagram_controls.addWidget(QLabel("Max n shown:"))
        self.n_max_spin = QSpinBox()
        self.n_max_spin.setRange(3, DIAGRAM_N_MAX_LIMIT)
        self.n_max_spin.setValue(6)
        self.n_max_spin.valueChanged.connect(self._on_n_max_changed)
        diagram_controls.addWidget(self.n_max_spin)
        diagram_controls.addStretch(1)
        export_btn = QPushButton("Export PNG")
        export_btn.clicked.connect(self._export_diagram)
        diagram_controls.addWidget(export_btn)
        diagram_layout.addLayout(diagram_controls)

        self.canvas = MplCanvas(figsize=(6.5, 5.5))
        diagram_layout.addWidget(self.canvas, stretch=1)
        body.addWidget(diagram_card, stretch=3)

        # --- Right: controls + results ---
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        body.addLayout(right_col, stretch=2)

        controls_card = card_frame()
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.addWidget(section_header("Select Transition"))

        grid = QGridLayout()
        grid.addWidget(QLabel("Series (optional):"), 0, 0)
        self.series_combo = QComboBox()
        self.series_combo.addItem("Custom")
        self.series_combo.addItems(list_series_names())
        self.series_combo.currentTextChanged.connect(self._on_series_changed)
        grid.addWidget(self.series_combo, 0, 1)

        grid.addWidget(QLabel("Initial level  n\u1d62:"), 1, 0)
        self.n_initial_spin = QSpinBox()
        self.n_initial_spin.setRange(2, MAX_SUPPORTED_N)
        self.n_initial_spin.setValue(3)
        grid.addWidget(self.n_initial_spin, 1, 1)

        grid.addWidget(QLabel("Final level  n\u0192:"), 2, 0)
        self.n_final_spin = QSpinBox()
        self.n_final_spin.setRange(1, MAX_SUPPORTED_N - 1)
        self.n_final_spin.setValue(2)
        self.n_final_spin.valueChanged.connect(self._sync_n_initial_minimum)
        grid.addWidget(self.n_final_spin, 2, 1)
        controls_layout.addLayout(grid)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e85f5f; font-size: 11px;")
        self.error_label.setWordWrap(True)
        controls_layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        self.calc_btn = QPushButton("Calculate")
        self.calc_btn.setObjectName("primaryButton")
        self.calc_btn.clicked.connect(self.calculate)
        btn_row.addWidget(self.calc_btn)

        self.animate_btn = QPushButton("Animate")
        self.animate_btn.setObjectName("accentButton")
        self.animate_btn.clicked.connect(self.animate)
        self.animate_btn.setEnabled(False)
        btn_row.addWidget(self.animate_btn)
        controls_layout.addLayout(btn_row)

        self.add_btn = QPushButton("+ Add to Spectrum Simulator")
        self.add_btn.clicked.connect(self._add_to_spectrum)
        self.add_btn.setEnabled(False)
        controls_layout.addWidget(self.add_btn)

        right_col.addWidget(controls_card)

        # --- Results cards ---
        results_card = card_frame()
        results_layout = QVBoxLayout(results_card)
        results_layout.addWidget(section_header("Result"))

        cards_grid = QGridLayout()
        cards_grid.setSpacing(8)
        self.card_delta_e = StatCard("Energy difference (ΔE)")
        self.card_wavelength_vac = StatCard("Wavelength (vacuum)", accent=True)
        self.card_wavelength_air = StatCard("Wavelength (standard air)", accent=True)
        self.card_frequency = StatCard("Photon frequency")
        self.card_series = StatCard("Spectral series")
        self.card_region = StatCard("Spectral region")
        cards_grid.addWidget(self.card_delta_e, 0, 0)
        cards_grid.addWidget(self.card_frequency, 0, 1)
        cards_grid.addWidget(self.card_wavelength_vac, 1, 0)
        cards_grid.addWidget(self.card_wavelength_air, 1, 1)
        cards_grid.addWidget(self.card_series, 2, 0)
        cards_grid.addWidget(self.card_region, 2, 1)
        results_layout.addLayout(cards_grid)

        note = QLabel(
            "Photon frequency and energy always follow the fundamental vacuum "
            "wavelength; the standard-air value is what a lab spectrometer or "
            "most textbooks report for the same photon."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #7c869c; font-size: 10.5px; padding-top: 4px;")
        results_layout.addWidget(note)

        right_col.addWidget(results_card)
        right_col.addStretch(1)

        self._sync_n_initial_minimum()
        self._redraw_diagram()

    # -- interaction handlers -------------------------------------------------

    def _sync_n_initial_minimum(self):
        n_f = self.n_final_spin.value()
        self.n_initial_spin.setMinimum(n_f + 1)
        if self.n_initial_spin.value() <= n_f:
            self.n_initial_spin.setValue(n_f + 1)

    def _on_series_changed(self, name: str):
        from physics.spectral_series import get_series_final_n
        if name == "Custom":
            return
        n_f = get_series_final_n(name)
        self.n_final_spin.setValue(n_f)
        self._sync_n_initial_minimum()
        if self.n_initial_spin.value() <= n_f:
            self.n_initial_spin.setValue(n_f + 1)

    def _on_n_max_changed(self):
        self._redraw_diagram()

    def _redraw_diagram(self):
        n_max = max(self.n_max_spin.value(), self.n_final_spin.value(), self.n_initial_spin.value())
        n_max = min(n_max, DIAGRAM_N_MAX_LIMIT)
        plot_energy_levels(self.canvas.fig, self.canvas.ax, n_max, transition=self.current_transition)
        self.canvas.redraw()

    def calculate(self):
        self.error_label.setText("")
        n_i = self.n_initial_spin.value()
        n_f = self.n_final_spin.value()
        try:
            transition = compute_emission_transition(n_i, n_f)
        except ValueError as exc:
            self.error_label.setText(str(exc))
            self.animate_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            return

        self.current_transition = transition
        self.app_state.set_current_transition(transition)
        self._update_result_cards(transition)
        self._redraw_diagram()
        self.animate_btn.setEnabled(True)
        self.add_btn.setEnabled(True)

    def _update_result_cards(self, tr: Transition):
        self.card_delta_e.set_value(f"{tr.delta_e_ev:.4f} eV")
        self.card_wavelength_vac.set_value(f"{tr.wavelength_nm:.2f} nm")
        air_text = f"{tr.wavelength_air_nm:.1f} nm" if tr.wavelength_air_nm is not None else "n/a (outside optical range)"
        self.card_wavelength_air.set_value(air_text)
        self.card_frequency.set_value(f"{tr.frequency_hz:.3e} Hz")
        self.card_series.set_value(tr.series or "—")
        self.card_region.set_value(tr.region)

    def animate(self):
        if self.current_transition is None:
            return
        self.animate_btn.setEnabled(False)
        self.calc_btn.setEnabled(False)
        self._anim_progress = 0.0
        self._anim_timer.start(30)

    def _animation_tick(self):
        self._anim_progress += 0.045
        if self._anim_progress >= 1.0:
            self._anim_progress = 1.0
            self._anim_timer.stop()
            self.animate_btn.setEnabled(True)
            self.calc_btn.setEnabled(True)
        plot_energy_levels(
            self.canvas.fig, self.canvas.ax,
            max(self.n_max_spin.value(), self.current_transition.n_initial),
            transition=self.current_transition,
            electron_position=self._anim_progress,
        )
        self.canvas.redraw()

    def _add_to_spectrum(self):
        if self.current_transition is None:
            return
        self.app_state.add_transition_to_spectrum(self.current_transition)
        QMessageBox.information(
            self, "Added",
            f"{self.current_transition.label} added to the Spectrum Simulator's working set.\n"
            "Switch to the Spectrum Simulator page and check 'Include added transitions'.",
        )

    def _export_diagram(self):
        self.canvas.save_png_dialog(self, default_name="hydrogen_energy_levels.png")
