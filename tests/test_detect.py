"""Tests for the detection layer: CFAR, bands, bursts, hopping, pipeline."""

from __future__ import annotations

import math

import pytest

from wavewatch.detect.burst import band_frame_power, duty_cycle, segment_bursts
from wavewatch.detect.cfar import cfar_1d, detect_bands, estimate_noise_floor
from wavewatch.detect.hopping import HOP_MIN_CHANNELS, group_emitters
from wavewatch.detect.model import Band, Burst, Emitter
from wavewatch.detect.pipeline import DetectionResult, detect_emitters
from wavewatch.dsp.spectrogram import spectrogram
from wavewatch.io.generator import generate
from tests.conftest import random_complex


# --------------------------------------------------------------------------- #
# CFAR
# --------------------------------------------------------------------------- #
def test_cfar_detects_single_peak():
    psd = [1.0] * 64
    psd[32] = 100.0
    peaks = cfar_1d(psd, threshold_db=6.0)
    assert 32 in peaks


def test_cfar_flat_no_peaks():
    psd = [1.0] * 64
    assert cfar_1d(psd) == []


def test_cfar_empty():
    assert cfar_1d([]) == []


def test_cfar_multiple_peaks():
    psd = [1.0] * 128
    psd[20] = 50.0
    psd[80] = 60.0
    peaks = cfar_1d(psd, threshold_db=6.0)
    assert 20 in peaks and 80 in peaks


def test_estimate_noise_floor():
    psd = [1.0] * 90 + [100.0] * 10
    floor = estimate_noise_floor(psd)
    assert math.isclose(floor, 1.0, abs_tol=1e-6)


def test_estimate_noise_floor_empty():
    assert estimate_noise_floor([]) == 0.0


def test_detect_bands_single():
    freqs = [float(i) for i in range(64)]
    psd = [1.0] * 64
    for i in range(30, 35):
        psd[i] = 100.0
    bands = detect_bands(freqs, psd, threshold_db=6.0)
    assert len(bands) == 1
    assert bands[0].f_lo <= 30 and bands[0].f_hi >= 34


def test_detect_bands_none():
    freqs = [float(i) for i in range(32)]
    psd = [1.0] * 32
    assert detect_bands(freqs, psd) == []


def test_detect_bands_empty():
    assert detect_bands([], []) == []


def test_detect_bands_merge_gap():
    freqs = [float(i) for i in range(100)]
    psd = [1.0] * 100
    for i in range(20, 25):
        psd[i] = 100.0
    for i in range(27, 32):  # small gap of 2 bins
        psd[i] = 100.0
    merged = detect_bands(freqs, psd, threshold_db=6.0, merge_gap=5.0)
    unmerged = detect_bands(freqs, psd, threshold_db=6.0, merge_gap=0.0)
    assert len(merged) == 1
    assert len(unmerged) == 2


def test_band_properties():
    b = Band(f_lo=10.0, f_hi=20.0, center=15.0, peak_power=100.0, peak_db=20.0, noise_db=0.0)
    assert b.bandwidth == 10.0
    assert b.snr_db == 20.0


# --------------------------------------------------------------------------- #
# Bursts
# --------------------------------------------------------------------------- #
def test_burst_segmentation_continuous():
    cap, _ = generate("gnss")
    spec = spectrogram(cap.samples, fs=cap.sample_rate, nperseg=256)
    freqs = spec.freqs
    band = Band(f_lo=freqs[0], f_hi=freqs[-1], center=0.0, peak_power=1.0,
                peak_db=0.0, noise_db=-10.0)
    bursts = segment_bursts(spec, band)
    assert len(bursts) >= 1


def test_duty_cycle_full():
    b = Burst(t_start=0.0, t_end=1.0, frame_start=0, frame_end=1, center=0.0)
    assert duty_cycle([b], 1.0) == 1.0


def test_duty_cycle_half():
    b = Burst(t_start=0.0, t_end=0.5, frame_start=0, frame_end=1, center=0.0)
    assert math.isclose(duty_cycle([b], 1.0), 0.5)


def test_duty_cycle_empty():
    assert duty_cycle([], 1.0) == 0.0


def test_burst_duration_property():
    b = Burst(t_start=1.0, t_end=3.5, frame_start=0, frame_end=1, center=0.0)
    assert b.duration == 2.5


# --------------------------------------------------------------------------- #
# Hopping
# --------------------------------------------------------------------------- #
def _mk_band(center, bw=1000.0):
    return Band(f_lo=center - bw / 2, f_hi=center + bw / 2, center=center,
                peak_power=100.0, peak_db=20.0, noise_db=0.0)


def test_group_emitters_hopping_merge():
    fs = 1_000_000.0
    centers = [-300000, -100000, 100000, 300000]
    bands = [_mk_band(c) for c in centers]
    bursts = [[Burst(0, 0.001, 0, 1, c)] for c in centers]
    duty = [0.1] * len(centers)
    emitters = group_emitters(bands, bursts, duty, fs=fs, total_time=0.04)
    hopping = [e for e in emitters if e.hopping]
    assert len(hopping) == 1
    assert hopping[0].n_channels == 4


def test_group_emitters_no_hop_below_min():
    fs = 1_000_000.0
    centers = [-100000, 100000]  # only 2 channels
    bands = [_mk_band(c) for c in centers]
    bursts = [[Burst(0, 0.001, 0, 1, c)] for c in centers]
    duty = [0.1, 0.1]
    emitters = group_emitters(bands, bursts, duty, fs=fs, total_time=0.04)
    assert all(not e.hopping for e in emitters)
    assert len(emitters) == 2


def test_group_emitters_wideband_not_merged():
    fs = 1_000_000.0
    bands = [_mk_band(0.0, bw=600000.0)]  # wideband
    bursts = [[Burst(0, 0.04, 0, 1, 0.0)]]
    duty = [1.0]
    emitters = group_emitters(bands, bursts, duty, fs=fs, total_time=0.04)
    assert len(emitters) == 1
    assert not emitters[0].hopping


def test_hop_min_constant():
    assert HOP_MIN_CHANNELS == 3


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_detect_emitters_finds_something(scenario):
    cap, _ = generate(scenario)
    det = detect_emitters(cap)
    assert isinstance(det, DetectionResult)
    assert len(det.emitters) >= 1


def test_detect_emitters_noise_empty():
    cap, _ = generate("noise")
    det = detect_emitters(cap)
    assert len(det.emitters) == 0


def test_detect_emitters_empty_capture():
    from wavewatch.io.capture import Capture
    det = detect_emitters(Capture(samples=[], sample_rate=1000.0))
    assert det.emitters == []


@pytest.mark.parametrize("scenario", ["drone-link", "ble"])
def test_detect_hopping_scenarios(scenario):
    cap, _ = generate(scenario)
    det = detect_emitters(cap)
    assert any(e.hopping for e in det.emitters)


def test_detect_from_spectrum_capture(tmp_path):
    from wavewatch.io.csvspec import write_csv_spectrum, read_csv_spectrum
    freqs = [float(i) for i in range(100)]
    powers = [-90.0] * 100
    for i in range(40, 50):
        powers[i] = -40.0
    path = str(tmp_path / "s.csv")
    write_csv_spectrum(path, freqs, powers)
    cap = read_csv_spectrum(path)
    det = detect_emitters(cap)
    assert len(det.emitters) >= 1


def test_detection_result_has_spectrogram():
    cap, _ = generate("wifi")
    det = detect_emitters(cap)
    assert det.spectrogram is not None
    assert len(det.psd) > 0
