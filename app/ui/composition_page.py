"""Interactive synthetic multi-element composition demonstration."""
from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QFileDialog,
)

from app.widgets.common import card_frame, page_header, section_header
from app.widgets.mpl_canvas import MplCanvas
from spectroscopy.composition import generate_composition_spectrum, summarize_composition
from spectroscopy.spectrum import build_wavelength_grid

ELEMENT_DEFAULTS = [('H', 'Hydrogen', 70), ('He', 'Helium', 25),
                    ('Na', 'Sodium', 2), ('Ca', 'Calcium', 1), ('Fe', 'Iron', 2)]

# Deliberately synthetic challenge answers. These are model inputs, not real stars.
MYSTERY_PRESETS = (
    {'H': 80, 'He': 20, 'Na': 0, 'Ca': 0, 'Fe': 0},
    {'H': 55, 'He': 30, 'Na': 0, 'Ca': 5, 'Fe': 10},
    {'H': 45, 'He': 25, 'Na': 15, 'Ca': 10, 'Fe': 5},
)


class CompositionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = None
        self._challenge_truth: dict[str, float] | None = None
        self._challenge_active = False
        self._challenge_revealed = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            'Stellar Composition Analyzer',
            'Explore synthetic stellar spectra containing hydrogen, helium, sodium, calcium and iron. '
            'Abundances are simulation inputs, not measurements inferred from real stars.'
        ))

        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)
        controls = card_frame()
        controls.setMaximumWidth(310)
        cl = QVBoxLayout(controls)
        cl.addWidget(section_header('Synthetic Composition'))
        weight_note = QLabel('Relative abundance weights (normalized to 100% below)')
        weight_note.setWordWrap(True)
        weight_note.setStyleSheet('color:#7c869c;font-size:11px;')
        cl.addWidget(weight_note)
        self.sliders = {}
        self.value_labels = {}
        for symbol, name, default in ELEMENT_DEFAULTS:
            cl.addWidget(QLabel(f'{name} ({symbol})'))
            row = QHBoxLayout()
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default)
            value = QLabel(str(default))
            value.setMinimumWidth(42)
            slider.valueChanged.connect(lambda v, lab=value: lab.setText(str(v)))
            row.addWidget(slider, 1)
            row.addWidget(value)
            cl.addLayout(row)
            self.sliders[symbol] = slider
            self.value_labels[symbol] = value

        cl.addWidget(QLabel('Noise level'))
        self.noise = QSlider(Qt.Horizontal)
        self.noise.setRange(0, 50)
        self.noise.setValue(8)
        self.noise_value = QLabel('0.8%')
        self.noise.valueChanged.connect(lambda v: self.noise_value.setText(f'{v / 10:.1f}%'))
        nr = QHBoxLayout()
        nr.addWidget(self.noise, 1)
        nr.addWidget(self.noise_value)
        cl.addLayout(nr)

        self.generate_btn = QPushButton('Generate & Analyze')
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

        self.status = QLabel('Adjust the inputs, then generate a spectrum.')
        self.status.setWordWrap(True)
        cl.addWidget(self.status)
        note = QLabel(
            'Scientific note: line depth also depends on temperature, ionization and atmospheric conditions. '
            'This simplified model demonstrates detection; it is not a real abundance solver.'
        )
        note.setWordWrap(True)
        note.setStyleSheet('color:#e8c04f;font-size:11px;')
        cl.addWidget(note)
        cl.addStretch(1)
        body.addWidget(controls)

        right = QVBoxLayout()
        body.addLayout(right, 1)
        plot_card = card_frame()
        pl = QVBoxLayout(plot_card)
        self.canvas = MplCanvas(figsize=(8, 4.6))
        # Split the visualization into the synthetic spectrum and a compact
        # normalized-composition bar chart, using the same dark figure theme.
        self.canvas.fig.clear()
        self.canvas.ax = self.canvas.fig.add_subplot(121)
        self.composition_ax = self.canvas.fig.add_subplot(122)
        from visualization.theme import apply_dark_theme
        apply_dark_theme(self.canvas.fig, [self.canvas.ax, self.composition_ax])
        self.canvas.fig.subplots_adjust(left=0.08, right=0.98, bottom=0.17, top=0.88, wspace=0.32)
        pl.addWidget(self.canvas)
        right.addWidget(plot_card, 2)

        table_card = card_frame()
        tl = QVBoxLayout(table_card)
        tl.addWidget(section_header('Composition Summary'))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ['Element', 'Simulated abundance', 'Lines detected', 'Mean line depth', 'Status', 'Line source']
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        tl.addWidget(self.table)
        right.addWidget(table_card, 1)
        self._generate()

    def _generate(self):
        abundances = {symbol: slider.value() for symbol, slider in self.sliders.items()}
        if sum(abundances.values()) == 0:
            QMessageBox.warning(self, 'Composition required', 'Set at least one element above zero.')
            return
        self._challenge_active = False
        self._challenge_truth = None
        self._challenge_revealed = False
        self.reveal_btn.setEnabled(False)
        self._render_spectrum(abundances, random_seed=7, reveal_abundances=True)

    def _load_mystery_star(self):
        # Cycle through preset compositions so repeated demos remain predictable.
        previous = getattr(self, '_mystery_index', -1)
        self._mystery_index = (previous + 1) % len(MYSTERY_PRESETS)
        self._challenge_truth = dict(MYSTERY_PRESETS[self._mystery_index])
        self._challenge_active = True
        self._challenge_revealed = False
        self.reveal_btn.setEnabled(True)
        self._render_spectrum(self._challenge_truth, random_seed=40 + self._mystery_index,
                              reveal_abundances=False)
        self.status.setText(
            'Mystery star loaded. Use the detected reference-line patterns to infer its composition, '
            'then reveal the simulated answer. This is a synthetic educational challenge.'
        )

    def _reveal_solution(self):
        if not self._challenge_active or self._challenge_truth is None:
            return
        self._challenge_revealed = True
        self._update_composition_chart(reveal_abundances=True)
        self._fill_table(reveal_abundances=True)
        self.status.setText('Solution revealed. Values are the hidden synthetic inputs, not inferred measurements.')
        self.reveal_btn.setEnabled(False)

    def _render_spectrum(self, abundances, random_seed=7, reveal_abundances=True):
        try:
            wl = build_wavelength_grid(380, 700, 8000)
            self.current = generate_composition_spectrum(
                wl, abundances, noise_level=self.noise.value() / 1000,
                random_seed=random_seed,
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, 'Could not generate spectrum', str(exc))
            return

        self.canvas.ax.clear()
        self.canvas.ax.plot(self.current.wavelength_nm, self.current.intensity,
                            lw=1.0, label='Synthetic stellar spectrum')
        self.canvas.ax.plot(self.current.wavelength_nm, self.current.continuum,
                            lw=1.0, alpha=.7, label='Continuum')
        self.canvas.ax.set_xlabel('Wavelength (nm)')
        self.canvas.ax.set_ylabel('Normalized intensity')
        self.canvas.ax.set_title('Synthetic Spectrum')
        self.canvas.ax.legend(loc='best', fontsize=8)

        self._update_composition_chart(reveal_abundances=reveal_abundances)
        self.canvas.redraw()
        self._fill_table(reveal_abundances=reveal_abundances)
        if not self._challenge_active:
            detected = [r['symbol'] for r in summarize_composition(self.current) if r['lines_detected']]
            self.status.setText('Detected line patterns: ' +
                                (', '.join(detected) if detected else 'none above the noise threshold') +
                                '\nAbundances are normalized simulation inputs.')

    def _update_composition_chart(self, reveal_abundances: bool):
        """Draw abundance bars only when showing them is allowed.

        The Mystery Star Challenge must not leak its hidden answer through a
        visualization while the table is masking the same values.
        """
        from visualization.theme import apply_dark_theme

        self.composition_ax.clear()
        apply_dark_theme(self.canvas.fig, [self.canvas.ax, self.composition_ax])
        self.composition_ax.set_ylabel('Relative abundance (%)')
        self.composition_ax.grid(axis='x', visible=False)
        if self._challenge_active and not reveal_abundances:
            self.composition_ax.set_title('Mystery Composition')
            self.composition_ax.text(0.5, 0.5, 'Composition hidden\nReveal the solution to view values',
                                     ha='center', va='center', transform=self.composition_ax.transAxes,
                                     color='#c9d3e6', wrap=True)
            self.composition_ax.set_xticks([])
            self.composition_ax.set_yticks([])
        else:
            rows = summarize_composition(self.current)
            symbols = [row['symbol'] for row in rows]
            percentages = [row['abundance_percent'] for row in rows]
            bars = self.composition_ax.bar(symbols, percentages)
            self.composition_ax.set_title('Input Composition')
            self.composition_ax.set_ylim(0, max(10.0, max(percentages, default=0) * 1.18))
            for bar, value in zip(bars, percentages):
                self.composition_ax.text(
                    bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                    f'{value:.1f}%', ha='center', va='bottom', fontsize=8, color='#c9d3e6'
                )
        self.canvas.fig.subplots_adjust(left=0.08, right=0.98, bottom=0.17, top=0.86, wspace=0.32)

    def _fill_table(self, reveal_abundances: bool):
        if self.current is None:
            return
        rows = summarize_composition(self.current)
        self.table.setRowCount(len(rows))
        hide_solution = self._challenge_active and not self._challenge_revealed
        for i, row in enumerate(rows):
            abundance = f"{row['abundance_percent']:.1f}%" if reveal_abundances and not hide_solution else 'Hidden'
            line_count = f"{row['lines_detected']} / {row['lines_checked']}" if not hide_solution else 'Hidden'
            mean_depth = f"{row['mean_line_depth_percent']:.1f}%" if not hide_solution else 'Hidden'
            status = row['status'] if not hide_solution else 'Hidden'
            vals = [f"{row['name']} ({row['symbol']})", abundance,
                    line_count, mean_depth, status, row['source']]
            for j, val in enumerate(vals):
                self.table.setItem(i, j, QTableWidgetItem(val))

    def _export_csv(self):
        if self.current is None:
            QMessageBox.warning(self, 'No analysis', 'Generate a spectrum before exporting.')
            return
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export Composition Analysis', 'stellar_composition_analysis.csv', 'CSV Files (*.csv)'
        )
        if not path:
            return
        try:
            with open(Path(path), 'w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(['# Synthetic stellar composition analysis'])
                writer.writerow(['# Abundances are simulation inputs, not inferred astrophysical measurements'])
                writer.writerow(['Element', 'Simulated abundance (%)', 'Lines detected', 'Lines checked', 'Mean line depth (%)', 'Status', 'Line source'])
                hide_solution = self._challenge_active and not self._challenge_revealed
                for row in summarize_composition(self.current):
                    if hide_solution:
                        writer.writerow([row['name'], 'Hidden', 'Hidden', 'Hidden', 'Hidden', 'Hidden', row['source']])
                    else:
                        writer.writerow([row['name'], row['abundance_percent'], row['lines_detected'], row['lines_checked'], row['mean_line_depth_percent'], row['status'], row['source']])
                writer.writerow([])
                writer.writerow(['Wavelength (nm)', 'Synthetic intensity', 'Continuum'])
                writer.writerows(zip(self.current.wavelength_nm, self.current.intensity, self.current.continuum))
        except OSError as exc:
            QMessageBox.warning(self, 'Export failed', f'Could not write the CSV file:\n{exc}')
            return
        QMessageBox.information(self, 'Export complete', f'Analysis exported to:\n{path}')
