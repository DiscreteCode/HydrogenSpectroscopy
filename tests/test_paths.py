"""
tests.test_paths
==================

Lightweight tests for app.paths -- the resource-resolution helper used
by main.py and the Stellar Analysis page so both the source-run and
PyInstaller-frozen code paths resolve bundled resources consistently
(see app/paths.py and HydrogenSpectroscopy.spec).

Deliberately small: this checks the source (non-frozen) path-resolution
behavior end to end, since that's what every environment running this
test suite actually is. The frozen branch (sys.frozen / sys._MEIPASS)
is exercised for real only by an actual PyInstaller build, which is
outside the scope of a unit test -- see docs/RELEASE_CHECKLIST.md's
Windows section for that verification step.

Notably, app.paths has zero PySide6/Qt dependency, so these tests run
in any Python environment with the repo on the path -- no GUI toolkit
required.
"""

from __future__ import annotations

import sys

import app.paths as paths_module
from app.paths import is_frozen, resource_path


def test_not_frozen_in_normal_test_run():
    # Test suites run from source, never as a frozen PyInstaller build.
    assert is_frozen() is False


def test_resource_path_finds_stylesheet():
    style_path = resource_path("app", "resources", "style.qss")
    assert style_path.exists(), f"expected stylesheet at {style_path}"
    assert style_path.is_file()


def test_resource_path_finds_sample_spectra_dir():
    data_dir = resource_path("data", "sample_spectra")
    assert data_dir.exists(), f"expected sample data dir at {data_dir}"
    assert data_dir.is_dir()


def test_sample_spectra_csvs_present():
    data_dir = resource_path("data", "sample_spectra")
    csvs = sorted(p.name for p in data_dir.glob("*.csv"))
    expected = {
        "hydrogen_balmer_emission.csv",
        "stellar_noisy_at_rest.csv",
        "stellar_doppler_shifted_180kms.csv",
        "stellar_no_hydrogen_control.csv",
    }
    assert expected.issubset(set(csvs)), f"missing sample files, found: {csvs}"


def test_app_root_is_repository_root():
    # app/paths.py lives at <repo_root>/app/paths.py, so its resolved
    # app root must be the directory containing both app/ and data/.
    root = paths_module.APP_ROOT
    assert (root / "app").is_dir()
    assert (root / "data").is_dir()
    assert (root / "main.py").is_file()


def test_resource_path_respects_frozen_flag(monkeypatch, tmp_path):
    # Simulate a frozen PyInstaller environment and confirm resource_path
    # resolves against sys._MEIPASS instead of the source tree. This
    # exercises the frozen branch's logic without requiring an actual
    # PyInstaller build.
    fake_bundle = tmp_path / "bundle"
    (fake_bundle / "app" / "resources").mkdir(parents=True)
    (fake_bundle / "app" / "resources" / "style.qss").write_text("/* fake */")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_bundle), raising=False)

    # Re-derive the root the same way app.paths does internally.
    fake_root = paths_module._app_root()
    assert fake_root == fake_bundle
    assert (fake_root / "app" / "resources" / "style.qss").exists()
