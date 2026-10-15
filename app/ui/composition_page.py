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
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QScrollArea, QSlider, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from app.widgets.common import StatCard, card_frame, page_header, section_header
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



PRESETS = {
    'Default demo star': {'H': 70, 'He': 25, 'Na': 2, 'Ca': 1, 'Fe': 2},
    'Hydrogen-dominated': {'H': 90, 'He': 8, 'Na': 0, 'Ca': 1, 'Fe': 1},
    'Helium-rich': {'H': 35, 'He': 60, 'Na': 1, 'Ca': 1, 'Fe': 3},
    'Metal-rich': {'H': 45, 'He': 25, 'Na': 15, 'Ca': 10, 'Fe': 5},
}


class CompositionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = None
        self.analysis = None
        self._loading_preset = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._apply_live_update)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        root.addWidget(page_header(
            'Stellar Composition Analyzer',
            'Build a synthetic multi-element spectrum, then let the analysis find the lines blindly from the '
            'intensity alone. Abundances are simulation inputs and demo-model inferences, not measurements of real stars.'
        ))

        # --- KPI strip -------------------------------------------------
        kpis = QHBoxLayout()
        kpis.setSpacing(12)
        self.kpi_rv = StatCard('Radial velocity (estimated)', '--', accent=True)
        self.kpi_elements = StatCard('Elements detected', '--')
        self.kpi_lines = StatCard('Lines detected', '--')
        self.kpi_noise = StatCard('Fit noise (rms)', '--')
        for card in (self.kpi_rv, self.kpi_elements, self.kpi_lines, self.kpi_noise):
            kpis.addWidget(card, 1)
        root.addLayout(kpis)

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)
        body.addWidget(self._build_controls())

        right = QVBoxLayout()
        right.setSpacing(12)
        body.addLayout(right, 1)

        plot_card = card_frame()
        pl = QVBoxLayout(plot_card)
        pl.setContentsMargins(8, 8, 8, 8)
        self.canvas = MplCanvas(figsize=(8, 4.8))
        self.canvas.fig.clear()
        gs = self.canvas.fig.add_gridspec(2, 1, height_ratios=[3.2, 1.2], hspace=0.12)
        self.canvas.ax = self.canvas.fig.add_subplot(gs[0])
        self.contrib_ax = self.canvas.fig.add_subplot(gs[1], sharex=self.canvas.ax)
        apply_dark_theme(self.canvas.fig, [self.canvas.ax, self.contrib_ax])
        self.canvas.fig.subplots_adjust(left=0.08, right=0.985, bottom=0.14, top=0.87)
        pl.addWidget(self.canvas)
        right.addWidget(plot_card, 5)

        self.tabs = QTabWidget()
        right.addWidget(self.tabs, 4)

        # Tab 1: input vs inferred abundance (one grouped chart)
        self.abundance_canvas = MplCanvas(figsize=(8, 3))
        self.abundance_canvas.fig.clear()
        self.abundance_ax = self.abundance_canvas.fig.add_subplot(111)
        apply_dark_theme(self.abundance_canvas.fig, [self.abundance_ax])
        self.abundance_canvas.fig.subplots_adjust(left=0.07, right=0.985, bottom=0.14, top=0.84)
        self.tabs.addTab(self.abundance_canvas, 'Abundances')

        # Tab 2: detected / candidate lines
        self.lines_table = QTableWidget(0, 10)
        self.lines_table.setHorizontalHeaderLabels(
            ['Element', 'Line', 'Reference λ (nm)', 'Expected λ (nm)', 'Detected λ (nm)',
             'Δλ (nm)', 'Fitted depth', 'Significance (σ)', 'Detected', 'Notes'])
        self._style_table(self.lines_table, stretch_col=9)
        self.tabs.addTab(self.lines_table, 'Detected lines')

        # Tab 3: per-element summary (input vs inferred)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ['Element', 'Simulated input (%)', 'Lines detected', 'Mean fitted depth', 'Status',
             'Line source', 'Inferred (%)', 'Inferred - input'])
        self._style_table(self.table, stretch_col=5)
        self.tabs.addTab(self.table, 'Summary')

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
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)

    @staticmethod
    def _slider_style(color):
        return (f'QSlider::sub-page:horizontal {{ background: {color}; border-radius: 2px; }}'
                f'QSlider::handle:horizontal {{ background: {color}; }}')

    def _slider_row(self, layout, label_html, lo, hi, value, suffix='', color=None, scale=1, decimals=0):
        """Label on top, slider + exact-entry spin box below. ``scale`` converts slider
        integer steps to the displayed value (e.g. 100 -> 0.01 steps). Returns (slider, spin)."""
        layout.addWidget(self._small_label(label_html))
        row = QHBoxLayout()
        row.setSpacing(8)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(value)
        if color:
            slider.setStyleSheet(self._slider_style(color))
        if scale == 1:
            spin = QSpinBox()
            spin.setRange(lo, hi)
        else:
            spin = QDoubleSpinBox()
            spin.setRange(lo / scale, hi / scale)
            spin.setDecimals(decimals)
            spin.setSingleStep(1.0 / scale)
        spin.setValue(value / scale)
        spin.setSuffix(suffix)
        spin.setFixedWidth(96)
        spin.setFixedHeight(28)
        spin.setKeyboardTracking(False)
        # typed values are clamped by the spin box range, so invalid entries cannot reach the physics code
        slider.valueChanged.connect(lambda v: spin.setValue(v / scale))
        spin.valueChanged.connect(lambda v: slider.setValue(int(round(v * scale))))
        slider.valueChanged.connect(self._schedule_update)
        row.addWidget(slider, 1)
        row.addWidget(spin)
        layout.addLayout(row)
        return slider, spin

    @staticmethod
    def _small_label(html):
        lab = QLabel(html)
        lab.setTextFormat(Qt.RichText)
        lab.setStyleSheet('color:#c9d3e6;font-size:12px;')
        return lab

    def _build_controls(self):
        controls = QWidget()
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(0, 0, 6, 0)
        cl.setSpacing(12)

        comp = card_frame()
        cc = QVBoxLayout(comp)
        cc.setSpacing(4)
        cc.addWidget(section_header('Composition (input weights)'))
        note = QLabel('Relative weights, normalized to 100% internally.')
        note.setWordWrap(True)
        note.setStyleSheet('color:#7c869c;font-size:11px;')
        cc.addWidget(note)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem('Presets (demo weights)…')
        for name in PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.currentIndexChanged.connect(self._on_preset)
        cc.addWidget(self.preset_combo)
        self.sliders, self.spins = {}, {}
        for symbol, name, default in ELEMENT_DEFAULTS:
            color = ELEMENT_COLORS[symbol]
            html = f"<span style='color:{color};font-size:14px;'>●</span>&nbsp;{name} <b>({symbol})</b>"
            slider, spin = self._slider_row(cc, html, 0, 100, default, color=color)
            self.sliders[symbol] = slider
            self.spins[symbol] = spin
        cl.addWidget(comp)

        obs = card_frame()
        oc = QVBoxLayout(obs)
        oc.setSpacing(4)
        oc.addWidget(section_header('Observation'))
        self.noise, self.noise_spin = self._slider_row(
            oc, 'Noise level (σ, % of peak flux)', 0, 50, 8, suffix=' %', scale=10, decimals=1)
        self.line_width, self.line_width_spin = self._slider_row(
            oc, 'Line width σ (nm)', 5, 60, 22, suffix=' nm', scale=100, decimals=2)
        self.rv, self.rv_spin = self._slider_row(
            oc, 'Radial velocity (km/s, + = receding)', -300, 300, 0, suffix=' km/s')
        cl.addWidget(obs)

        actions = QHBoxLayout()
        self.generate_btn = QPushButton('Re-run analysis')
        self.generate_btn.setObjectName('primaryButton')
        self.generate_btn.clicked.connect(self._generate)
        self.reset_btn = QPushButton('Reset')
        self.reset_btn.clicked.connect(self._reset)
        actions.addWidget(self.generate_btn, 2)
        actions.addWidget(self.reset_btn, 1)
        cl.addLayout(actions)
        self.export_btn = QPushButton('Export analysis CSV')
        self.export_btn.clicked.connect(self._export_csv)
        cl.addWidget(self.export_btn)

        self.status = QLabel('Adjust the inputs; the spectrum and analysis update live.')
        self.status.setWordWrap(True)
        self.status.setStyleSheet('color:#97a3ba;font-size:11px;')
        cl.addWidget(self.status)
        warn = QLabel(
            'Inferred values invert this app’s own toy line-strength model. This demonstrates the workflow; '
            'it is not an abundance solver. See the Limitations tab.')
        warn.setWordWrap(True)
        warn.setStyleSheet('color:#e8c04f;font-size:11px;')
        cl.addWidget(warn)
        cl.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(340)
        return scroll

    # --------------------------------------------------------- state / flow
    def _schedule_update(self, *_):
        self._timer.start()

    def _on_preset(self, index):
        if index <= 0:
            return
        values = PRESETS[self.preset_combo.itemText(index)]
        for symbol, slider in self.sliders.items():
            slider.blockSignals(True)
            slider.setValue(values[symbol])
            slider.blockSignals(False)
            self.spins[symbol].blockSignals(True)
            self.spins[symbol].setValue(values[symbol])
            self.spins[symbol].blockSignals(False)
        self._schedule_update()

    def _reset(self):
        for symbol, _name, default in ELEMENT_DEFAULTS:
            self.sliders[symbol].setValue(default)
        self.noise.setValue(8)
        self.line_width.setValue(22)
        self.rv.setValue(0)
        self.preset_combo.setCurrentIndex(0)
        self._generate()

    def _abundance_inputs(self):
        return {s: sl.value() for s, sl in self.sliders.items()}

    def _apply_live_update(self):
        abundances = self._abundance_inputs()
        if sum(abundances.values()) == 0:
            self.status.setText('Set at least one element above zero to update the spectrum.')
            return
        self._render_spectrum(abundances, modal_errors=False)

    def _generate(self):
        abundances = self._abundance_inputs()
        if sum(abundances.values()) == 0:
            QMessageBox.warning(self, 'Composition required', 'Set at least one element above zero.')
            return
        self._timer.stop()
        self._render_spectrum(abundances)

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
        detected = [e.symbol for e in analysis.elements if e.detected]
        self.status.setText(
            'Detected line patterns: ' + (', '.join(detected) if detected else 'none above the noise threshold') +
            '.\n“Input” values are normalized simulation inputs; “inferred” values come from the blind fit.'
            + ('\n' + ' '.join(analysis.notes) if analysis.notes else ''))

    # ------------------------------------------------------------- drawing
    def _refresh_views(self):
        if self.current is None or self.analysis is None:
            return
        an = self.analysis
        self.kpi_rv.set_value(f'{an.radial_velocity_kms:+.1f} ± {an.radial_velocity_sigma_kms:.1f} km/s')
        n_el = sum(e.detected for e in an.elements)
        self.kpi_elements.set_value(f'{n_el} of {len(an.elements)}')
        n_det = sum(m.detected for m in an.matches)
        self.kpi_lines.set_value(f'{n_det} of {len(an.matches)}')
        self.kpi_noise.set_value(f'{an.noise_sigma:.4f}')
        self._plot_spectrum()
        self._plot_abundances()
        self._fill_summary_table()
        self._fill_lines_table()
        self.canvas.redraw()
        self.abundance_canvas.redraw()

    def _plot_spectrum(self):
        sp, an = self.current, self.analysis
        ax, cax = self.canvas.ax, self.contrib_ax
        ax.clear()
        cax.clear()
        apply_dark_theme(self.canvas.fig, [ax, cax])
        ax.plot(sp.wavelength_nm, sp.intensity, lw=0.8, color='#aab6cf', label='Observed (simulated + noise)')
        ax.plot(sp.wavelength_nm, an.continuum_estimate, lw=1.2, ls='--', color='#4f8fe8',
                label='Estimated continuum')
        ax.plot(sp.wavelength_nm, an.continuum_estimate * an.fitted_model, lw=1.0, color='#e85f5f',
                alpha=0.85, label='Line fit')
        top = float(np.max(an.continuum_estimate)) * 1.07
        for symbol in ELEMENT_ORDER:
            xs = [m.expected_observed_nm for m in an.matches if m.symbol == symbol and m.detected]
            if xs:
                ax.plot(xs, [top] * len(xs), ls='', marker='v', ms=6, color=ELEMENT_COLORS[symbol],
                        label=f'{symbol} lines')
        ax.set_ylim(0, top * 1.06)
        ax.set_ylabel('Normalized intensity (a.u.)')
        ax.legend(loc='lower left', bbox_to_anchor=(0, 1.01), ncol=4, fontsize=8, frameon=False,
                  labelcolor='#c9d3e6')
        ax.tick_params(labelbottom=False)
        for symbol in ELEMENT_ORDER:
            trans = sp.element_transmission[symbol]
            cax.plot(sp.wavelength_nm, 100.0 * (1.0 - trans), lw=1.0, color=ELEMENT_COLORS[symbol])
        cax.set_ylim(bottom=0)
        cax.set_ylabel('Absorption (%)\nper element', fontsize=8)
        cax.set_xlabel('Wavelength (nm, standard air)')
        cax.set_xlim(sp.wavelength_nm[0], sp.wavelength_nm[-1])

    def _plot_abundances(self):
        an, sp = self.analysis, self.current
        ax = self.abundance_ax
        ax.clear()
        apply_dark_theme(self.abundance_canvas.fig, [ax])
        symbols = list(ELEMENT_ORDER)
        x = np.arange(len(symbols))
        inputs = np.array([sp.abundances[s] for s in symbols])
        inferred = np.array([an.element(s).inferred_percent for s in symbols])
        w = 0.36
        colors = [ELEMENT_COLORS[s] for s in symbols]
        in_bars = ax.bar(x - w / 2, inputs, w, facecolor='none', edgecolor=colors, linewidth=1.8)
        out_bars = ax.bar(x + w / 2, inferred, w, color=colors)
        ymax = max(10.0, float(max(inputs.max(), inferred.max())) * 1.18)
        ax.set_ylim(0, ymax)
        ax.set_xticks(x)
        ax.set_xticklabels(symbols, fontsize=10)
        ax.set_ylabel('Relative abundance (% of demo weights)', fontsize=9)
        ax.set_title('Simulated input (outline) vs inferred by blind fit (solid)', fontsize=10)
        ax.grid(axis='x', visible=False)
        for bars, vals in ((in_bars, inputs), (out_bars, inferred)):
            for bar, value in zip(bars, vals):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.012,
                        f'{value:.1f}', ha='center', va='bottom', fontsize=8, color='#c9d3e6')

    def _fill_summary_table(self):
        an, sp = self.analysis, self.current
        cmp_rows = {r['symbol']: r for r in compare_input_and_inferred(an, sp.abundances)}
        self.table.setRowCount(len(an.elements))
        for i, e in enumerate(an.elements):
            r = cmp_rows[e.symbol]
            vals = [f'{e.name} ({e.symbol})', f"{r['input_percent']:.1f}%",
                    f'{e.lines_detected} / {e.lines_checked}', f'{100 * e.mean_depth:.1f}%',
                    'DETECTED' if e.detected else 'NOT DETECTED', e.source,
                    f"{e.inferred_percent:.1f}% ± {e.inferred_sigma_percent:.1f}"
                    + (' (lower bound)' if e.saturated else ''),
                    f"{r['difference_percent']:+.1f}"]
            for j, val in enumerate(vals):
                item = QTableWidgetItem(val)
                if j == 4:
                    item.setForeground(QColor('#39d98a' if e.detected else '#7c869c'))
                self.table.setItem(i, j, item)

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
                item = QTableWidgetItem(val)
                if j == 0:
                    item.setForeground(QColor(ELEMENT_COLORS[m.symbol]))
                if j == 8:
                    item.setForeground(QColor('#39d98a' if m.detected else '#7c869c'))
                self.lines_table.setItem(i, j, item)

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
                write_analysis_csv(handle, self.current, self.analysis)
        except OSError as exc:
            QMessageBox.warning(self, 'Export failed', f'Could not write the CSV file:\n{exc}')
            return
        QMessageBox.information(self, 'Export complete', f'Analysis exported to:\n{path}')
