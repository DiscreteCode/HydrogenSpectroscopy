"""
app.ui.about_page
=====================

Brief section 22: static project information -- purpose, technology,
scientific scope, honest limitations, and the references the physics
engine actually cites (see physics/constants.py). No content here is
invented; every reference listed also appears in the module that uses
it.
"""

from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from app.widgets.common import card_frame, page_header

ABOUT_HTML = """
<h2 style='color:#f2f5fb;'>Unveiling Stellar Composition Through Quantum Simulations
of Hydrogen Spectral Lines</h2>

<p style='color:#7c869c;'>Physics of Semiconductor Devices / ECM course project &mdash;
desktop application built with Python and PySide6.</p>

<h3 style='color:#9d7ce8;'>Purpose</h3>
<p>This application demonstrates, end to end and with a real (if simplified) working
pipeline, how a single physical idea &mdash; the quantization of a bound electron's
energy &mdash; leads all the way to identifying an element in a star millions of
kilometers away. Starting from E<sub>n</sub> = &minus;13.6&nbsp;eV/n&sup2;, it computes
electron transitions, the photon each one releases, that photon's wavelength in vacuum
and standard air, the resulting spectral fingerprint, and finally searches a simulated
(or imported) stellar spectrum for that fingerprint to report a hydrogen detection
verdict.</p>

<h3 style='color:#9d7ce8;'>Technology</h3>
<ul>
<li><b>Physics engine</b> (<code>physics/</code>) &mdash; NumPy/SciPy, CODATA constants</li>
<li><b>Spectroscopy pipeline</b> (<code>spectroscopy/</code>) &mdash; synthetic spectrum
generation, peak detection, hydrogen line matching</li>
<li><b>Visualization</b> (<code>visualization/</code>) &mdash; Matplotlib, dark
scientific-instrument theme</li>
<li><b>Desktop GUI</b> (<code>app/</code>) &mdash; PySide6 (Qt for Python)</li>
</ul>

<h3 style='color:#9d7ce8;'>Scientific Scope</h3>
<p>Hydrogen's energy levels and hydrogen transition wavelengths are computed live from
the quantum model, rather than looked up from a hardcoded line table. Helium, sodium,
calcium and iron use clearly labeled reference wavelengths in the element-identification
and synthetic-composition demonstrations. Vacuum and standard-air wavelengths are
tracked separately where applicable. The Doppler shift uses the standard classical
formula (&Delta;&lambda;/&lambda; = v/c) by default, with an exact relativistic formula
also implemented.</p>

<h3 style='color:#e8c04f;'>Honest Limitations</h3>
<ul>
<li>The stellar spectrum simulator is an <b>educational model</b>, not a full
stellar-atmosphere radiative-transfer simulation. Its continuum is an illustrative
blackbody-style curve, not a precise stellar model atmosphere.</li>
<li>Line intensities use a simple illustrative n&sup3;-style falloff, not a real
oscillator-strength or LTE/non-LTE calculation.</li>
<li>Only hydrogen is quantum-mechanically computed. Helium, sodium, calcium, and iron
use a small, clearly labeled reference-line subset in the Element Identification and
Stellar Composition pages; their atomic transitions are not computed by this application.</li>
<li>The Stellar Composition Analyzer generates synthetic spectra from user-controlled
relative abundance weights. It does not infer real elemental concentrations from an
observed star. Line strengths also depend on temperature, ionization, and atmospheric
conditions, so the plotted percentages are simulation inputs rather than astrophysical
measurements.</li>
</ul>

<h3 style='color:#9d7ce8;'>References</h3>
<ul>
<li>CODATA 2018 recommended values of the fundamental physical constants
(via <code>scipy.constants</code>)</li>
<li>NIST Atomic Spectral Database &mdash; https://physics.nist.gov/PhysRefData/ASD/</li>
</ul>
"""


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header("About / References"))

        card = card_frame()
        card_layout = QVBoxLayout(card)
        browser = QTextBrowser()
        browser.setHtml(ABOUT_HTML)
        card_layout.addWidget(browser)
        root.addWidget(card, stretch=1)
