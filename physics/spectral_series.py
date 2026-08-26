"""
physics.spectral_series
========================

The named hydrogen spectral series are simply groupings of transitions
that share the same final quantum level n_final:

    Lyman     -> n_final = 1   (Ultraviolet)
    Balmer    -> n_final = 2   (Visible -- the famous one)
    Paschen   -> n_final = 3   (Infrared)
    Brackett  -> n_final = 4   (Infrared)
    Pfund     -> n_final = 5   (Infrared)

This module owns that mapping and the logic for listing every
transition in a given series. It intentionally does NOT import
``physics.transitions`` at module scope, because ``transitions`` imports
``identify_series`` from here -- the lazy import inside
``get_series_transitions`` breaks that circular dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from physics.transitions import Transition

SERIES_BY_FINAL_N: dict[int, str] = {
    1: "Lyman",
    2: "Balmer",
    3: "Paschen",
    4: "Brackett",
    5: "Pfund",
}

FINAL_N_BY_SERIES: dict[str, int] = {name: n for n, name in SERIES_BY_FINAL_N.items()}


@dataclass(frozen=True)
class SeriesInfo:
    name: str
    n_final: int
    discoverer_note: str


SERIES_INFO: dict[str, SeriesInfo] = {
    "Lyman": SeriesInfo("Lyman", 1, "Theodore Lyman, 1906 (ultraviolet)"),
    "Balmer": SeriesInfo("Balmer", 2, "Johann Balmer, 1885 (visible light)"),
    "Paschen": SeriesInfo("Paschen", 3, "Friedrich Paschen, 1908 (infrared)"),
    "Brackett": SeriesInfo("Brackett", 4, "Frederick Brackett, 1922 (infrared)"),
    "Pfund": SeriesInfo("Pfund", 5, "August Pfund, 1924 (infrared)"),
}


def list_series_names() -> list[str]:
    return list(SERIES_BY_FINAL_N.values())


def get_series_final_n(series_name: str) -> int:
    try:
        return FINAL_N_BY_SERIES[series_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown spectral series '{series_name}'. "
            f"Known series: {list_series_names()}"
        ) from exc


def identify_series(n_final: int) -> str | None:
    """Return the classical series name for a given final quantum level,
    or None if n_final doesn't correspond to one of the five named
    series (still physically valid, just unnamed in most textbooks)."""
    return SERIES_BY_FINAL_N.get(n_final)


def get_series_transitions(series_name: str, n_i_max: int) -> "list[Transition]":
    """Return every emission transition in the named series, from the
    series' n_final+1 up to n_i_max, computed via the physics engine
    (never hard-coded).

    Example: get_series_transitions("Balmer", 6) returns the four
    transitions 3->2, 4->2, 5->2, 6->2.
    """
    from physics.transitions import compute_emission_transition  # local import: breaks cycle

    n_final = get_series_final_n(series_name)
    if n_i_max <= n_final:
        raise ValueError(
            f"n_i_max ({n_i_max}) must be greater than the {series_name} "
            f"series' final level (n_final={n_final})"
        )
    return [
        compute_emission_transition(n_initial, n_final)
        for n_initial in range(n_final + 1, n_i_max + 1)
    ]
