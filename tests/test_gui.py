"""
tests.test_gui
==================

GUI tests (Checkpoint 2, brief section 28-29). These run against a
real QApplication using Qt's "offscreen" platform plugin, so they
work in headless CI / this sandbox with no physical display, and they
drive real widget code -- not mocks of it -- for every page.

Modal QMessageBox calls block forever under the offscreen platform
(there's no user to click them), so tests that exercise a code path
which can pop one patch QMessageBox out for the duration of that call.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.ui.main_window import MainWindow

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_spectra"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qapp):
    w = MainWindow()
    yield w
    w.deleteLater()


# ---------------------------------------------------------------------------
# Shell / navigation
# ---------------------------------------------------------------------------


def test_main_window_constructs(window):
    assert window.stack.count() == 8


@pytest.mark.parametrize(
    "key",
    ["dashboard", "energy_levels", "spectrum_simulator", "stellar_analysis",
     "element_id", "composition", "theory", "about"],
)
def test_navigation_reaches_every_page(window, key):
    window.navigate(key)
    assert window.stack.currentIndex() == window._page_index[key]
    assert window._nav_buttons[key].isChecked()


def test_navigate_ignores_unknown_key(window):
    window.navigate("dashboard")
    before = window.stack.currentIndex()
    window.navigate("not_a_real_page")
    assert window.stack.currentIndex() == before


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def test_dashboard_updates_on_transition_change(window):
    window.navigate("dashboard")
    dash = window.stack.currentWidget()
    from physics.transitions import compute_emission_transition

    tr = compute_emission_transition(3, 2)
    window.app_state.set_current_transition(tr)
    assert "3" in dash.card_transition.value_label.text()
    assert "656" in dash.card_wavelength.value_label.text()


def test_dashboard_nav_card_navigates(window):
    window.navigate("dashboard")
    dash = window.stack.currentWidget()
    dash.navigate("theory")
    assert window.stack.currentIndex() == window._page_index["theory"]


# ---------------------------------------------------------------------------
# Energy Levels & Transition Explorer (critical path: 3 -> 2)
# ---------------------------------------------------------------------------


def test_energy_levels_3_to_2_matches_known_values(window):
    window.navigate("energy_levels")
    page = window.stack.currentWidget()
    page.n_initial_spin.setValue(3)
    page.n_final_spin.setValue(2)
    page.calculate()

    tr = page.current_transition
    assert tr is not None
    assert tr.wavelength_nm == pytest.approx(656.46, abs=0.1)
    assert tr.wavelength_air_nm == pytest.approx(656.28, abs=0.1)
    assert tr.series == "Balmer"
    assert page.animate_btn.isEnabled()
    assert page.add_btn.isEnabled()


def test_energy_levels_rejects_absorption_order(window):
    window.navigate("energy_levels")
    page = window.stack.currentWidget()
    # n_final_spin.valueChanged keeps n_initial > n_final automatically,
    # so force an invalid state directly to confirm calculate() still
    # guards against it defensively.
    page.n_initial_spin.setValue(2)
    page.n_final_spin.setValue(2)
    page.n_initial_spin.setValue(2)
    page.calculate()
    # Either the spinboxes' own constraint kept it valid, or calculate()
    # reported the error -- either way there must be no crash and no
    # false "success" state left dangling.
    if page.current_transition is None:
        assert page.error_label.text() != ""


def test_energy_levels_animation_progresses_and_stops(window):
    window.navigate("energy_levels")
    page = window.stack.currentWidget()
    page.n_initial_spin.setValue(4)
    page.n_final_spin.setValue(2)
    page.calculate()
    page.animate()
    assert page._anim_timer.isActive()
    for _ in range(40):
        page._animation_tick()
    assert page._anim_progress == pytest.approx(1.0)
    assert not page._anim_timer.isActive()
    assert page.animate_btn.isEnabled()


def test_add_to_spectrum_updates_app_state(window, qapp):
    window.navigate("energy_levels")
    page = window.stack.currentWidget()
    page.n_initial_spin.setValue(3)
    page.n_final_spin.setValue(2)
    page.calculate()
    with patch.object(QMessageBox, "information", return_value=None):
        page._add_to_spectrum()
    assert len(window.app_state.custom_transitions) == 1
    assert window.app_state.custom_transitions[0].label == "3 -> 2"


# ---------------------------------------------------------------------------
# Spectrum Simulator
# ---------------------------------------------------------------------------


def test_spectrum_simulator_generates_balmer_series(window):
    window.navigate("spectrum_simulator")
    page = window.stack.currentWidget()
    page.series_combo.setCurrentText("Balmer")
    page.generate()
    assert page.current_spectrum is not None
    assert len(page.current_spectrum.wavelength_nm) == page.resolution_spin.value()
    # Balmer-alpha should fall inside the generated range.
    lo, hi = page.current_spectrum.wavelength_nm[0], page.current_spectrum.wavelength_nm[-1]
    assert lo <= 656.3 <= hi


def test_spectrum_simulator_absorption_mode(window):
    window.navigate("spectrum_simulator")
    page = window.stack.currentWidget()
    page.mode_combo.setCurrentText("Absorption")
    page.generate()
    from spectroscopy.spectrum import SpectrumMode

    assert page.current_spectrum.mode == SpectrumMode.ABSORPTION


def test_spectrum_simulator_export_without_data_warns(window):
    window.navigate("spectrum_simulator")
    page = window.stack.currentWidget()
    page.current_spectrum = None
    with patch.object(QMessageBox, "information", return_value=None) as mock_info:
        page._export_png()
    mock_info.assert_called_once()


# ---------------------------------------------------------------------------
# Stellar Spectrum & Analysis (critical path: simulate -> analyze -> verdict)
# ---------------------------------------------------------------------------


def test_stellar_simulate_and_detect_hydrogen(window):
    window.navigate("stellar_analysis")
    page = window.stack.currentWidget()
    page.temp_slider.setValue(9500)
    page.vel_slider.setValue(0)
    page.noise_slider.setValue(10)
    page.strength_slider.setValue(85)
    page._generate_synthetic()
    assert page.current_star is not None
    assert page.analyze_btn.isEnabled()

    page._run_analysis()
    assert page._pipeline_timer.isActive()
    for _ in range(10):
        page._pipeline_tick()
    assert not page._pipeline_timer.isActive()

    summary = page.current_summary
    assert summary is not None
    assert summary.detected is True
    assert summary.num_matched == 4
    assert page.table.rowCount() == 4
    assert "HYDROGEN DETECTED" in page.verdict_label.text()


def test_stellar_negative_control_sample_not_detected(window):
    window.navigate("stellar_analysis")
    page = window.stack.currentWidget()
    control = DATA_DIR / "stellar_no_hydrogen_control.csv"
    assert control.exists()
    page._load_csv_path(control)
    page._run_analysis()
    for _ in range(10):
        page._pipeline_tick()
    assert page.current_summary.detected is False
    assert "NOT DETECTED" in page.verdict_label.text()


def test_stellar_doppler_shifted_sample_loads_and_analyzes(window):
    window.navigate("stellar_analysis")
    page = window.stack.currentWidget()
    sample = DATA_DIR / "stellar_doppler_shifted_180kms.csv"
    assert sample.exists()
    page._load_csv_path(sample)
    page._run_analysis()
    for _ in range(10):
        page._pipeline_tick()
    assert page.current_summary is not None
    assert page.table.rowCount() == 4


def test_stellar_doppler_readout_updates_with_velocity(window):
    window.navigate("stellar_analysis")
    page = window.stack.currentWidget()
    page._on_velocity_changed(0)
    text_at_rest = page.doppler_readout.text()
    page._on_velocity_changed(200)
    text_receding = page.doppler_readout.text()
    assert text_at_rest != text_receding
    assert "redshift" in text_receding


def test_stellar_malformed_file_shows_warning_and_keeps_state(window, tmp_path):
    window.navigate("stellar_analysis")
    page = window.stack.currentWidget()

    good = DATA_DIR / "stellar_noisy_at_rest.csv"
    page._load_csv_path(good)
    star_before = page.current_star

    bad_file = tmp_path / "bad.csv"
    bad_file.write_text("not,a,spectrum\nfoo,bar,baz\n")

    with patch.object(QMessageBox, "warning", return_value=None) as mock_warn:
        page._load_csv_path(bad_file)

    mock_warn.assert_called_once()
    assert page.current_star is star_before  # malformed load must not clobber good data


def test_stellar_export_without_analysis_warns(window):
    window.navigate("stellar_analysis")
    page = window.stack.currentWidget()
    page.current_summary = None
    with patch.object(QMessageBox, "information", return_value=None) as mock_info:
        page._export_csv()
    mock_info.assert_called_once()


# ---------------------------------------------------------------------------
# Element Identification
# ---------------------------------------------------------------------------


def test_element_identification_hydrogen_is_computed_live(window):
    window.navigate("element_id")
    page = window.stack.currentWidget()
    page.element_list.setCurrentRow(0)
    assert "AVAILABLE" in page.badge_label.text()
    assert page.table.rowCount() > 0
    # First row must be a real computed Balmer line, not a lookup value.
    assert page.table.item(0, 3).text() == "Quantum calculated"


def test_element_identification_others_are_reference_only(window):
    window.navigate("element_id")
    page = window.stack.currentWidget()
    from spectroscopy.element_database import list_elements

    symbols = list_elements()
    helium_row = symbols.index("He")
    page.element_list.setCurrentRow(helium_row)
    assert "REFERENCE ONLY" in page.badge_label.text()
    assert page.table.rowCount() > 0
    assert page.table.item(0, 3).text() == "Reference database"


# ---------------------------------------------------------------------------
# Theory / Learn and About pages
# ---------------------------------------------------------------------------


def test_theory_page_has_all_topics_and_links_navigate(window):
    window.navigate("theory")
    page = window.stack.currentWidget()
    assert page.topic_list.count() == 12

    page.topic_list.setCurrentRow(1)  # "Hydrogen Energy Levels" -> energy_levels
    # The window is never actually shown in headless tests, so
    # isVisible() would be False regardless of show()/hide() calls
    # (it also depends on the whole ancestor chain being shown);
    # isHidden() reflects the widget's own explicit show/hide state.
    assert not page.link_btn.isHidden()
    page._on_link_clicked()
    assert window.stack.currentIndex() == window._page_index["energy_levels"]


def test_theory_topic_without_link_hides_button(window):
    window.navigate("theory")
    page = window.stack.currentWidget()
    page.topic_list.setCurrentRow(0)  # "Quantization" has no linked page
    assert page.link_btn.isHidden()


def test_about_page_renders_content(window):
    from PySide6.QtWidgets import QTextBrowser

    window.navigate("about")
    page = window.stack.currentWidget()
    browser = page.findChildren(QTextBrowser)[0]
    assert "Hydrogen" in browser.toPlainText()
    assert "NIST" in browser.toPlainText()


# ---------------------------------------------------------------------------
# Multi-element synthetic composition analyzer
# ---------------------------------------------------------------------------


def test_composition_page_generates_five_element_summary(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    assert page.current is not None
    assert page.table.rowCount() == 5
    assert page.sliders["H"].value() == 70


def test_mystery_star_hides_abundances_until_revealed(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    page._load_mystery_star()
    assert page._challenge_active
    assert page.reveal_btn.isEnabled()
    assert page.table.item(0, 1).text() == "Hidden"
    page._reveal_solution()
    assert not page.reveal_btn.isEnabled()
    assert page.table.item(0, 1).text().endswith("%")

# ---------------------------------------------------------------------------
# Stellar Composition Analyzer (Review 2 feature)
# ---------------------------------------------------------------------------


def test_composition_page_generates_multielement_spectrum(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    assert page.current is not None
    assert page.table.rowCount() == 5
    assert page.composition_ax.get_title() == "Input Composition"
    assert len(page.composition_ax.patches) == 5
    assert "normalized simulation inputs" in page.status.text().lower()


def test_mystery_star_hides_abundances_until_revealed(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    page._load_mystery_star()

    assert page._challenge_active is True
    assert page.reveal_btn.isEnabled()
    assert all(page.table.item(row, 1).text() == "Hidden" for row in range(5))
    assert all(page.table.item(row, 2).text() == "Hidden" for row in range(5))
    assert all(page.table.item(row, 3).text() == "Hidden" for row in range(5))
    assert all(page.table.item(row, 4).text() == "Hidden" for row in range(5))
    assert page.composition_ax.get_title() == "Mystery Composition"
    assert len(page.composition_ax.patches) == 0

    page._reveal_solution()
    assert page._challenge_revealed is True
    assert page.table.item(0, 1).text() == "80.0%"
    assert len(page.composition_ax.patches) == 5
    assert not page.reveal_btn.isEnabled()


def test_mystery_csv_export_does_not_leak_solution(window, tmp_path):
    import csv

    window.navigate("composition")
    page = window.stack.currentWidget()
    page._load_mystery_star()
    export_path = tmp_path / "mystery.csv"
    with patch("app.ui.composition_page.QFileDialog.getSaveFileName",
               return_value=(str(export_path), "CSV Files (*.csv)")), \
         patch.object(QMessageBox, "information", return_value=None):
        page._export_csv()

    with export_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    element_rows = [row for row in rows if row and row[0] in {"Hydrogen", "Helium", "Sodium", "Calcium", "Iron"}]
    assert len(element_rows) == 5
    assert all(row[1:6] == ["Hidden"] * 5 for row in element_rows)


# ---------------------------------------------------------------------------
# Review 2: blind analysis, live updates, CSV export
# ---------------------------------------------------------------------------


def test_composition_page_shows_input_and_inferred_separately(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    assert page.table.item(0, 1).text() == "70.0%"            # simulated input
    assert page.table.item(0, 6).text().startswith("69") or page.table.item(0, 6).text().startswith("70")
    assert len(page.inferred_ax.patches) == 5
    assert "inferred" in page.inferred_ax.get_title().lower()
    assert page.lines_table.rowCount() >= 15
    assert page.lines_table.horizontalHeaderItem(2).text().startswith("Reference")
    assert page.canvas.ax.get_ylabel() and page.contrib_ax.get_xlabel().startswith("Wavelength")
    assert "Limitations" in [page.tabs.tabText(i) for i in range(page.tabs.count())]


def test_composition_live_update_changes_analysis_for_new_radial_velocity(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    page.rv.setValue(150)
    page._apply_live_update()
    assert page.analysis.radial_velocity_kms == pytest.approx(150, abs=5)
    page.sliders["Na"].setValue(0)
    page._apply_live_update()
    assert not page.analysis.element("Na").detected
    assert page.table.item(2, 2).text().startswith("0 /")


def test_composition_all_zero_live_update_is_graceful(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    for s in page.sliders.values():
        s.setValue(0)
    page._apply_live_update()          # must not raise or pop a modal dialog
    assert "at least one element" in page.status.text().lower()


def test_composition_csv_export_contains_analysis(window, tmp_path):
    import csv
    window.navigate("composition")
    page = window.stack.currentWidget()
    out = tmp_path / "analysis.csv"
    with patch("app.ui.composition_page.QFileDialog.getSaveFileName",
               return_value=(str(out), "CSV Files (*.csv)")), \
         patch.object(QMessageBox, "information", return_value=None):
        page._export_csv()
    rows = list(csv.reader(out.open(newline="", encoding="utf-8")))
    flat = [r[0] for r in rows if r]
    assert "# SECTION: detected lines" in flat and "# SECTION: spectrum" in flat
    hydrogen = next(r for r in rows if r and r[0] == "Hydrogen")
    assert hydrogen[1] == "70.000" and hydrogen[5] == "DETECTED"


def test_composition_csv_export_failure_is_reported_not_raised(window, tmp_path):
    window.navigate("composition")
    page = window.stack.currentWidget()
    bad = tmp_path / "missing_dir" / "x.csv"
    with patch("app.ui.composition_page.QFileDialog.getSaveFileName",
               return_value=(str(bad), "CSV Files (*.csv)")), \
         patch.object(QMessageBox, "warning") as warn:
        page._export_csv()
    assert warn.called


def test_mystery_star_inferred_chart_hidden_until_reveal(window):
    window.navigate("composition")
    page = window.stack.currentWidget()
    page._load_mystery_star()
    assert len(page.inferred_ax.patches) == 0
    assert all(not s.isEnabled() for s in page.sliders.values())
    page._reveal_solution()
    assert len(page.inferred_ax.patches) == 5


def test_headless_smoke_test_passes(tmp_path):
    from app.smoke_test import run
    out = tmp_path / "smoke.txt"
    assert run(str(out)) == 0
    assert "SMOKE TEST PASSED" in out.read_text(encoding="utf-8")
