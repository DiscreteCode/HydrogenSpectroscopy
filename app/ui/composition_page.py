"""Stellar Composition Analyzer: multi-element synthetic spectrum + blind analysis.

Simulated INPUT abundances (what the simulation was built from) and INFERRED
abundances (what the analysis recovers from the intensity alone, through the
same toy model) are always shown separately. Nothing here is a measured stellar
abundance.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QScrollArea, QSlider, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from app.widgets.common import card_frame, page_header, section_header
from app.widgets.mpl_canvas import MplCanvas
from spectroscopy.composition import ELEMENT_ORDER, generate_composition_spectrum
from spectroscopy.composition_analysis import (
    analyze_composition, compare_input_and_inferred, write_analysis_csv,
)
from spectroscopy.spectrum import build_wavelength_grid
from visualization.theme import apply_dark_theme

ELEMENT_DEFAULTS = [('H', 'Hydrogen', 70), ('He', 'Helium', 25),
                    ('Na', 'Sodium', 2), ('Ca', 'Calcium', 1), ('Fe', 'Iron', 2)]
ELEMENT_COLORS = {'H': '#4fd1e8', 'He': '#e8c04f', 'Na': '#e8844f',
                  'Ca': '#7ce89d', 'Fe': '#c58ae8'}

# Deliberately synthetic challenge answers. These are model inputs, not real stars.
MYSTERY_PRESETS = (
    {'H': 80, 'He': 20, 'Na': 0, 'Ca': 0, 'Fe': 0},
    {'H': 55, 'He': 30, 'Na': 0, 'Ca': 5, 'Fe': 10},
    {'H': 45, 'He': 25, 'Na': 15, 'Ca': 10, 'Fe': 5},
)

LIMITATIONS_HTML = """
<h3 style='color:#f2f5fb'>What this analysis is - and is not</h3>
<ul>
<li><b>Simulated input vs inferred.</b> "Simulated input" is the weight you chose for each element.
"Inferred" is what a blind line fit recovers from the intensity alone (continuum estimate, Doppler
estimate, per-line depth fit). They are different numbers and are shown separately.</li>
<li><b>The inference inverts this app's own toy model.</b> Line depth is generated as
<code>D<sub>max</sub>&middot;tanh(s&middot;0.65&middot;&radic;(a/a<sub>0</sub>)/D<sub>max</sub>)</code>
with a fixed strength s per element, and the analyzer inverts exactly that mapping. Good agreement therefore
shows the fitting pipeline works; it does <b>not</b> show that real stellar abundances can be read off this way.</li>
<li><b>Not stellar-atmosphere physics.</b> No radiative transfer, curve of growth, ionization balance
(Saha), excitation (Boltzmann), pressure/thermal/microturbulent broadening, NLTE, limb darkening or
molecular lines. The continuum is a plain blackbody.</li>
<li><b>Line lists.</b> Hydrogen Balmer lines are computed from the quantum model. He, Na, Ca and Fe use a short
subset of NIST Handbook reference wavelengths - real spectra have thousands of lines. Lines
within ~3 fitted line-widths of each other are flagged <i>blended</i>.</li>
<li><b>Uncertainties</b> shown are statistical (from the fit covariance and the noise) and exclude
model error. Heavy noise, wide lines, saturation near the toy-model depth limit, or lines near the
edges of the 380-700 nm window reduce reliability.</li>
<li><b>Real work</b> needs high-resolution calibrated spectra, atomic data (oscillator strengths,
excitation energies) and model atmospheres.</li>
</ul>
"""


class CompositionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = None
        self.analysis = None
        self._challenge_truth: dict[str, float] | None = None
        self._challenge_active = False
        self._challenge_revealed = False
        self._mystery_index = -1
        self._challenge_seed = 7

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._apply_live_update)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            'Stellar Composition Analyzer',
            'Simulate a multi-element spectrum, then detect and fit its lines blindly from intensity alone. '
            'Abundances are simulation inputs / demo-model inferences, not measurements of real stars.'
        ))

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)
        body.addWidget(self._build_controls())

        right = QVBoxLayout()
        body.addLayout(right, 1)

        plot_card = card_frame()
        pl = QVBoxLayout(plot_card)
        self.canvas = MplCanvas(figsize=(8, 4.6))
        self.canvas.fig.clear()
        gs = self.canvas.fig.add_gridspec(2, 1, height_ratios=[3, 1.25], hspace=0.14)
        self.canvas.ax = self.canvas.fig.add_subplot(gs[0])
        self.contrib_ax = self.canvas.fig.add_subplot(gs[1], sharex=self.canvas.ax)
        apply_dark_theme(self.canvas.fig, [self.canvas.ax, self.contrib_ax])
        self.canvas.fig.subplots_adjust(left=0.09, right=0.985, bottom=0.14, top=0.88)
        pl.addWidget(self.canvas)
        right.addWidget(plot_card, 3)

        self.tabs = QTabWidget()
        right.addWidget(self.tabs, 2)

        # Tab 1: per-element summary (input vs inferred)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ['Element', 'Simulated input (%)', 'Lines detected', 'Mean fitted depth', 'Status',
             'Line source', 'Inferred (%)', 'Inferred - input'])
        self._style_table(self.table, stretch_col=5)
        self.tabs.addTab(self.table, 'Summary')

        # Tab 2: detected / candidate lines
        self.lines_table = QTableWidget(0, 10)
        self.lines_table.setHorizontalHeaderLabels(
            ['Element', 'Line', 'Reference λ (nm, air)', 'Expected λ (nm)', 'Detected λ (nm)',
             'Δλ (nm)', 'Fitted depth', 'Significance (σ)', 'Detected', 'Notes'])
        self._style_table(self.lines_table, stretch_col=9)
        self.tabs.addTab(self.lines_table, 'Detected lines')

        # Tab 3: input vs inferred abundance charts
        self.abundance_canvas = MplCanvas(figsize=(8, 3))
        self.abundance_canvas.fig.clear()
        self.composition_ax = self.abundance_canvas.fig.add_subplot(121)
        self.inferred_ax = self.abundance_canvas.fig.add_subplot(122)
        apply_dark_theme(self.abundance_canvas.fig, [self.composition_ax, self.inferred_ax])
        self.abundance_canvas.fig.subplots_adjust(left=0.08, right=0.98, bottom=0.14, top=0.86, wspace=0.28)
        self.tabs.addTab(self.abundance_canvas, 'Abundances')

        # Tab 4: limitations
        self.limitations = QTextBrowser()
        self.limitations.setHtml(LIMITATIONS_HTML)
        self.tabs.addTab(self.limitations, 'Limitations')

        self._generate()

    # ------------------------------------------------------------------ UI
    @staticmethod
    def _style_table(table, stretch_col):
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(stretch_col, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

    def _slider_row(self, layout, label, lo, hi, value, formatter):
        layout.addWidget(QLabel(label))
        row = QHBoxLayout()
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        val = QLabel(formatter(value))
        val.setMinimumWidth(64)
        slider.valueChanged.connect(lambda v, lab=val: lab.setText(formatter(v)))
        slider.valueChanged.connect(self._schedule_update)
        row.addWidget(slider, 1)
        row.addWidget(val)
        layout.addLayout(row)
        return slider, val

    def _build_controls(self):
        controls = card_frame()
        controls.setMaximumWidth(330)
        controls.setMinimumWidth(290)
        cl = QVBoxLayout(controls)
        cl.addWidget(section_header('Simulation Inputs'))
        weight_note = QLabel('Relative abundance weights (normalized to 100% internally)')
        weight_note.setWordWrap(True)
        weight_note.setStyleSheet('color:#7c869c;font-size:11px;')
        cl.addWidget(weight_note)
        self.sliders, self.value_labels = {}, {}
        for symbol, name, default in ELEMENT_DEFAULTS:
            slider, val = self._slider_row(cl, f'{name} ({symbol})', 0, 100, default, str)
            self.sliders[symbol] = slider
            self.value_labels[symbol] = val
        self.noise, self.noise_value = self._slider_row(
            cl, 'Noise level (σ of intensity)', 0, 50, 8, lambda v: f'{v / 10:.1f}%')
        self.line_width, self.line_width_value = self._slider_row(
            cl, 'Line width σ (nm)', 5, 60, 22, lambda v: f'{v / 100:.2f} nm')
        self.rv, self.rv_value = self._slider_row(
            cl, 'Radial velocity (km/s, + = receding)', -300, 300, 0, lambda v: f'{v:+d} km/s')

        self.generate_btn = QPushButton('Generate && Analyze')
        self.generate_btn.setObjectName('primaryButton')
        self.generate_btn.clicked.connect(self._generate)
        cl.addWidget(self.generate_btn)
        self.mystery_btn = QPushButton('Load Mystery Star Challenge')
        self.mystery_btn.clicked.connect(self._load_mystery_star)
        cl.addWidget(self.mystery_btn)
        self.reveal_btn = QPushButton('Reveal Mystery Solution')
        self.reveal_btn.setEnabled(False)
        self.reveal_btn.clicked.connect(self._reveal_solution)
        cl.addWidget(self.reveal_btn)
        self.export_btn = QPushButton('Export Analysis CSV')
        self.export_btn.clicked.connect(self._export_csv)
        cl.addWidget(self.export_btn)

        self.status = QLabel('Adjust the inputs; the spectrum and analysis update live.')
        self.status.setWordWrap(True)
        cl.addWidget(self.status)
        note = QLabel(
            'Scientific note: inferred values invert this app’s own toy line-strength model. '
            'Real line depth also depends on temperature, ionization, pressure and atomic data; '
            'this is a demonstration of the workflow, not an abundance solver.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color:#e8c04f;font-size:11px;')
        cl.addWidget(note)
        cl.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setMaximumWidth(350)
        scroll.setMinimumWidth(310)
        return scroll

    # --------------------------------------------------------- state / flow
    @property
    def _hide_solution(self) -> bool:
        return self._challenge_active and not self._challenge_revealed

    def _set_element_sliders_enabled(self, enabled: bool):
        for s in self.sliders.values():
            s.setEnabled(enabled)

    def _schedule_update(self, *_):
        self._timer.start()

    def _apply_live_update(self):
        if self._challenge_active and self._challenge_truth is not None:
            self._render_spectrum(self._challenge_truth, random_seed=self._challenge_seed,
                                  modal_errors=False)
        else:
            abundances = {s: sl.value() for s, sl in self.sliders.items()}
            if sum(abundances.values()) == 0:
                self.status.setText('Set at least one element above zero to update the spectrum.')
                return
            self._render_spectrum(abundances, random_seed=7, modal_errors=False)

    def _generate(self):
        abundances = {symbol: slider.value() for symbol, slider in self.sliders.items()}
        if sum(abundances.values()) == 0:
            QMessageBox.warning(self, 'Composition required', 'Set at least one element above zero.')
            return
        self._timer.stop()
        self._challenge_active = False
        self._challenge_truth = None
        self._challenge_revealed = False
        self.reveal_btn.setEnabled(False)
        self._set_element_sliders_enabled(True)
        self._render_spectrum(abundances, random_seed=7)

    def _load_mystery_star(self):
        self._timer.stop()
        self._mystery_index = (self._mystery_index + 1) % len(MYSTERY_PRESETS)
        self._challenge_truth = dict(MYSTERY_PRESETS[self._mystery_index])
        self._challenge_seed = 40 + self._mystery_index
        self._challenge_active = True
        self._challenge_revealed = False
        self.reveal_btn.setEnabled(True)
        self._set_element_sliders_enabled(False)
        self._render_spectrum(self._challenge_truth, random_seed=self._challenge_seed)
        self.status.setText(
            'Mystery star loaded. Use the spectrum and the Detected lines tab to infer its composition, '
            'then reveal the simulated answer. Noise, line width and radial velocity can still be changed. '
            'This is a synthetic educational challenge.'
        )

    def _reveal_solution(self):
        if not self._challenge_active or self._challenge_truth is None:
            return
        self._challenge_revealed = True
        self._refresh_views()
        self.status.setText('Solution revealed. Input values are the hidden synthetic inputs; '
                            'inferred values are the blind analysis result - neither is a measurement.')
        self.reveal_btn.setEnabled(False)

    def _show_error(self, text, modal):
        if modal:
            QMessageBox.warning(self, 'Could not generate or analyze spectrum', text)
        else:
            self.status.setText(f'⚠ {text}')

    def _render_spectrum(self, abundances, random_seed=7, modal_errors=True):
        try:
            wl = build_wavelength_grid(380, 700, 8000)
            spectrum = generate_composition_spectrum(
                wl, abundances, noise_level=self.noise.value() / 1000,
                radial_velocity_kms=float(self.rv.value()),
                line_sigma_nm=self.line_width.value() / 100.0,
                random_seed=random_seed,
            )
            analysis = analyze_composition(wl, spectrum.intensity)
        except (ValueError, RuntimeError, np.linalg.LinAlgError, FloatingPointError) as exc:
            self._show_error(str(exc), modal_errors)
            return
        self.current, self.analysis = spectrum, analysis
        self._refresh_views()
        if not self._challenge_active:
            detected = [e.symbol for e in analysis.elements if e.detected]
            self.status.setText(
                'Detected line patterns: ' + (', '.join(detected) if detected else 'none above the noise threshold') +
                f'\nEstimated radial velocity: {analysis.radial_velocity_kms:+.1f} ± '
                f'{analysis.radial_velocity_sigma_kms:.1f} km/s.'
                '\n“Input” values are normalized simulation inputs; “inferred” values come from the blind fit.'
                + ('\n' + ' '.join(analysis.notes) if analysis.notes else ''))

    # ------------------------------------------------------------- drawing
    def _refresh_views(self):
        if self.current is None or self.analysis is None:
            return
        self._plot_spectrum()
        self._plot_abundances()
        self._fill_summary_table()
        self._fill_lines_table()
        self.canvas.redraw()
        self.abundance_canvas.redraw()

    def _plot_spectrum(self):
        sp, an, hide = self.current, self.analysis, self._hide_solution
        ax, cax = self.canvas.ax, self.contrib_ax
        ax.clear()
        cax.clear()
        apply_dark_theme(self.canvas.fig, [ax, cax])
        ax.plot(sp.wavelength_nm, sp.intensity, lw=0.9, color='#c9d3e6', label='Observed (simulated + noise)')
        ax.plot(sp.wavelength_nm, an.continuum_estimate, lw=1.1, ls='--', color='#4f8fe8',
                label='Estimated continuum')
        ax.plot(sp.wavelength_nm, an.continuum_estimate * an.fitted_model, lw=0.9, color='#e85f5f',
                alpha=0.8, label='Line fit')
        top = float(np.max(an.continuum_estimate)) * 1.06
        for symbol in ELEMENT_ORDER:
            xs = [m.expected_observed_nm for m in an.matches if m.symbol == symbol and m.detected]
            if xs:
                ax.plot(xs, [top] * len(xs), ls='', marker='v', ms=6, color=ELEMENT_COLORS[symbol],
                        label=f'{symbol} detected')
        ax.set_ylim(0, top * 1.05)
        ax.set_ylabel('Normalized intensity (a.u.)')
        ax.legend(loc='lower left', bbox_to_anchor=(0, 1.01), ncol=4, fontsize=7.5, frameon=False,
                  labelcolor='#c9d3e6')
        ax.tick_params(labelbottom=False)

        if hide:
            cax.text(0.5, 0.5, 'Per-element contributions hidden until the solution is revealed',
                     ha='center', va='center', transform=cax.transAxes, color='#c9d3e6', fontsize=9)
            cax.set_yticks([])
        else:
            for symbol in ELEMENT_ORDER:
                trans = sp.element_transmission[symbol]
                cax.plot(sp.wavelength_nm, 100.0 * (1.0 - trans), lw=0.9, color=ELEMENT_COLORS[symbol],
                         label=symbol)
            cax.set_ylim(bottom=0)
            cax.set_ylabel('Absorption (%)\nper element (sim.)', fontsize=8)
        cax.set_xlabel('Wavelength (nm, standard air)')
        cax.set_xlim(sp.wavelength_nm[0], sp.wavelength_nm[-1])

    def _plot_abundances(self):
        an, sp = self.analysis, self.current
        hide = self._hide_solution
        cax, iax = self.composition_ax, self.inferred_ax
        cax.clear()
        iax.clear()
        apply_dark_theme(self.abundance_canvas.fig, [cax, iax])
        symbols = list(ELEMENT_ORDER)
        colors = [ELEMENT_COLORS[s] for s in symbols]
        cax.set_ylabel('Input abundance (%)')
        iax.set_ylabel('Inferred abundance (%)')
        for a in (cax, iax):
            a.grid(axis='x', visible=False)
        if hide:
            for a, title in ((cax, 'Mystery Composition'), (iax, 'Inferred (hidden)')):
                a.set_title(title)
                a.text(0.5, 0.5, 'Hidden\nReveal the solution to view values', ha='center', va='center',
                       transform=a.transAxes, color='#c9d3e6', wrap=True)
                a.set_xticks([])
                a.set_yticks([])
            return
        inputs = [sp.abundances[s] for s in symbols]
        inferred = [an.element(s).inferred_percent for s in symbols]
        ymax = max(10.0, max(inputs + inferred) * 1.2)
        for a, vals, title in ((cax, inputs, 'Input Composition'),
                               (iax, inferred, 'Inferred (blind fit, demo model)')):
            bars = a.bar(symbols, vals, color=colors)
            a.set_title(title, fontsize=10)
            a.set_ylim(0, ymax)
            for bar, value in zip(bars, vals):
                a.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.01,
                       f'{value:.1f}%', ha='center', va='bottom', fontsize=8, color='#c9d3e6')

    def _fill_summary_table(self):
        an, sp, hide = self.analysis, self.current, self._hide_solution
        cmp_rows = {r['symbol']: r for r in compare_input_and_inferred(an, sp.abundances)}
        self.table.setRowCount(len(an.elements))
        for i, e in enumerate(an.elements):
            r = cmp_rows[e.symbol]
            if hide:
                vals = [f'{e.name} ({e.symbol})', 'Hidden', 'Hidden', 'Hidden', 'Hidden', e.source,
                        'Hidden', 'Hidden']
            else:
                vals = [f'{e.name} ({e.symbol})', f"{r['input_percent']:.1f}%",
                        f'{e.lines_detected} / {e.lines_checked}', f'{100 * e.mean_depth:.1f}%',
                        'DETECTED' if e.detected else 'NOT DETECTED', e.source,
                        f"{e.inferred_percent:.1f}% ± {e.inferred_sigma_percent:.1f}"
                        + (' (lower bound)' if e.saturated else ''),
                        f"{r['difference_percent']:+.1f}"]
            for j, val in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(val))

    def _fill_lines_table(self):
        matches = sorted(self.analysis.matches, key=lambda m: m.expected_observed_nm)
        self.lines_table.setRowCount(len(matches))
        for i, m in enumerate(matches):
            has = np.isfinite(m.detected_wavelength_nm)
            notes = []
            if m.blended:
                notes.append('blended with a neighbouring line')
            if m.detected and not has:
                notes.append('no separate peak (blend/shoulder)')
            vals = [m.symbol, m.label, f'{m.reference_nm:.3f}', f'{m.expected_observed_nm:.3f}',
                    f'{m.detected_wavelength_nm:.3f}' if has else '—',
                    f'{m.detected_wavelength_nm - m.expected_observed_nm:+.3f}' if has else '—',
                    f'{100 * m.fitted_depth:.1f}%', f'{m.significance:.1f}',
                    'Yes' if m.detected else 'No', '; '.join(notes) or m.source]
            for j, val in enumerate(vals):
                self.lines_table.setItem(i, j, QTableWidgetItem(val))

    # --------------------------------------------------------------- export
    def _export_csv(self):
        if self.current is None or self.analysis is None:
            QMessageBox.warning(self, 'No analysis', 'Generate a spectrum before exporting.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Composition Analysis', 'stellar_composition_analysis.csv', 'CSV Files (*.csv)'
        )
        if not path:
            return
        try:
            with open(Path(path), 'w', newline='', encoding='utf-8') as handle:
                write_analysis_csv(handle, self.current, self.analysis, hide_solution=self._hide_solution)
        except OSError as exc:
            QMessageBox.warning(self, 'Export failed', f'Could not write the CSV file:\n{exc}')
            return
        QMessageBox.information(self, 'Export complete', f'Analysis exported to:\n{path}')
