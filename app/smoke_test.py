"""Headless self-test used to verify a PyInstaller build.

    HydrogenSpectroscopy.exe --smoke-test <result_file.txt>

The frozen app is windowed (no console), so the verdict is written to the
result file and reported through the exit code (0 = pass). It exercises the
same code paths a user reaches through the GUI: bundled resources, the main
window with every page, the composition simulation + blind analysis, and CSV
export.
"""
from __future__ import annotations

import csv
import io
import sys
import traceback
from pathlib import Path


def run(result_path: str) -> int:
    lines: list[str] = []
    ok = False
    try:
        from PySide6.QtWidgets import QApplication

        from app.paths import resource_path
        from app.ui.main_window import MainWindow
        from spectroscopy.composition_analysis import write_analysis_csv

        lines.append(f"frozen={getattr(sys, 'frozen', False)}")
        style = resource_path("app", "resources", "style.qss")
        samples = resource_path("data", "sample_spectra")
        assert style.exists(), f"missing bundled stylesheet: {style}"
        assert samples.is_dir() and any(samples.glob("*.csv")), f"missing sample spectra: {samples}"
        lines.append("resources: stylesheet and sample spectra found")

        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet(style.read_text(encoding="utf-8"))
        window = MainWindow()
        for key in ("dashboard", "energy_levels", "spectrum_simulator", "stellar_analysis",
                    "element_id", "composition", "theory", "about"):
            window.navigate(key)
            app.processEvents()
        lines.append("navigation: all 8 pages opened")

        page = window.stack.currentWidget()
        window.navigate("composition")
        page = window.stack.currentWidget()
        page.rv.setValue(120)
        page._apply_live_update()
        an, sp = page.analysis, page.current
        assert an is not None and sp is not None, "composition analysis did not run"
        assert abs(an.radial_velocity_kms - 120.0) < 10.0, f"radial velocity estimate {an.radial_velocity_kms}"
        assert an.element("H").detected and an.element("He").detected, "H/He not detected"
        lines.append(f"composition: RV estimate {an.radial_velocity_kms:+.1f} km/s, "
                     f"H inferred {an.element('H').inferred_percent:.1f}%")

        buf = io.StringIO()
        write_analysis_csv(buf, sp, an)
        rows = list(csv.reader(io.StringIO(buf.getvalue())))
        assert any(r and r[0] == "# SECTION: spectrum" for r in rows), "CSV spectrum section missing"
        assert len(rows) > 8000, "CSV too short"
        lines.append(f"csv export: {len(rows)} rows")
        ok = True
    except BaseException:  # noqa: BLE001 - report every failure into the result file
        lines.append("FAILED:\n" + traceback.format_exc())
    lines.append("SMOKE TEST PASSED" if ok else "SMOKE TEST FAILED")
    Path(result_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1
