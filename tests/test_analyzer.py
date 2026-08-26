import numpy as np
import pytest

from spectroscopy import analyzer as an
from spectroscopy.spectrum import build_wavelength_grid


def test_synthetic_stellar_spectrum_has_expected_shape():
    grid = build_wavelength_grid(380, 700, 6000)
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.6, random_seed=42,
    )
    assert star.wavelength_nm.shape == grid.shape
    assert star.intensity.shape == grid.shape
    assert np.all(star.intensity >= 0.0)
    # continuum should generally be higher than the line-carrying spectrum
    assert np.mean(star.continuum) >= np.mean(star.intensity)


def test_match_hydrogen_lines_detects_clean_synthetic_star():
    """The flagship demonstration (brief section 32): a clean synthetic
    Balmer-absorption star must be positively identified as hydrogen."""
    grid = build_wavelength_grid(380, 700, 8000)
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.7, random_seed=1,
    )
    summary = an.match_hydrogen_lines(star.wavelength_nm, star.intensity, continuum_level=star.continuum)
    assert summary.detected is True
    assert summary.num_matched >= 3
    assert "HYDROGEN DETECTED" in summary.message

    # Every matched line should be close to its expected wavelength.
    for r in summary.results:
        if r.matched:
            assert abs(r.difference_nm) < 1.0


def test_match_hydrogen_lines_no_detection_on_featureless_spectrum():
    grid = build_wavelength_grid(380, 700, 4000)
    flat_intensity = np.ones_like(grid)
    summary = an.match_hydrogen_lines(grid, flat_intensity, continuum_level=1.0)
    assert summary.detected is False
    assert summary.num_matched == 0
    assert "NOT DETECTED" in summary.message


def test_match_hydrogen_lines_recovers_doppler_velocity():
    grid = build_wavelength_grid(380, 700, 10000)
    true_velocity = 120.0
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=8500, radial_velocity_kms=true_velocity, noise_level=0.0,
        h_line_strength=0.7, random_seed=2,
    )
    summary = an.match_hydrogen_lines(grid, star.intensity, continuum_level=star.continuum)
    assert summary.detected is True
    assert summary.mean_velocity_kms is not None
    assert summary.mean_velocity_kms == pytest.approx(true_velocity, abs=15.0)


def test_match_hydrogen_lines_robust_to_moderate_noise():
    grid = build_wavelength_grid(380, 700, 10000)
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.01,
        h_line_strength=0.7, random_seed=3,
    )
    summary = an.match_hydrogen_lines(grid, star.intensity, continuum_level=star.continuum)
    assert summary.detected is True


def test_detection_result_implied_velocity_none_when_unmatched():
    grid = build_wavelength_grid(380, 700, 2000)
    flat_intensity = np.ones_like(grid)
    summary = an.match_hydrogen_lines(grid, flat_intensity, continuum_level=1.0)
    for r in summary.results:
        assert r.implied_velocity_kms is None


def test_invalid_stellar_spectrum_params_rejected():
    grid = build_wavelength_grid(380, 700, 500)
    with pytest.raises(ValueError):
        an.generate_synthetic_stellar_spectrum(grid, h_line_strength=-1.0)
    with pytest.raises(ValueError):
        an.generate_synthetic_stellar_spectrum(grid, noise_level=-0.1)


def test_match_hydrogen_lines_partial_series_is_inconclusive_not_detected():
    """Only H-alpha falls inside a narrow wavelength window (the other
    Balmer members are entirely off-grid) -- a single matching line
    should NOT be reported as a confident hydrogen detection."""
    grid = build_wavelength_grid(650, 663, 4000)  # only covers H-alpha's neighborhood
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.7, random_seed=7,
    )
    summary = an.match_hydrogen_lines(grid, star.intensity, continuum_level=star.continuum)
    assert summary.num_matched <= 1
    assert summary.detected is False
    assert "INCONCLUSIVE" in summary.message or "NOT DETECTED" in summary.message


def test_match_hydrogen_lines_few_series_members_still_works():
    """Restricting n_i_max to 3 means only H-alpha (3->2) is an expected
    line at all -- exercises the 'small series' edge case cleanly."""
    grid = build_wavelength_grid(380, 700, 8000)
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.7, series="Balmer", n_i_max=3, random_seed=9,
    )
    summary = an.match_hydrogen_lines(
        grid, star.intensity, continuum_level=star.continuum, n_i_max=3,
    )
    assert summary.num_expected == 1
    assert summary.num_matched == 1
    # A single line, even if it matches perfectly, is intentionally not
    # enough to declare confident detection (see analyzer.py threshold).
    assert summary.detected is False


def test_match_hydrogen_lines_weak_lines_reduce_matches():
    """Very weak (shallow) absorption lines should be harder to detect
    than strong ones -- exercises sensitivity to hydrogen_strength."""
    grid = build_wavelength_grid(380, 700, 8000)
    strong = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.9, random_seed=11,
    )
    weak = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.02, random_seed=11,
    )
    strong_summary = an.match_hydrogen_lines(grid, strong.intensity, continuum_level=strong.continuum)
    weak_summary = an.match_hydrogen_lines(grid, weak.intensity, continuum_level=weak.continuum)
    assert strong_summary.num_matched >= weak_summary.num_matched


def test_noisy_featureless_spectrum_does_not_falsely_detect_hydrogen():
    """Regression test: a purely noisy blackbody continuum with NO
    injected hydrogen lines at all must not be reported as a detection,
    even though pure noise occasionally clears a naive fixed-prominence
    threshold within a few-nm search window around every expected line.
    This is exactly the "don't succeed just because it's supposed to"
    check from the backend spec."""
    import numpy as np
    from physics.blackbody import normalized_blackbody_continuum

    grid = build_wavelength_grid(380, 700, 6000)
    continuum = normalized_blackbody_continuum(grid, 9000.0)
    rng = np.random.default_rng(99)
    intensity = np.clip(continuum + rng.normal(0.0, 0.01, size=continuum.shape), 0.0, None)

    summary = an.match_hydrogen_lines(grid, intensity, continuum_level=continuum)
    assert summary.detected is False
    assert summary.num_matched <= 1  # a single coincidental hit is tolerated; a pattern is not


def test_noisy_doppler_shifted_spectrum_still_recovers_correct_velocity():
    """Regression test for a real bug found while generating sample
    data: with noise present, the matcher used to grab the NEAREST
    detected feature to each line's rest wavelength, which could be a
    shallow noise wiggle sitting closer to the rest position than the
    true (much deeper) Doppler-shifted line -- silently corrupting the
    recovered velocity toward zero. The matcher must pick the deepest
    candidate in the search window, not merely the nearest."""
    grid = build_wavelength_grid(380, 700, 6000)
    true_velocity = 180.0
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=8500, radial_velocity_kms=true_velocity, noise_level=0.01,
        h_line_strength=0.7, random_seed=7,
    )
    summary = an.match_hydrogen_lines(grid, star.intensity, continuum_level=star.continuum)
    assert summary.detected is True
    assert summary.mean_velocity_kms == pytest.approx(true_velocity, abs=25.0)
