# -*- mode: python ; coding: utf-8 -*-
"""
HydrogenSpectroscopy.spec
==========================

PyInstaller build specification for the Hydrogen Quantum Spectroscopy
desktop app.

Build mode: ONEDIR (not onefile). A onedir build starts noticeably
faster (no self-extraction step on every launch) and is much easier to
debug if something is missing at runtime -- you can look straight into
dist/HydrogenSpectroscopy/ and see what did or didn't get bundled.
Onefile trades that away purely for a single-file download, which
isn't a priority here.

Run this on Windows (see build.bat) or via the windows-latest GitHub
Actions runner (see .github/workflows/windows-build.yml) -- PyInstaller
builds platform-native executables and cannot cross-compile a Windows
.exe from Linux/macOS.

    pyinstaller HydrogenSpectroscopy.spec

Output:

    dist/HydrogenSpectroscopy/HydrogenSpectroscopy.exe
    dist/HydrogenSpectroscopy/_internal/...   (PySide6, NumPy, SciPy,
                                                Matplotlib, Qt plugins,
                                                and the app's own
                                                bundled resources)

Resource resolution at runtime is handled by app/paths.py, which
checks sys.frozen / sys._MEIPASS -- the `datas` entries below are
declared with the same relative layout (app/resources/..., data/...)
that app/paths.py expects to find under sys._MEIPASS when frozen.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ---------------------------------------------------------------------
# Bundled data files
# ---------------------------------------------------------------------
# Each tuple is (source_path, destination_dir_inside_bundle). Keeping
# the destination directory identical to the source-tree layout is
# what lets app/paths.resource_path("app", "resources", "style.qss")
# and resource_path("data", "sample_spectra") work unmodified whether
# running from source or frozen.
datas = [
    ("app/resources/style.qss", "app/resources"),
    ("data/sample_spectra", "data/sample_spectra"),
]

# Matplotlib ships its own data files (fonts, mpl-data) that its
# hook normally collects automatically, but we make it explicit here
# so a missing/blocked hook doesn't silently produce a build that
# fails only at first-plot-render time on a clean machine.
datas += collect_data_files("matplotlib")

# ---------------------------------------------------------------------
# Hidden imports
# ---------------------------------------------------------------------
# PySide6's Qt plugin loading and some SciPy/NumPy submodules aren't
# always picked up by PyInstaller's static import analysis. Only the
# submodules actually needed at runtime are collected -- no speculative
# additions.
hiddenimports = []
hiddenimports += collect_submodules("scipy.signal")  # find_peaks and friends
hiddenimports += [
    "scipy.special.cython_special",  # common scipy hidden-import gap
    "PySide6.QtSvg",                 # Qt style/icon rendering dependency
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the bundle lean: exclude alternative Qt bindings so
        # PyInstaller's Qt hook doesn't get confused about which
        # binding to bundle, and exclude test frameworks that have no
        # business being in a release build.
        "PyQt5",
        "PyQt6",
        "PySide2",
        "pytest",
        "pytest_cov",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HydrogenSpectroscopy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # GUI app -- no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # add an .ico path here if/when project artwork exists
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HydrogenSpectroscopy",
)
