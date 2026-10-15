# Release Checklist

Work through this before tagging/shipping a release. Checkpoint 3
statically verified the code paths behind each item where noted; the
GUI/Windows items marked "verify locally" require an environment with
PySide6 (and, for the Windows section, PyInstaller on Windows or the
CI runner) that this checkpoint's authoring environment did not have.

## Source

- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python main.py` launches the application with no errors
- [ ] `pytest` -- all tests pass (173 non-GUI cases pass in the current environment; GUI tests require
      PySide6 and are pending the Windows CI run -- see README's Testing section)
- [ ] All 8 GUI pages open without error: Dashboard, Energy Levels,
      Spectrum Simulator, Stellar Analysis, Element Identification,
      Stellar Composition, Theory, About
- [ ] All 4 sample spectra load from the Stellar Analysis page
- [ ] CSV/TXT spectrum import works, including graceful rejection of a
      malformed file (clean message, not a traceback)
- [ ] CSV/PNG/TXT export works from the relevant pages

- [ ] Stellar Composition Analyzer: move the sliders (spectrum and analysis update
      live), try a preset, compare simulated-input vs inferred abundance bars,
      check the Detected lines tab, and export CSV.

## Scientific

Statically verified in this checkpoint via direct `python3` execution
of the physics/spectroscopy modules (no pytest/PySide6 required for
these -- see the checkpoint's audit notes):

- [x] 3->2 transition computes correctly: ΔE, vacuum wavelength ≈
      656.47 nm, air wavelength ≈ 656.29 nm
- [x] Air wavelength for Hα matches the conventional ≈656.3 nm textbook
      figure; vacuum and air values are both preserved, never conflated
- [x] Balmer series (3,4,5,6 -> 2) produces the expected wavelength
      sequence (656.3 / 486.1 / 434.1 / 410.2 nm, air)
- [x] Synthetic stellar spectrum generation runs and produces a valid
      `StellarSpectrum`
- [x] Doppler shift is applied correctly (classical formula verified
      against `velocity_from_shift_kms` round-trip)
- [x] Hydrogen detection: clean at-rest synthetic spectrum -> DETECTED,
      4/4 lines matched
- [x] Hydrogen detection: Doppler-shifted + noisy synthetic spectrum ->
      DETECTED, implied velocity within documented tolerance of the
      injected value
- [x] Negative control (`stellar_no_hydrogen_control.csv`) -> HYDROGEN
      NOT DETECTED
- [x] `stellar_noisy_at_rest.csv` and `stellar_doppler_shifted_180kms.csv`
      -> HYDROGEN DETECTED, matching `data/sample_spectra/README.md`'s
      documented expected results exactly

## Windows packaging

- [ ] `build.bat` completes without error on a Windows machine
- [ ] PyInstaller succeeds against `HydrogenSpectroscopy.spec`
- [ ] `dist\HydrogenSpectroscopy\HydrogenSpectroscopy.exe` launches with
      no Python installation on the target machine
- [ ] Qt resources (stylesheet, plugins) load correctly in the frozen
      build -- UI should not look unstyled
- [ ] Sample spectra load correctly in the frozen build (verifies
      `app/paths.py`'s frozen-mode resolution against real
      `sys._MEIPASS`, not just the simulated test in `test_paths.py`)
- [ ] Exports (CSV/PNG/TXT) work and write to a sensible location from
      the frozen build

Statically verified this checkpoint (Linux environment, no PySide6/
PyInstaller available -- see audit notes):

- [x] `app/paths.py` correctly resolves resource paths in both
      non-frozen (source) mode and a simulated frozen
      (`sys.frozen`/`sys._MEIPASS`) mode -- see `tests/test_paths.py`,
      manually executed with plain `python3`
- [x] No remaining `Path(__file__)`-relative resource loads outside
      `app/paths.py` itself (audited: `main.py`'s stylesheet load and
      `app/ui/stellar_analysis_page.py`'s sample-data directory were
      the only two call sites; both now go through `resource_path()`)
- [x] `HydrogenSpectroscopy.spec` is syntactically valid Python
      (`python3 -m py_compile`); its `datas` declarations mirror the
      relative layout `app/paths.py` expects under `sys._MEIPASS`
- [x] `build.bat` reviewed for correct PyInstaller invocation and
      output-path reporting; not executed (Windows-only)

## CI

- [ ] `.github/workflows/Windows-Build.yml` runs successfully on push/PR
- [ ] The `HydrogenSpectroscopy-Windows` artifact is produced and
      downloadable from the workflow run

Statically verified this checkpoint:

- [x] Workflow YAML structure reviewed: checkout -> setup Python ->
      install deps -> install PyInstaller -> `pytest` -> PyInstaller
      build -> verify `.exe` exists -> upload artifact named
      `HydrogenSpectroscopy-Windows`
- [ ] Not yet run for real (requires a push/PR or manual
      `workflow_dispatch` trigger on GitHub)

## Documentation accuracy

- [x] README no longer claims "Phase 1 of N complete" / GUI-not-built
      (this was stale as of the Checkpoint 2 handoff and is fixed this
      checkpoint)
- [x] README's feature list matches the actual 7 implemented GUI pages
- [x] Wavelength values in README match values computed directly from
      the physics engine, not retyped from memory
- [x] No claims of professional astronomical precision or real
      elemental-abundance measurement anywhere in README/About page
