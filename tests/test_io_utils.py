import numpy as np
import pytest

from spectroscopy import io_utils as io


def test_load_csv_with_standard_headers(tmp_path):
    p = tmp_path / "spectrum.csv"
    p.write_text("wavelength_nm,intensity\n400,0.9\n450,0.85\n500,0.95\n550,0.92\n600,0.88\n")
    wl, intensity, header = io.load_spectrum_csv(p)
    assert len(wl) == 5
    assert wl[0] == pytest.approx(400)
    assert intensity[0] == pytest.approx(0.9)


def test_load_csv_with_unusual_headers(tmp_path):
    p = tmp_path / "spectrum.csv"
    p.write_text("Wave (nm),Flux\n400,0.9\n450,0.85\n500,0.95\n550,0.92\n600,0.88\n")
    wl, intensity, header = io.load_spectrum_csv(p)
    assert len(wl) == 5


def test_load_csv_sorts_by_wavelength(tmp_path):
    p = tmp_path / "spectrum.csv"
    p.write_text("wavelength_nm,intensity\n500,1\n400,2\n600,3\n450,4\n550,5\n")
    wl, intensity, header = io.load_spectrum_csv(p)
    assert list(wl) == sorted(wl)


def test_load_csv_no_header_falls_back_to_positional(tmp_path):
    p = tmp_path / "spectrum.csv"
    p.write_text("400,0.9\n450,0.85\n500,0.95\n550,0.92\n600,0.88\n")
    wl, intensity, header = io.load_spectrum_csv(p)
    assert len(wl) == 5


def test_load_csv_missing_file_raises_friendly_error():
    with pytest.raises(io.SpectrumImportError):
        io.load_spectrum_csv("/tmp/does_not_exist_12345.csv")


def test_load_csv_empty_file_raises(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("")
    with pytest.raises(io.SpectrumImportError):
        io.load_spectrum_csv(p)


def test_load_csv_too_few_rows_raises(tmp_path):
    p = tmp_path / "tiny.csv"
    p.write_text("wavelength_nm,intensity\n400,0.9\n450,0.85\n")
    with pytest.raises(io.SpectrumImportError):
        io.load_spectrum_csv(p)


def test_load_csv_skips_malformed_rows(tmp_path):
    p = tmp_path / "messy.csv"
    p.write_text(
        "wavelength_nm,intensity\n400,0.9\n450,notanumber\n500,0.95\n550,0.92\n600,0.88\n650,0.80\n"
    )
    wl, intensity, header = io.load_spectrum_csv(p)
    assert len(wl) == 5  # the bad row was skipped


def test_export_spectrum_csv_round_trip(tmp_path):
    p = tmp_path / "out.csv"
    wl = np.array([400.0, 450.0, 500.0, 550.0, 600.0, 650.0])
    intensity = np.array([0.1, 0.3, 0.5, 0.7, 0.9, 0.6])
    io.export_spectrum_csv(p, wl, intensity)
    wl2, intensity2, _ = io.load_spectrum_csv(p)
    assert np.allclose(wl2, wl, atol=1e-3)
    assert np.allclose(intensity2, intensity, atol=1e-4)


def test_explicit_column_selection_by_name(tmp_path):
    p = tmp_path / "spectrum.csv"
    p.write_text("a,b,c\n400,999,0.9\n450,999,0.85\n500,999,0.95\n550,999,0.92\n600,999,0.88\n")
    wl, intensity, header = io.load_spectrum_csv(p, wavelength_col="a", intensity_col="c")
    assert intensity[0] == pytest.approx(0.9)


def test_explicit_unknown_column_name_raises(tmp_path):
    p = tmp_path / "spectrum.csv"
    p.write_text("a,b\n400,0.9\n450,0.85\n500,0.95\n550,0.92\n600,0.88\n")
    with pytest.raises(io.SpectrumImportError):
        io.load_spectrum_csv(p, wavelength_col="nonexistent")


def test_load_csv_rejects_nonpositive_wavelengths(tmp_path):
    p = tmp_path / "bad_wavelengths.csv"
    p.write_text("wavelength_nm,intensity\n-10,0.9\n0,0.85\n500,0.95\n550,0.92\n600,0.88\n")
    with pytest.raises(io.SpectrumImportError):
        io.load_spectrum_csv(p)


def test_load_whitespace_delimited_txt(tmp_path):
    p = tmp_path / "spectrum.txt"
    p.write_text(
        "wavelength_nm intensity\n400 0.90\n450 0.85\n500 0.95\n550 0.92\n600 0.88\n"
    )
    wl, intensity, header = io.load_spectrum_csv(p)
    assert len(wl) == 5
    assert wl[0] == pytest.approx(400)


def test_export_detection_csv_and_report_txt(tmp_path):
    from spectroscopy import analyzer as an
    from spectroscopy.spectrum import build_wavelength_grid

    grid = build_wavelength_grid(380, 700, 6000)
    star = an.generate_synthetic_stellar_spectrum(
        grid, temperature_k=9000, radial_velocity_kms=0.0, noise_level=0.0,
        h_line_strength=0.7, random_seed=1,
    )
    summary = an.match_hydrogen_lines(grid, star.intensity, continuum_level=star.continuum)

    csv_path = tmp_path / "detection.csv"
    txt_path = tmp_path / "detection.txt"
    io.export_detection_results_csv(csv_path, summary.results)
    io.export_detection_report_txt(txt_path, summary, star_label="Test Star")

    assert csv_path.exists() and csv_path.stat().st_size > 0
    assert txt_path.exists()
    report_text = txt_path.read_text()
    assert "HYDROGEN" in report_text
    assert "Test Star" in report_text
