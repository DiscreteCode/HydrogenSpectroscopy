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

The application includes the original hydrogen spectroscopy workflow and the
Review 2 **Stellar Composition Analyzer**. Hydrogen transitions are calculated
by the quantum physics engine; He/Na/Ca/Fe use labeled NIST reference lines.
The composition page simulates a multi-element spectrum (adjustable relative
abundances, noise, line width, radial velocity; live updates), then analyzes
the resulting intensity *blindly*: continuum estimate, line detection, Doppler
estimate, line-to-element matching, and an **inferred** relative-abundance
chart shown next to the **simulated input** abundances. Inferred values come
from a demo model and are not measurements of real stars (see *Composition
analysis* and *Limitations* below). See `docs/PROGRESS.md` and
`docs/REVIEW2_HANDOFF.md` for details.

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
- **Stellar Composition Analyzer** -- H/He/Na/Ca/Fe simulated spectrum
  with adjustable abundances, noise, line width and radial velocity (live
  updates); per-element absorption contributions; blind analysis (detected
  vs reference wavelength, element, line info, fitted depth, significance,
  blend flags); simulated-**input** vs **inferred** abundance charts; CSV
  export (summary, line table, full spectrum); in-app limitations tab;
  mystery-star challenge with solution reveal. Not an astrophysical
  abundance solver.
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

Verified status of this revision: see *Verification* in
`docs/REVIEW2_HANDOFF.md` (exact tests run, and what could not be run here).

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

`.github/workflows/Windows-Build.yml` runs on `windows-latest`: installs
dependencies, runs the full test suite (offscreen Qt), builds with PyInstaller,
**smoke-tests the built exe** (`HydrogenSpectroscopy.exe --smoke-test result.txt`
opens every page, runs the composition simulation + analysis and CSV export,
and exits 0 on success), then zips and re-extracts the package and smoke-tests
the extracted copy before uploading it as the artifact
**`HydrogenSpectroscopy-Windows`**.

To use it: open the run on GitHub > *Artifacts* > download
`HydrogenSpectroscopy-Windows`. GitHub delivers a standard `.zip` with **no
password**. Extract the whole thing, open the `HydrogenSpectroscopy` folder and
double-click `HydrogenSpectroscopy.exe`. Keep the `_internal` folder next to
the exe. The exe is unsigned, so Windows SmartScreen may show *More info > Run
anyway*.

PyInstaller cannot cross-compile, so the Windows exe itself is only ever built
and verified by this workflow (or `build.bat` on a Windows machine).

## Composition analysis: physics, assumptions, equations

**Wavelengths.** Hydrogen: Rydberg/Bohr levels, `E_n = -13.6 eV / n^2`
(reduced-mass corrected), `lambda = hc / |E_i - E_f|` (vacuum), converted to
standard air with the Edlen (1966) formula. He/Na/Ca/Fe are looked-up
standard-air wavelengths. All composition-page wavelengths are standard air, nm.

**Doppler shift** (classical, `v << c`): `lambda_obs = lambda_rest (1 + v/c)`;
`v > 0` is receding (redshift).

**Simulation.** `I(lambda) = B_T(lambda) * Pi_lines [1 - d_i exp(-(lambda - lambda_i)^2 / 2 sigma^2)] + noise`
with `B_T` the normalized Planck blackbody (8500 K), Gaussian lines of common
width `sigma`, and Gaussian noise. Line depth uses a **toy model**
`d = D_max tanh( s_el * 0.65 * sqrt(a / a_0) / D_max )`, `D_max = 0.78`,
`a` the input weight (normalized to 100), `a_0` a per-element reference weight
and `s_el` a per-element strength. It is not a curve of growth.

**Blind analysis** (`spectroscopy/composition_analysis.py`) uses the intensity
only: (1) continuum = clipped polynomial in log flux, refined after the lines
are fitted; (2) radial velocity = scan for the shift that best aligns the known
candidate lines, then fitted; (3) joint bounded least-squares fit of one depth
per candidate line plus shared velocity and line width; (4) a line is
*detected* if depth >= 0.02 and depth/sigma_depth >= 5 (sigma from the fit
covariance); (5) detected peaks are matched to reference lines (blends flagged
when lines are within ~3 line-widths); (6) per-element depths are inverted
through the toy model and normalized to 100 -> **inferred** abundance.

**Input vs inferred.** *Simulated input* = the weights you set. *Inferred* =
what step (6) recovers. They agree well in tests only because the analyzer
inverts the very model that generated the data.

### Reference line data

| Element | Lines (nm, air) | Source |
|---|---|---|
| H | Balmer H-alpha..H-delta, computed | Quantum model (Rydberg) + Edlen 1966 |
| He I | 447.1479, 492.1931, 501.5678, 587.562 (D3), 667.8152, 706.5177 | NIST Handbook, He wavelength table |
| Na I | 588.995 (D2), 589.592 (D1) | NIST Handbook, Na table |
| Ca II / I | 393.3661 (K), 396.8467 (H), 422.6727 (Ca I) | NIST Handbook, Ca strong-lines table |
| Fe I | 382.04, 385.99, 388.63, 404.58, 438.35, 516.75 | NIST Handbook, Fe strong-lines table (0.01 nm) |

Each `ReferenceLine` carries its citation (`spectroscopy/element_database.py`).
Full citations: `docs/REFERENCES.md`. Lines outside 380-700 nm (He 706.5) are
stored but not drawn in the default window.

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
- **Composition analysis:** inferred abundances are demo-model outputs (the
  analyzer inverts the simulator's own toy line-strength model). There is no
  radiative transfer, ionization/excitation balance, broadening physics, NLTE,
  limb darkening or molecular lines; the continuum is a plain blackbody; line
  lists are short subsets; uncertainties are statistical only. Never present
  these numbers as measured stellar abundances.

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
.github/workflows/Windows-Build.yml   Windows CI build + test + artifact upload
```

The dependency direction is strict and one-way:

```
physics  ->  spectroscopy  ->  visualization  ->  app (GUI)
```

`physics/` never imports anything from `spectroscopy/`, `visualization/`,
or `app/`; the GUI calls into the backend, never the reverse.

## References

See `docs/REFERENCES.md`.
