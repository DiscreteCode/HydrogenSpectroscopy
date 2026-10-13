"""
app.ui.main_window
=====================

The application shell (brief section 3): a persistent sidebar with one
button per top-level section, driving a QStackedWidget that holds the
actual pages. This is the only place that knows about every page class
and owns the single shared AppState instance -- individual pages only
ever see the state object and (for the Dashboard) a navigate callback,
never each other.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.app_state import AppState
from app.ui.about_page import AboutPage
from app.ui.dashboard_page import DashboardPage
from app.ui.element_identification_page import ElementIdentificationPage
from app.ui.composition_page import CompositionPage
from app.ui.energy_levels_page import EnergyLevelsPage
from app.ui.spectrum_simulator_page import SpectrumSimulatorPage
from app.ui.stellar_analysis_page import StellarAnalysisPage
from app.ui.theory_page import TheoryPage

# (nav label, internal page key, factory taking app_state+navigate)
NAV_SECTIONS = [
    ("Dashboard", "dashboard"),
    ("Energy Levels && Transitions", "energy_levels"),
    ("Spectrum Simulator", "spectrum_simulator"),
    ("Stellar Spectrum && Analysis", "stellar_analysis"),
    ("Element Identification", "element_id"),
    ("Stellar Composition", "composition"),
    ("Theory / Learn", "theory"),
    ("About / References", "about"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hydrogen Quantum Spectroscopy")
        self.resize(1280, 820)
        self.setMinimumSize(1000, 680)

        self.app_state = AppState()

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Sidebar ---
        sidebar = QWidget()
        sidebar.setObjectName("navSidebar")
        sidebar.setFixedWidth(232)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 8)
        side_layout.setSpacing(2)

        title = QLabel("HYDROGEN\nSPECTROSCOPY")
        title.setObjectName("navTitle")
        side_layout.addWidget(title)
        subtitle = QLabel("Quantum simulations of stellar hydrogen lines")
        subtitle.setObjectName("navSubtitle")
        subtitle.setWordWrap(True)
        side_layout.addWidget(subtitle)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons: dict[str, QPushButton] = {}
        for label, key in NAV_SECTIONS:
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, k=key: self.navigate(k))
            self._nav_group.addButton(btn)
            self._nav_buttons[key] = btn
            side_layout.addWidget(btn)

        side_layout.addStretch(1)
        root.addWidget(sidebar)

        # --- Page stack ---
        self.stack = QStackedWidget()
        root.addWidget(self.stack, stretch=1)

        self._page_index: dict[str, int] = {}
        self._build_pages()

        self.statusBar().showMessage(
            "Hydrogen transitions are computed live; He, Na, Ca and Fe use labeled reference lines."
        )

        self.navigate("dashboard")

    def _build_pages(self):
        pages = [
            ("dashboard", DashboardPage(self.app_state, self.navigate)),
            ("energy_levels", EnergyLevelsPage(self.app_state)),
            ("spectrum_simulator", SpectrumSimulatorPage(self.app_state)),
            ("stellar_analysis", StellarAnalysisPage()),
            ("element_id", ElementIdentificationPage()),
            ("composition", CompositionPage()),
            ("theory", TheoryPage(self.navigate)),
            ("about", AboutPage()),
        ]
        for key, widget in pages:
            self._page_index[key] = self.stack.addWidget(widget)

    def navigate(self, page_key: str):
        if page_key not in self._page_index:
            return
        self.stack.setCurrentIndex(self._page_index[page_key])
        btn = self._nav_buttons.get(page_key)
        if btn is not None:
            btn.setChecked(True)
