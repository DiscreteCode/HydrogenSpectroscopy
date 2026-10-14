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

class CompositionPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = None
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
        self.export_btn = QPushButton('Export Analysis CSV')
        self.export_btn.clicked.connect(self._export_csv)
        cl.addWidget(self.export_btn)

        self.status = QLabel('Adjust the inputs, then generate a spectrum.')
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            'padding: 10px; border-radius: 8px; background-color: #131a2b; '
            'color: #97a3ba; border: 1px solid #2b354b; font-size: 11px;'
        )
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
        self._render_spectrum(abundances, random_seed=7)

    def _render_spectrum(self, abundances, random_seed=7):
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

        detected = [r['symbol'] for r in summarize_composition(self.current) if r['lines_detected']]
        self._update_composition_chart()
        self.canvas.redraw()
        self._fill_table()
        if detected:
            self.status.setText(
                f"DETECTION STATUS · {len(detected)} of {len(ELEMENT_DEFAULTS)} element patterns found\n"
                f"Detected: {', '.join(detected)}\n"
                "Abundances are normalized simulation inputs, not measured stellar abundances."
            )
            self.status.setStyleSheet(
                'padding: 10px; border-radius: 8px; background-color: #12331f; '
                'color: #39d98a; border: 1px solid #39d98a; font-size: 11px;'
            )
        else:
            self.status.setText(
                "DETECTION STATUS · No clear element patterns detected above the noise threshold.\n"
                "Try reducing noise or adjusting the simulated element weights."
            )
            self.status.setStyleSheet(
                'padding: 10px; border-radius: 8px; background-color: #332c12; '
                'color: #e8c04f; border: 1px solid #e8c04f; font-size: 11px;'
            )

    def _update_composition_chart(self):
        from visualization.theme import apply_dark_theme

        self.composition_ax.clear()
        apply_dark_theme(self.canvas.fig, [self.canvas.ax, self.composition_ax])
        self.composition_ax.set_ylabel('Relative abundance (%)')
        self.composition_ax.grid(axis='x', visible=False)
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

    def _fill_table(self):
        if self.current is None:
            return
        rows = summarize_composition(self.current)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            vals = [f"{row['name']} ({row['symbol']})",
                    f"{row['abundance_percent']:.1f}%",
                    f"{row['lines_detected']} / {row['lines_checked']}",
                    f"{row['mean_line_depth_percent']:.1f}%",
                    row['status'], row['source']]
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
                for row in summarize_composition(self.current):
                    writer.writerow([row['name'], row['abundance_percent'], row['lines_detected'], row['lines_checked'], row['mean_line_depth_percent'], row['status'], row['source']])
                writer.writerow([])
                writer.writerow(['Wavelength (nm)', 'Synthetic intensity', 'Continuum'])
                writer.writerows(zip(self.current.wavelength_nm, self.current.intensity, self.current.continuum))
        except OSError as exc:
            QMessageBox.warning(self, 'Export failed', f'Could not write the CSV file:\n{exc}')
            return
        QMessageBox.information(self, 'Export complete', f'Analysis exported to:\n{path}')
