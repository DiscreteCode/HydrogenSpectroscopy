# Hydrogen Quantum Spectroscopy

> Unveiling Stellar Composition Through Quantum Simulations of Hydrogen Spectral Lines

An educational desktop application (Python + PySide6) that demonstrates,
end to end, how the quantization of a bound electron's energy leads all
the way to identifying hydrogen in a stellar spectrum:

```
Quantum Energy Levels
        |
        v
 Electron Transition
        |
        v
      Photon
        |
        v
  Spectral Line
        |
        v
 Stellar Spectrum
        |
        v
Hydrogen Detection
```

Hydrogen energy levels and transitions are computed live from the model
(`E_n = -13.6 eV/n^2` and the Rydberg relation). The app also includes
clearly labeled reference wavelengths for helium, sodium, calcium and iron.
It simulates stellar absorption spectra, searches for line patterns, and
reports detections. Multi-element abundances are synthetic input parameters,
not values inferred from real stellar observations.

## Status

The application includes the original hydrogen spectroscopy workflow and a
Review 2 Stellar Composition Analyzer. Hydrogen transitions are calculated
by the physics engine; He/Na/Ca/Fe use labeled reference lines. The
composition page creates synthetic spectra with adjustable relative
abundance weights, shows normalized input composition, and includes a
mystery-star challenge. See `docs/PROGRESS.md` for development details.

## Features

- **Energy Levels / Transition Explorer** -- interactive `n_i -> n_f`
  selection, live energy-level diagram, transition animation, vacuum
  *and* air wavelength readouts
- **Spectrum Simulator** -- emission or absorption mode, full spectral
  series (Lyman/Balmer/Paschen/Brackett/Pfund) or custom transitions,
  configurable wavelength range, resolution, line width, and
  intensity; PNG + CSV export
- **Stellar Spectrum & Analysis** -- synthetic star generation
  (temperature, radial velocity, noise, hydrogen line strength),
  built-in sample spectra, CSV/TXT import, hydrogen line matching with
  a pass/fail verdict, detection results table, CSV + TXT report
  export, live Doppler (rest/observed wavelength) readout
- **Element Identification** -- hydrogen shown as live quantum-calculated;
  helium/sodium/calcium/iron shown as clearly labeled reference-only
  lookup data (not quantum-computed in this app)
- **Stellar Composition Analyzer** -- adjustable synthetic H/He/Na/Ca/Fe
  abundance inputs, multi-element absorption spectrum, noise control,
  mystery-star challenge, solution reveal, and CSV export. The simplified
  line-depth model is educational and is not an astrophysical abundance solver.
- **Theory / Learn** -- the underlying physics with equations, linked
  into the relevant interactive page
- **About / References** -- project purpose, scientific scope, honest
  limitations, and citations
- Dark, scientific-instrument-styled UI; restrained animations
  (electron-drop/photon transition, sequential line reveal)
- Graceful handling of malformed spectrum files (a clean message, not
  a traceback)

## Running from source

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 main.py
```

## Testing

```bash
pip install -r requirements.txt   # includes pytest / pytest-cov
pytest
```

The backend (`physics`, `spectroscopy`, `visualization`) has no GUI
dependency and can be tested/used with no display and no Qt installed
at all. `tests/test_gui.py` additionally drives the real PySide6 widget
tree headlessly via Qt's offscreen platform plugin
(`QT_QPA_PLATFORM=offscreen`, set automatically by the test module),
so the full suite also runs in CI with no physical display.

The current development environment does not have PySide6 installed, so
GUI tests cannot run here. All 173 non-GUI tests pass. Two GUI regression
tests were added for the composition page and mystery-solution masking;
the full suite and Windows build must be verified by GitHub Actions before
release. See `docs/RELEASE_CHECKLIST.md`.

## Windows executable

The end user does **not** need Python, pip, or a terminal. A packaged
Windows build is a self-contained folder:

```
HydrogenSpectroscopy/
    HydrogenSpectroscopy.exe   <- double-click this
    _internal/                 <- PySide6, NumPy, SciPy, Matplotlib,
                                   Qt plugins, and the app's own
                                   bundled resources (style sheet,
                                   sample spectra)
```

### Building it yourself

On Windows, from the repository root:

```
build.bat
```

This creates a build virtual environment, installs dependencies and
PyInstaller, cleans any stale `build/`/`dist/`, and runs PyInstaller
against `HydrogenSpectroscopy.spec`. The result appears at:

```
dist\HydrogenSpectroscopy\HydrogenSpectroscopy.exe
```

Ship the entire `dist\HydrogenSpectroscopy\` folder together -- the
`.exe` depends on the `_internal\` folder next to it (this is a onedir
build, not onefile; see the spec file's docstring for why).

### Via GitHub Actions (no Windows machine needed)

`.github/workflows/windows-build.yml` runs on `windows-latest`,
installs dependencies, runs the full test suite, builds with
PyInstaller, and uploads the result as a workflow artifact named
**`HydrogenSpectroscopy-Windows`**. This is the authoritative Windows
build/verification path for this project, since PyInstaller cannot
cross-compile a Windows executable from Linux or macOS -- if you're
developing on a non-Windows machine, let CI produce and verify the
actual `.exe`.

## Scientific methodology

- **Energy quantization**: `E_n = -13.6 eV / n^2` (Rydberg energy
  derived from CODATA constants with the electron-proton reduced-mass
  correction applied, not hard-coded as 13.6)
- **Transitions**: `delta_E = |E_initial - E_final|`,
  `lambda = hc / delta_E` (vacuum wavelength), `nu = c / lambda`
- **Spectral series**: Lyman (n_f=1), Balmer (n_f=2), Paschen (n_f=3),
  Brackett (n_f=4), Pfund (n_f=5)
- **Line broadening**: Gaussian profiles (Lorentzian also available)
  turn a single wavelength into a plottable, physically realistic line
  shape
- **Doppler shift**: classical `delta_lambda/lambda = v/c` by default
  (accurate to ~1 part in 10^6 at stellar radial velocities), with an
  exact relativistic formula also implemented
- **Hydrogen detection**: absorption features are located with an
  adaptive, noise-based threshold (a robust median-absolute-deviation
  estimator, not one fixed number for every spectrum), then matched
  against expected Balmer wavelengths by taking the *deepest* candidate
  within a search window -- not merely the nearest -- so a shallow
  noise wiggle can't be mistaken for a real, Doppler-shifted line

### Vacuum vs. air wavelengths

The Rydberg/quantum calculation is a vacuum calculation -- there is no
atmosphere in `E = hc/lambda`. But almost every commonly quoted
hydrogen line value (Hα "= 656.3 nm") is actually the wavelength as
dispersed through standard air, whose refractive index is very
slightly above 1. This application computes and preserves **both**:

| | Hα (3->2) |
|---|---|
| Vacuum | ≈ 656.46 nm |
| Standard air | ≈ 656.28 nm |

The conversion uses the Edlén (1966) dispersion formula for standard
air (see `physics/air_conversion.py`), valid from ~200-1700 nm.
Frequency is always derived from the vacuum wavelength -- it's a
medium-independent property of the photon, so deriving it from the air
wavelength would be subtly wrong. The air wavelength is what's shown as
the headline UI value (matching conventional textbook/lab figures)
whenever it's defined; the app falls back to vacuum outside that range
(e.g. deep-UV Lyman lines).

## Limitations

This is an **educational simulation and spectral-identification
demonstration**, not a research-grade astronomical instrument:

- The stellar spectrum simulator uses an illustrative blackbody-style
  continuum, not a full stellar-atmosphere radiative-transfer model
  (real stellar continua also depend on opacity, limb darkening, etc.)
- Line intensities use a simple illustrative falloff, not computed
  Einstein A-coefficients / oscillator strengths
- Only hydrogen is quantum-mechanically computed; helium, sodium,
  calcium, and iron in Element Identification are clearly labeled
  reference lookup data, not derived from this app's physics engine
- Noise can measurably affect the inferred radial velocity of a
  matched line (this is realistic -- so does it for real
  spectroscopists -- but it means single-line velocity readouts should
  be read as illustrative, not a precision measurement)
- Hydrogen "detection" means the observed/synthetic spectrum's features
  match hydrogen's reference wavelengths within tolerance; it is not a
  claim of elemental-abundance quantification

## Project structure

```
main.py                    Entry point (QApplication + MainWindow)
app/
    paths.py                Resource-path resolution (source vs. PyInstaller-frozen)
    controllers/             Shared cross-page state (AppState)
    ui/                       The 8 GUI pages + MainWindow shell
    widgets/                  Small reusable widget builders
    resources/style.qss       Dark scientific-instrument theme
physics/                   Pure physics engine -- zero GUI dependency
spectroscopy/               Spectrum construction, element references, composition simulation, peak detection and I/O
visualization/               Matplotlib plotting helpers used by the GUI
data/sample_spectra/         4 sample CSVs (see data/sample_spectra/README.md)
scripts/generate_sample_spectra.py   Regenerates the sample CSVs from the backend
tests/                      Backend and headless GUI regression tests
docs/                      PROGRESS.md, REFERENCES.md, RELEASE_CHECKLIST.md, REVIEW2_HANDOFF.md
HydrogenSpectroscopy.spec   PyInstaller build spec
build.bat                   Windows developer build script
.github/workflows/windows-build.yml   Windows CI build + test + artifact upload
```

The dependency direction is strict and one-way:

```
physics  ->  spectroscopy  ->  visualization  ->  app (GUI)
```

`physics/` never imports anything from `spectroscopy/`, `visualization/`,
or `app/`; the GUI calls into the backend, never the reverse.

## References

See `docs/REFERENCES.md`.
