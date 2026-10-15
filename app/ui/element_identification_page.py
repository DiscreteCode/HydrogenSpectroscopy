"""
app.ui.element_identification_page
======================================

Brief section 13: a page over ``spectroscopy.element_database``.
Hydrogen is the only element with a live quantum-mechanical engine in
this application -- its lines shown here are computed on the spot via
``physics.spectral_series.get_series_transitions``, exactly like every
other page. The other catalog entries (He, Na, Ca, Fe) are clearly
labeled reference-only lookup data, never presented as calculated, and
never blended into the same table row as a computed hydrogen value.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.widgets.common import card_frame, page_header, section_header
from physics.spectral_series import get_series_transitions
from spectroscopy.element_database import ELEMENT_DATABASE, LineSource, list_elements


class ElementIdentificationPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "Element Identification",
            "This application quantum-mechanically calculates hydrogen's spectral lines. "
            "Other elements are listed only as reference lookup data, to show how the "
            "matching architecture generalizes -- they are never computed here.",
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        # --- Left: element list ---
        list_card = card_frame()
        list_card.setMaximumWidth(260)
        list_layout = QVBoxLayout(list_card)
        list_layout.addWidget(section_header("Elements"))
        self.element_list = QListWidget()
        for symbol in list_elements():
            entry = ELEMENT_DATABASE[symbol]
            item = QListWidgetItem(f"{entry.symbol}  —  {entry.name}")
            item.setData(Qt.UserRole, symbol)
            self.element_list.addItem(item)
        self.element_list.currentItemChanged.connect(self._on_selection_changed)
        list_layout.addWidget(self.element_list)
        body.addWidget(list_card)

        # --- Right: detail panel ---
        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        body.addLayout(right_col, stretch=1)

        header_card = card_frame()
        header_layout = QVBoxLayout(header_card)
        self.name_label = QLabel("Select an element")
        self.name_label.setStyleSheet("color: #f2f5fb; font-size: 18px; font-weight: 700;")
        header_layout.addWidget(self.name_label)

        self.badge_label = QLabel("")
        self.badge_label.setStyleSheet(
            "font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 10px; "
            "max-width: 220px;"
        )
        header_layout.addWidget(self.badge_label, alignment=Qt.AlignLeft)

        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        self.note_label.setStyleSheet("color: #97a3ba; font-size: 11.5px; padding-top: 6px;")
        header_layout.addWidget(self.note_label)
        right_col.addWidget(header_card)

        table_card = card_frame()
        table_layout = QVBoxLayout(table_card)
        table_layout.addWidget(section_header("Spectral Lines"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Line", "Vacuum (nm)", "Air (nm)", "Source"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.table)
        right_col.addWidget(table_card, stretch=1)

        if self.element_list.count():
            self.element_list.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem, _previous):
        if current is None:
            return
        symbol = current.data(Qt.UserRole)
        entry = ELEMENT_DATABASE[symbol]
        self.name_label.setText(f"{entry.name} ({entry.symbol})")
        self.note_label.setText(entry.note)

        if entry.source == LineSource.QUANTUM_CALCULATED:
            self.badge_label.setText("✓ AVAILABLE — Computed Live")
            self.badge_label.setStyleSheet(
                "background-color: #12331f; color: #39d98a; border: 1px solid #39d98a; "
                "font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 10px;"
            )
            self._populate_hydrogen_table()
        else:
            self.badge_label.setText("REFERENCE ONLY — Not Calculated")
            self.badge_label.setStyleSheet(
                "background-color: #332c12; color: #e8c04f; border: 1px solid #e8c04f; "
                "font-size: 11.5px; font-weight: 700; padding: 3px 10px; border-radius: 10px;"
            )
            self._populate_reference_table(entry)

    def _populate_hydrogen_table(self):
        transitions = get_series_transitions("Balmer", 7)
        self.table.setRowCount(len(transitions))
        for row, tr in enumerate(transitions):
            self.table.setItem(row, 0, QTableWidgetItem(f"{tr.label}  ({tr.series})"))
            self.table.setItem(row, 1, QTableWidgetItem(f"{tr.wavelength_nm:.2f}"))
            air = f"{tr.wavelength_air_nm:.2f}" if tr.wavelength_air_nm is not None else "n/a"
            self.table.setItem(row, 2, QTableWidgetItem(air))
            self.table.setItem(row, 3, QTableWidgetItem("Quantum calculated"))

    def _populate_reference_table(self, entry):
        lines = entry.reference_lines
        self.table.setRowCount(len(lines))
        for row, line in enumerate(lines):
            self.table.setItem(row, 0, QTableWidgetItem(line.label))
            self.table.setItem(row, 1, QTableWidgetItem("—"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{line.wavelength_air_nm:.3f}"))
            self.table.setItem(row, 3, QTableWidgetItem("Reference database"))
