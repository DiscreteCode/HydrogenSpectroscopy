"""
app.widgets.common
=====================

A handful of tiny reusable widget builders shared across every page,
so the "card" look (brief section 14: "use cards, panels, tabs, clear
hierarchy") stays consistent without copy-pasting layout code
everywhere.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class StatCard(QFrame):
    """A small card showing a label + big value, e.g. 'WAVELENGTH  656.3 nm'."""

    def __init__(self, title: str, value: str = "--", accent: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("cardTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValueAccent" if accent else "statValue")
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


def page_header(title: str, subtitle: str = "") -> QWidget:
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 4)
    layout.setSpacing(0)

    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    layout.addWidget(title_label)

    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)

    return container


def section_header(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionHeader")
    return label


def card_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame
