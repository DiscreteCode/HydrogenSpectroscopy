# Scientific References

Every reference below is one this project's physics/spectroscopy code
actually relies on -- either cited directly in the relevant module's
docstring, or the authoritative source for a formula/dataset the code
implements. Nothing here is added for length; if it's listed, some
module in `physics/` or `spectroscopy/` depends on it.

## Physical constants

**CODATA 2018 recommended values of the fundamental physical
constants**, as provided by `scipy.constants`. Used in
`physics/constants.py` as the single source of truth for the Planck
constant, speed of light, elementary charge, electron/proton mass, and
the Rydberg constant -- every other physics module derives its numbers
from these rather than hard-coding them.

- Committee on Data for Science and Technology (CODATA), 2018
  recommended values.
- `scipy.constants` documentation: https://docs.scipy.org/doc/scipy/reference/constants.html

## Atomic spectroscopy reference data

**NIST Atomic Spectra Database (ASD)** -- the standard reference for
measured atomic transition wavelengths, used to compare computed hydrogen
Balmer wavelengths and as the reference source for the non-hydrogen line
subset in `spectroscopy/element_database.py`. The app labels these lines as
reference data, not as quantum calculations. The current educational subset
includes He I 447.1/587.6/667.8 nm; Na D2/D1 near 589.0/589.6 nm; Ca II K/H
near 393.4/396.8 nm; and a small Fe I subset near 438.4/495.8/526.9 nm.
Rounded values are for demonstration and should not be treated as precision
line-list data. Consult NIST ASD for species, ionization stage, and exact
wavelength conventions when precision is required.

- NIST Atomic Spectra Database: https://physics.nist.gov/PhysRefData/ASD/

## Vacuum-to-air wavelength conversion

**B. Edlén, "The Refractive Index of Air", Metrologia, 2, 71 (1966).**
The dispersion formula for the refractive index of standard air
(15°C, 101325 Pa, 0.03% CO₂) implemented in
`physics/air_conversion.py`, used to convert the fundamentally vacuum
wavelength produced by the Rydberg calculation into the standard-air
wavelength conventionally quoted in laboratory and textbook hydrogen
line tables (e.g. Hα "= 656.3 nm"). Valid from approximately 200-1700 nm;
the module returns `None` outside that range rather than extrapolating
past the formula's validated domain.

## Hydrogen spectral series (historical)

The five named hydrogen spectral series implemented in
`physics/spectral_series.py`, with their discovery attributions as
commonly documented in standard atomic physics references and the
NIST ASD:

- Theodore Lyman, 1906 (ultraviolet, n_final = 1)
- Johann Balmer, 1885 (visible, n_final = 2)
- Friedrich Paschen, 1908 (infrared, n_final = 3)
- Frederick Brackett, 1922 (infrared, n_final = 4)
- August Pfund, 1924 (infrared, n_final = 5)

## Foundational physics

- **N. Bohr** (1913) and the non-relativistic Schrödinger treatment of
  the hydrogen atom -- both give the same `E_n = -13.6 eV/n²` energy
  spectrum used throughout `physics/hydrogen.py`.
- **M. Planck** (1900) -- blackbody spectral radiance
  (`physics/blackbody.py`), used only to give the Stellar Spectrum
  Simulator a physically motivated continuum shape, explicitly *not*
  as a stellar-atmosphere model (see the Limitations section of the
  main README).
- Special-relativistic Doppler formula (`physics/doppler.py`) --
  standard textbook special relativity, included alongside the
  classical `Δλ/λ = v/c` approximation used by default in the UI.

## What is *not* a citation here

The illustrative line-intensity falloff (`spectroscopy/spectrum.py`,
`default_relative_amplitude`) and the synthetic stellar continuum/noise
model (`spectroscopy/analyzer.py`) are original, clearly-documented
simplifications built for this project's educational purpose -- they
do not claim to reproduce a specific published oscillator-strength or
stellar-atmosphere calculation, and are not cited as if they did. See
the README's Limitations section and each module's docstring for what
they do and don't claim.
