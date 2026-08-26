"""
app.ui.theory_page
======================

Brief section 21: the educational reference section. Each topic gets a
concise explanation, the governing equation where one applies, why it
matters for the project's story, and a pointer to the interactive page
where the student can see that exact physics computed live. This page
is pure static content -- it renders text, it does not perform any
physics calculation itself.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.widgets.common import card_frame, page_header, section_header

# Each topic: (title, HTML body, linked page key or None, link button text)
TOPICS = [
    (
        "1. Quantization",
        "<p>A hydrogen atom's electron cannot have just any energy. Bound-state energy is "
        "restricted to a discrete ladder of allowed values, indexed by an integer "
        "<i>n</i> = 1, 2, 3, &hellip; This is the central departure from classical physics: "
        "orbits are not continuously variable, they are quantized.</p>",
        None, None,
    ),
    (
        "2. Hydrogen Energy Levels",
        "<p>Solving the Schr&ouml;dinger equation (or, equivalently, the Bohr model) for a "
        "single electron bound to a single proton gives:</p>"
        "<p style='font-size:15px; color:#4fd1e8;'>E<sub>n</sub> = &minus;13.6 eV / n&sup2;</p>"
        "<p>Energies are negative because they're measured relative to the ionization limit "
        "(E = 0, a free electron at rest infinitely far from the nucleus). The 13.6&nbsp;eV "
        "constant is the Rydberg energy, derived here from CODATA fundamental constants "
        "with the electron&ndash;proton reduced-mass correction &mdash; it is never hard-coded "
        "as a literal 13.6 in this application.</p>",
        "energy_levels", "Open Energy Levels →",
    ),
    (
        "3. Electron Transitions",
        "<p>An electron can jump between allowed levels. Falling from a higher level "
        "n<sub>i</sub> to a lower one n<sub>f</sub> releases a photon (emission); being "
        "promoted from a lower level to a higher one requires absorbing a photon of "
        "exactly matching energy (absorption). Both directions are the same physics run "
        "in opposite directions.</p>",
        "energy_levels", "Try a Transition →",
    ),
    (
        "4. Photon Energy",
        "<p>Energy is conserved: the photon emitted or absorbed carries exactly the energy "
        "gap between the two levels.</p>"
        "<p style='font-size:15px; color:#4fd1e8;'>&Delta;E = |E<sub>i</sub> &minus; E<sub>f</sub>|</p>",
        "energy_levels", "Calculate ΔE →",
    ),
    (
        "5. Wavelength",
        "<p>A photon's energy sets its wavelength through Planck's relation, rearranged "
        "using the speed of light c:</p>"
        "<p style='font-size:15px; color:#4fd1e8;'>&lambda; = hc / &Delta;E</p>"
        "<p>This <i>vacuum</i> wavelength is the fundamental quantity. What a lab spectrometer "
        "or telescope actually reports is usually the very slightly shorter <i>standard-air</i> "
        "wavelength, since light travels marginally slower through air than vacuum. Both are "
        "shown side by side everywhere in this app so the distinction is never hidden.</p>",
        "energy_levels", "See Both Wavelengths →",
    ),
    (
        "6. The Rydberg Equation",
        "<p>Combining the energy-level formula with &lambda; = hc/&Delta;E reproduces the "
        "19th-century empirical Rydberg formula that was discovered from lab spectra decades "
        "before quantum mechanics explained <i>why</i> it worked:</p>"
        "<p style='font-size:15px; color:#4fd1e8;'>1/&lambda; = R<sub>H</sub> (1/n<sub>f</sub>&sup2; "
        "&minus; 1/n<sub>i</sub>&sup2;)</p>"
        "<p>This app never uses the classical Rydberg formula directly &mdash; it derives the "
        "same physics from first-principles energy levels, which is more fundamental and "
        "automatically includes the reduced-mass correction.</p>",
        None, None,
    ),
    (
        "7. Spectral Series",
        "<p>Transitions that share the same final level n<sub>f</sub> form a named family: "
        "Lyman (n<sub>f</sub>=1, ultraviolet), Balmer (n<sub>f</sub>=2, visible &mdash; the "
        "famous one), Paschen (n<sub>f</sub>=3), Brackett (n<sub>f</sub>=4), and Pfund "
        "(n<sub>f</sub>=5), the last three all infrared. Balmer is the only series with lines "
        "in visible light, which is why it dominates ground-based stellar hydrogen "
        "detection.</p>",
        "spectrum_simulator", "Generate a Series →",
    ),
    (
        "8. Emission Spectra",
        "<p>A hot, low-density gas (like an excited hydrogen lamp) emits light only at its "
        "characteristic transition wavelengths &mdash; a set of bright lines on an otherwise "
        "dark background. Each line's position is fixed by physics; nothing about its "
        "wavelength is a free parameter.</p>",
        "spectrum_simulator", "Simulate Emission →",
    ),
    (
        "9. Absorption Spectra",
        "<p>Shine a broad continuum of light (like a star's blackbody-ish continuum) through "
        "cooler hydrogen gas, and atoms absorb photons at those exact same characteristic "
        "wavelengths, removing them from the beam. The result is a continuous spectrum with "
        "dark dips at the same positions the emission lines would occupy. This is precisely "
        "how hydrogen is detected in starlight &mdash; we see it in absorption, not "
        "emission.</p>",
        "spectrum_simulator", "Simulate Absorption →",
    ),
    (
        "10. Stellar Spectroscopy",
        "<p>A star's outer, cooler photosphere sits in front of the hotter interior's "
        "continuum radiation, so its spectrum shows absorption lines from whatever elements "
        "are present in that outer layer. Matching an observed dark line's wavelength to a "
        "known transition tells you which element produced it &mdash; this app's whole "
        "story, end to end, is doing exactly that for hydrogen.</p>",
        "stellar_analysis", "Analyze a Star →",
    ),
    (
        "11. Doppler Shift",
        "<p>If the star is moving toward or away from the observer along the line of sight, "
        "every one of its spectral lines shifts in wavelength:</p>"
        "<p style='font-size:15px; color:#4fd1e8;'>&Delta;&lambda; / &lambda; = v / c</p>"
        "<p>A receding star (v &gt; 0) redshifts its lines to longer wavelengths; an "
        "approaching star blueshifts them shorter. This is exactly why the stellar analyzer "
        "has to <i>search</i> near each expected hydrogen wavelength rather than checking one "
        "fixed value.</p>",
        "stellar_analysis", "Shift a Spectrum →",
    ),
    (
        "12. Semiconductor Connection",
        "<p>This project sits in a Physics of Semiconductor Devices course for a reason: a "
        "semiconductor's conduction and valence bands are, like hydrogen's energy levels, a "
        "set of quantized allowed electron energies separated by a gap. An electron dropping "
        "across that gap in an LED or laser diode emits a photon whose energy sets its "
        "color, exactly as an electron dropping from n=3 to n=2 in hydrogen emits a "
        "656&nbsp;nm photon. A photodetector runs the process in reverse, absorbing photons "
        "to promote electrons across the gap &mdash; the semiconductor analogue of "
        "absorption spectroscopy. Quantum wells go a step further, adding an engineered "
        "confinement that produces genuinely discrete sub-levels within a band, closer still "
        "to the atomic picture.</p>"
        "<p style='color:#7c869c;'>The analogy is conceptual, not an identity: hydrogen's "
        "levels come from a single electron bound to a bare proton, while a semiconductor's "
        "bands come from many atoms' orbitals overlapping in a crystal lattice. The "
        "underlying idea &mdash; quantized states, transitions, and photons of definite "
        "energy &mdash; is the same; the microscopic origin is not.</p>",
        None, None,
    ),
]


class TheoryPage(QWidget):
    def __init__(self, navigate_callback, parent=None):
        super().__init__(parent)
        self.navigate = navigate_callback

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(10)
        root.addWidget(page_header(
            "Theory / Learn",
            "The physics behind every number this application computes, from a single "
            "quantized electron to a stellar hydrogen fingerprint.",
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, stretch=1)

        list_card = card_frame()
        list_card.setMaximumWidth(260)
        list_layout = QVBoxLayout(list_card)
        list_layout.addWidget(section_header("Topics"))
        self.topic_list = QListWidget()
        for title, _body, _key, _btn in TOPICS:
            self.topic_list.addItem(title)
        self.topic_list.currentRowChanged.connect(self._on_topic_changed)
        list_layout.addWidget(self.topic_list)
        body.addWidget(list_card)

        content_card = card_frame()
        content_layout = QVBoxLayout(content_card)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        content_layout.addWidget(self.browser, stretch=1)

        self.link_btn = QPushButton("")
        self.link_btn.setObjectName("accentButton")
        self.link_btn.clicked.connect(self._on_link_clicked)
        self.link_btn.hide()
        content_layout.addWidget(self.link_btn)

        body.addWidget(content_card, stretch=1)

        self.topic_list.setCurrentRow(0)

    def _on_topic_changed(self, row: int):
        if row < 0:
            return
        title, body, page_key, btn_text = TOPICS[row]
        self.browser.setHtml(f"<h2 style='color:#f2f5fb;'>{title}</h2>{body}")
        self._linked_page = page_key
        if page_key and btn_text:
            self.link_btn.setText(btn_text)
            self.link_btn.show()
        else:
            self.link_btn.hide()

    def _on_link_clicked(self):
        if getattr(self, "_linked_page", None):
            self.navigate(self._linked_page)
