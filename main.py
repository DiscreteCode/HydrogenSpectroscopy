#!/usr/bin/env python3
"""
Hydrogen Quantum Spectroscopy -- application entry point.

Double-click target once packaged with PyInstaller (a later checkpoint);
for now, run directly with:

    python3 main.py

The user never needs to touch the physics/spectroscopy code once this
launches -- everything is driven through the GUI.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

# Ensure the project root is importable regardless of the working
# directory this script is launched from (matters once packaged).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.paths import resource_path  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

STYLE_PATH = resource_path("app", "resources", "style.qss")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Hydrogen Quantum Spectroscopy")
    app.setOrganizationName("Physics of Semiconductor Devices Project")

    if STYLE_PATH.exists():
        app.setStyleSheet(STYLE_PATH.read_text(encoding="utf-8"))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
