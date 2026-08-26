"""
app.ui.dashboard_page
========================

The landing screen (brief section 4): a visual introduction to the
pipeline this whole app demonstrates, live stats about the
last-calculated transition, and quick navigation into the other pages.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.controllers.app_state import AppState
from app.widgets.common import StatCard, card_frame, page_header, section_header
from physics.transitions import Transition

PIPELINE_STEPS = [
    "Hydrogen atom", "Quantized energy levels", "Allowed transitions",
    "Energy gap ΔE", "Photon E = hν", "Wavelength λ = hc/ΔE",
    "Spectral lines", "Stellar spectrum match",
]


class DashboardPage(QWidget):
    def __init__(self, app_state: AppState, navigate_callback, parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.navigate = navigate_callback
        app_state.transition_changed.connect(self._on_transition_changed)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        root.addWidget(page_header(
            "Unveiling Stellar Composition Through Quantum Simulations of Hydrogen Spectral Lines",
            "A hydrogen atom's quantized energy levels produce a precise set of photon "
            "wavelengths. Those wavelengths are a fingerprint — find them in starlight, "
            "and you've identified hydrogen without ever touching the star.",
        ))

        # --- Pipeline strip ---
        pipeline_card = card_frame()
        pipeline_layout = QVBoxLayout(pipeline_card)
        pipeline_layout.addWidget(section_header("The Pipeline"))
        chip_row = QHBoxLayout()
        chip_row.setSpacing(4)
        for i, step in enumerate(PIPELINE_STEPS):
            chip = QLabel(step)
            chip.setStyleSheet(
                "background-color: #131a2b; color: #9d7ce8; border-radius: 10px; "
                "padding: 5px 9px; font-size: 10.5px;"
            )
            chip_row.addWidget(chip)
            if i < len(PIPELINE_STEPS) - 1:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #4a5578; font-size: 12px;")
                chip_row.addWidget(arrow)
        chip_row.addStretch(1)
        pipeline_layout.addLayout(chip_row)
        root.addWidget(pipeline_card)

        # --- Live stat cards ---
        stats_card = card_frame()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.addWidget(section_header("Current Selection"))
        stats_grid = QGridLayout()
        self.card_transition = StatCard("Transition", "none calculated yet")
        self.card_wavelength = StatCard("Wavelength (air)", "--", accent=True)
        self.card_series = StatCard("Series", "--")
        self.card_energy = StatCard("Energy ΔE", "--")
        stats_grid.addWidget(self.card_transition, 0, 0)
        stats_grid.addWidget(self.card_wavelength, 0, 1)
        stats_grid.addWidget(self.card_series, 0, 2)
        stats_grid.addWidget(self.card_energy, 0, 3)
        stats_layout.addLayout(stats_grid)
        root.addWidget(stats_card)

        # --- Navigation cards ---
        root.addWidget(section_header("Explore"))
        nav_grid = QGridLayout()
        nav_grid.setSpacing(12)
        nav_items = [
            ("Energy Levels & Transitions", "Pick a quantum transition and watch the photon it emits.", "energy_levels"),
            ("Spectrum Simulator", "Generate emission or absorption hydrogen spectra.", "spectrum_simulator"),
            ("Stellar Analysis", "Simulate a star and detect hydrogen in its spectrum.", "stellar_analysis"),
            ("Theory / Learn", "The physics behind every number this app computes.", "theory"),
        ]
        for i, (title, desc, key) in enumerate(nav_items):
            nav_grid.addWidget(self._make_nav_card(title, desc, key), i // 2, i % 2)
        root.addLayout(nav_grid)
        root.addStretch(1)

    def _make_nav_card(self, title: str, desc: str, page_key: str) -> QWidget:
        card = card_frame()
        card.setMinimumHeight(90)
        layout = QVBoxLayout(card)
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #f2f5fb; font-size: 14px; font-weight: 600;")
        layout.addWidget(title_label)
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #7c869c; font-size: 11.5px;")
        layout.addWidget(desc_label)
        btn = QPushButton("Open →")
        btn.setMaximumWidth(90)
        btn.clicked.connect(lambda: self.navigate(page_key))
        layout.addWidget(btn, alignment=Qt.AlignRight)
        return card

    def _on_transition_changed(self, transition: Transition):
        self.card_transition.set_value(transition.label)
        air = f"{transition.wavelength_air_nm:.1f} nm" if transition.wavelength_air_nm is not None else f"{transition.wavelength_nm:.1f} nm (vac.)"
        self.card_wavelength.set_value(air)
        self.card_series.set_value(transition.series or "—")
        self.card_energy.set_value(f"{transition.delta_e_ev:.3f} eV")
