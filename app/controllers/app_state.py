"""
app.controllers.app_state
============================

A small shared-state object, not a heavyweight MVC framework -- this
app has one meaningful piece of cross-page state (the currently
selected/accumulated transitions) and giving it its own controller
class would be architectural overhead for no real benefit. Pages read
and write this directly and connect to its Qt signals when they need
to react live (e.g. the Dashboard showing "last calculated: 3->2,
656.3 nm").
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from physics.transitions import Transition


class AppState(QObject):
    transition_changed = Signal(object)      # emits the new Transition
    spectrum_lines_changed = Signal()         # emitted when the custom-lines list changes

    def __init__(self):
        super().__init__()
        self.current_transition: Transition | None = None
        self.custom_transitions: list[Transition] = []

    def set_current_transition(self, transition: Transition) -> None:
        self.current_transition = transition
        self.transition_changed.emit(transition)

    def add_transition_to_spectrum(self, transition: Transition) -> None:
        self.custom_transitions.append(transition)
        self.spectrum_lines_changed.emit()

    def clear_custom_transitions(self) -> None:
        self.custom_transitions.clear()
        self.spectrum_lines_changed.emit()
