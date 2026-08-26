"""
spectroscopy.io_utils
=======================

CSV import for user-supplied stellar spectra (brief section 24) and
export helpers for spectra / detection reports (brief section 25).
Deliberately dependency-light (stdlib csv + numpy only) with tolerant
column-name auto-detection, since the whole point is that a
non-technical user's CSV should "just work" without them needing to
know exact column names.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import numpy.typing as npt

_WAVELENGTH_ALIASES = {"wavelength", "wavelength_nm", "wave", "lambda", "nm", "wl"}
_INTENSITY_ALIASES = {"intensity", "flux", "counts", "signal", "value", "amplitude"}


class SpectrumImportError(ValueError):
    """Raised for any malformed/unreadable spectrum file, always with
    a message safe to show directly to a non-technical user."""


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t ").delimiter
    except csv.Error:
        return ","


def _find_column(header: list[str], aliases: set[str]) -> int | None:
    normalized = [h.strip().lower().replace(" ", "_") for h in header]
    for i, name in enumerate(normalized):
        if name in aliases:
            return i
    # loose substring fallback
    for i, name in enumerate(normalized):
        if any(alias in name for alias in aliases):
            return i
    return None


def load_spectrum_csv(
    path: str | Path,
    wavelength_col: str | int | None = None,
    intensity_col: str | int | None = None,
) -> tuple[npt.NDArray[np.floating], npt.NDArray[np.floating], list[str]]:
    """Load a two-column (or more) wavelength/intensity spectrum from
    a CSV/TXT/TSV file. Returns (wavelength_nm, intensity, header).

    Column selection:
    - If wavelength_col / intensity_col are given as strings, matched
      by (case-insensitive) header name.
    - If given as ints, used as direct column indices.
    - If left as None, auto-detected from common header names
      ('wavelength', 'nm', 'flux', 'intensity', etc.), falling back to
      "first two numeric columns" if no header is recognized.

    Raises SpectrumImportError with a human-readable message on any
    problem -- this is the boundary the GUI relies on to show a clean
    QMessageBox instead of a raw traceback.
    """
    path = Path(path)
    if not path.exists():
        raise SpectrumImportError(f"File not found: {path}")

    try:
        raw_text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise SpectrumImportError(f"Could not read file: {exc}") from exc

    if not raw_text.strip():
        raise SpectrumImportError("The file is empty.")

    delimiter = _sniff_delimiter(raw_text[:2048])
    lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    reader = csv.reader(lines, delimiter=delimiter)
    rows = list(reader)
    if len(rows) < 2:
        raise SpectrumImportError("The file needs at least a header row and one data row.")

    first_row = rows[0]

    def _row_is_numeric(row: list[str]) -> bool:
        try:
            [float(cell) for cell in row]
            return True
        except ValueError:
            return False

    has_header = not _row_is_numeric(first_row)
    header = first_row if has_header else [f"col{i}" for i in range(len(first_row))]
    data_rows = rows[1:] if has_header else rows

    # Resolve column indices.
    def _resolve(col, aliases, default_index):
        if col is None:
            idx = _find_column(header, aliases)
            return idx if idx is not None else default_index
        if isinstance(col, int):
            return col
        idx = _find_column(header, {col.strip().lower()})
        if idx is None:
            raise SpectrumImportError(f"Column '{col}' not found in file header: {header}")
        return idx

    wl_idx = _resolve(wavelength_col, _WAVELENGTH_ALIASES, default_index=0)
    int_idx = _resolve(intensity_col, _INTENSITY_ALIASES, default_index=1 if len(header) > 1 else 0)

    if wl_idx == int_idx:
        raise SpectrumImportError(
            "Could not tell the wavelength and intensity columns apart -- "
            "please specify them explicitly."
        )

    wavelengths: list[float] = []
    intensities: list[float] = []
    for row_num, row in enumerate(data_rows, start=2):
        if len(row) <= max(wl_idx, int_idx):
            continue  # skip short/malformed rows rather than crash
        try:
            w = float(row[wl_idx])
            i = float(row[int_idx])
        except ValueError:
            continue  # skip non-numeric rows (blank lines, comments, etc.)
        wavelengths.append(w)
        intensities.append(i)

    if len(wavelengths) < 5:
        raise SpectrumImportError(
            "Fewer than 5 valid numeric data rows were found. Check that the file "
            "has wavelength and intensity columns with numeric values."
        )

    wl_arr = np.array(wavelengths, dtype=float)
    int_arr = np.array(intensities, dtype=float)

    order = np.argsort(wl_arr)
    wl_arr, int_arr = wl_arr[order], int_arr[order]

    if wl_arr.min() <= 0:
        raise SpectrumImportError("Wavelength values must be positive.")

    return wl_arr, int_arr, header


def export_spectrum_csv(path: str | Path, wavelength_nm, intensity) -> None:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["wavelength_nm", "intensity"])
        for w, i in zip(wavelength_nm, intensity):
            writer.writerow([f"{w:.4f}", f"{i:.6f}"])


def export_detection_results_csv(path: str | Path, results) -> None:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["label", "n_initial", "n_final", "expected_air_nm", "observed_nm",
             "difference_nm", "matched", "confidence"]
        )
        for r in results:
            writer.writerow(
                [
                    r.label,
                    r.n_initial,
                    r.n_final,
                    f"{r.expected_air_nm:.4f}",
                    f"{r.observed_nm:.4f}" if r.observed_nm is not None else "",
                    f"{r.difference_nm:+.4f}" if r.difference_nm is not None else "",
                    "YES" if r.matched else "NO",
                    f"{r.confidence:.2f}",
                ]
            )


def export_detection_report_txt(path: str | Path, summary, star_label: str = "Observed Star") -> None:
    path = Path(path)
    lines = [
        "HYDROGEN SPECTRUM DETECTION REPORT",
        "=" * 40,
        f"Target: {star_label}",
        "",
    ]
    for r in summary.results:
        lines.append(r.label)
        lines.append(f"  Expected : {r.expected_air_nm:.2f} nm")
        if r.observed_nm is not None:
            lines.append(f"  Observed : {r.observed_nm:.2f} nm")
            lines.append(f"  Difference: {r.difference_nm:+.2f} nm")
        else:
            lines.append("  Observed : (no feature found)")
        lines.append(f"  Match    : {'YES' if r.matched else 'NO'}  (confidence {r.confidence:.2f})")
        lines.append("")
    lines.append("-" * 40)
    lines.append(summary.message)
    path.write_text("\n".join(lines), encoding="utf-8")
