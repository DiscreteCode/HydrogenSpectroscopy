"""
app.paths
=========

Single source of truth for resolving runtime resource paths (the Qt
stylesheet, bundled sample spectra, and anything else shipped alongside
the code) in a way that works identically in two situations:

1. Running from source:      python main.py
2. Running frozen:            HydrogenSpectroscopy.exe  (PyInstaller)

When PyInstaller freezes the app, ``sys.frozen`` is set to True and
``sys._MEIPASS`` points at the directory the bundle was extracted/laid
out into (for a onedir build this is the ``_internal`` folder next to
the executable). Source files are no longer laid out at their original
repository-relative locations relative to ``__file__`` in the way they
are when running from source, so any path built from
``Path(__file__).resolve().parents[N]`` silently breaks once frozen.

Every other module that needs a bundled resource should import
``resource_path`` from here rather than re-deriving its own
``Path(__file__)`` chain -- that scattering is exactly what the release
checklist calls out as a packaging risk.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _app_root() -> Path:
    """Root directory to resolve bundled resources against.

    Frozen (PyInstaller): ``sys._MEIPASS`` -- the extracted/onedir
    bundle root, which mirrors the project's top-level layout because
    the .spec's ``datas`` entries are declared with that same
    relative layout (see HydrogenSpectroscopy.spec).

    Source: the repository root, i.e. the directory containing this
    ``app/`` package (one level up from this file).
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return Path(__file__).resolve().parent.parent


APP_ROOT: Path = _app_root()


def resource_path(*parts: str) -> Path:
    """Resolve a resource path relative to the application root, e.g.

        resource_path("app", "resources", "style.qss")
        resource_path("data", "sample_spectra")

    Works identically whether running from source or as a frozen
    PyInstaller build.
    """
    return APP_ROOT.joinpath(*parts)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
