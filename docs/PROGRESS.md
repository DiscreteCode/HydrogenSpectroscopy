# Development Progress

## Phase 1 / Checkpoint 1 — Physics Engine + Spectroscopy Backend (COMPLETE)

Physics engine (`physics/`) and spectroscopy pipeline (`spectroscopy/`)
implemented, audited, and validated. Zero GUI dependency; independently
testable. 160/160 backend tests passing, ~96% coverage across
physics + spectroscopy at the end of Checkpoint 1.

## Checkpoint 2 — Complete GUI + Visualization + Interactive Demonstration (COMPLETE)

The application is now a real, launchable PySide6 desktop app:

```bash
python3 main.py
```

- [x] `main.py` entry point (QApplication + stylesheet + MainWindow)
- [x] `app/ui/main_window.py` — sidebar navigation shell, owns the shared `AppState`
- [x] Dashboard (pipeline overview, live "current selection" stats, quick nav)
- [x] Energy Levels + Transition Explorer (combined page — see its module
      docstring for why): interactive n_i/n_f selection, live diagram,
      vacuum/air wavelengths, transition animation, "add to spectrum"
- [x] Spectrum Simulator: emission/absorption, series or custom transitions,
      configurable range/resolution/line width/intensity, PNG + CSV export
- [x] Stellar Spectrum & Analysis: synthetic star generation (temperature,
      radial velocity, noise, H-line strength), sample-spectrum loading,
      CSV/TXT import, hydrogen line matching, verdict banner, detection
      table, CSV + TXT report export, live Doppler (rest/observed
      wavelength) readout
- [x] Element Identification: hydrogen shown as live quantum-calculated;
      He/Na/Ca/Fe shown as clearly labeled reference-only lookup data
- [x] Theory / Learn: all 12 required topics with equations and links into
      the relevant interactive page
- [x] About / References: project purpose, technology, scientific scope,
      honest limitations, references (CODATA, NIST ASD)
- [x] Dark scientific-instrument theme (`app/resources/style.qss`) applied
      application-wide
- [x] Restrained animations: electron-drop/photon transition, sequential
      spectrum-line reveal, staged analysis pipeline status text
- [x] Graceful malformed-file handling (user-facing QMessageBox, no
      tracebacks), verified with a real malformed CSV in tests
- [x] `tests/test_gui.py` — 29 headless (Qt offscreen) GUI tests covering
      construction, navigation, every page, the 3→2 critical-path
      calculation, spectrum generation, synthetic + sample-file stellar
      analysis (including the negative-control and Doppler-shifted
      samples), malformed-file handling, and element identification

**Historical full suite: 189/189 tests passing, 93% combined coverage**
(`physics` + `spectroscopy` + `visualization`; `app/` is exercised by
`test_gui.py` but not included in the coverage source list).

## Checkpoint 3 — Documentation, Release Packaging, Windows Build (COMPLETE)

- [x] `README.md` rewritten to match actual repository state (previously
      stale, still describing "Phase 1 of N complete")
- [x] `docs/REFERENCES.md` -- CODATA, NIST ASD, Edlén (1966), spectral
      series discovery attributions; nothing invented
- [x] `docs/RELEASE_CHECKLIST.md` -- source/scientific/Windows/CI/docs
      checklist, with items marked as statically-verified-this-checkpoint
      vs. requiring a PySide6/Windows environment to confirm
- [x] `app/paths.py` -- single resource-path helper (frozen/`sys._MEIPASS`
      aware); replaced the two ad hoc `Path(__file__)`-relative resource
      loads in `main.py` and `app/ui/stellar_analysis_page.py`
- [x] `tests/test_paths.py` -- resource resolution in both source and
      simulated-frozen mode; has no PySide6 dependency
- [x] `HydrogenSpectroscopy.spec` -- PyInstaller onedir build spec
- [x] `build.bat` -- Windows developer build script
- [x] `.github/workflows/windows-build.yml` -- Windows CI: install, test,
      build, upload `HydrogenSpectroscopy-Windows` artifact
- [x] `pyproject.toml` -- added `[project]` metadata (name, version 1.0.0,
      description, dependencies)
- [x] `.gitignore` added; stray `.coverage` and `__pycache__/` directories
      removed from the source tree

**Environment note:** this checkpoint's authoring environment had no
network access and no PySide6/pytest/PyInstaller installed, so the GUI
and Windows build could not be executed directly here. Every physics/
spectroscopy claim in this checkpoint's docs was verified by direct
`python3` execution against the actual backend code (not assumed); GUI
launch, the full `pytest` run, and the actual Windows `.exe` build are
marked in `docs/RELEASE_CHECKLIST.md` as pending verification in a
capable environment (local machine or the Windows GitHub Actions
runner, which is the project's authoritative Windows build path).

## Remaining (requires an environment with PySide6/PyInstaller)

- [ ] Run `pytest` end to end and confirm the current pass count
- [ ] Launch `python main.py` and click through all 8 pages
- [ ] Run `build.bat` on Windows (or trigger the GitHub Actions workflow)
      and confirm `HydrogenSpectroscopy.exe` launches correctly

## Review 2 Update — Synthetic Stellar Composition

- [x] Added `spectroscopy/composition.py`: multi-element synthetic absorption
      spectra for H, He, Na, Ca and Fe; hydrogen transitions are generated by
      the quantum engine and other elements use explicitly labeled reference
      wavelengths.
- [x] Added `app/ui/composition_page.py`: adjustable relative-abundance weights,
      noise control, spectral plot, normalized-composition bar chart, line-count/mean-depth
      summary, mystery-star challenge with hidden solution, and CSV export.
- [x] Fixed a challenge-answer leak: abundance bars remain hidden until the solution
      is revealed, just like the abundance values in the table.
- [x] Fixed a modeling bug where zero-abundance elements could still create
      synthetic lines; detection now uses continuum-normalized core flux to
      reduce false matches from neighboring lines.
- [x] Added validation for temperature, line width, radial velocity, noise,
      and abundance inputs; expanded backend tests, including noisy zero-abundance
      controls and reproducible random-seed behavior.
- [x] Updated the navigation count and documentation to distinguish calculated
      hydrogen transitions from reference-only lines for other elements.
- [x] 173 non-GUI tests pass; Python syntax compilation passes.
- [x] Added GUI regression tests for the composition chart and mystery-answer masking.
- [ ] Full GUI suite and Windows executable still need to run on a Windows or
      PySide6-capable environment. PySide6 installation was unavailable in
      the current offline environment, so no GUI/build success is claimed.

**Scientific scope:** abundance sliders control the synthetic spectrum; the
app does not infer real stellar abundances from observed spectra. Line strength
is affected by temperature, ionization and atmospheric conditions, so values
must be presented as simulated inputs, not precise astrophysical measurements.
