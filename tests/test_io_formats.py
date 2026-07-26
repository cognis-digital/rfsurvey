"""Tests for capture readers/writers: SigMF, WAV-IQ, CSV spectrum."""

from __future__ import annotations

import math
import os

import pytest

from wavewatch.io import load_capture
from wavewatch.io.capture import Capture
from wavewatch.io.csvspec import (
    parse_csv_spectrum_text,
    read_csv_spectrum,
    write_csv_spectrum,
)
from wavewatch.io.generator import gen_tone
from wavewatch.io.sigmf import read_sigmf, write_sigmf
from wavewatch.io.waviq import read_waviq, write_waviq

SIGMF_TYPES = ["cf32_le", "cf64_le", "ci16_le", "ci8", "cu8"]


def _small_capture():
    cap, _ = gen_tone(duration=0.001)
    return cap


@pytest.mark.parametrize("dtype", SIGMF_TYPES)
def test_sigmf_roundtrip_sample_count(tmp_path, dtype):
    cap = _small_capture()
    base = str(tmp_path / "cap")
    meta, data = write_sigmf(base, cap, datatype=dtype)
    assert os.path.exists(meta) and os.path.exists(data)
    cap2 = read_sigmf(meta)
    assert len(cap2.samples) == len(cap.samples)


@pytest.mark.parametrize("dtype", ["cf32_le", "cf64_le"])
def test_sigmf_float_roundtrip_accuracy(tmp_path, dtype):
    cap = _small_capture()
    base = str(tmp_path / "cap")
    write_sigmf(base, cap, datatype=dtype)
    cap2 = read_sigmf(base + ".sigmf-meta")
    for a, b in zip(cap.samples[:50], cap2.samples[:50]):
        assert abs(a - b) < 1e-3


def test_sigmf_metadata_preserved(tmp_path):
    cap = _small_capture()
    cap.center_freq = 2_400_000_000.0
    cap.position = (38.9, -77.03)
    base = str(tmp_path / "cap")
    write_sigmf(base, cap)
    cap2 = read_sigmf(base)
    assert math.isclose(cap2.center_freq, 2_400_000_000.0)
    assert cap2.position is not None
    assert abs(cap2.position[0] - 38.9) < 1e-6
    assert abs(cap2.position[1] - (-77.03)) < 1e-6


def test_sigmf_sample_rate_preserved(tmp_path):
    cap = _small_capture()
    base = str(tmp_path / "cap")
    write_sigmf(base, cap)
    cap2 = read_sigmf(base)
    assert math.isclose(cap2.sample_rate, cap.sample_rate)


def test_sigmf_unknown_datatype_raises(tmp_path):
    cap = _small_capture()
    with pytest.raises(ValueError):
        write_sigmf(str(tmp_path / "c"), cap, datatype="bogus")


def test_sigmf_read_via_data_path(tmp_path):
    cap = _small_capture()
    base = str(tmp_path / "cap")
    _, data = write_sigmf(base, cap)
    cap2 = read_sigmf(data)
    assert len(cap2.samples) == len(cap.samples)


@pytest.mark.parametrize("float32", [True, False])
def test_wav_roundtrip_count(tmp_path, float32):
    cap = _small_capture()
    path = str(tmp_path / "cap.wav")
    write_waviq(path, cap, float32=float32)
    cap2 = read_waviq(path)
    assert len(cap2.samples) == len(cap.samples)


def test_wav_float_accuracy(tmp_path):
    cap = _small_capture()
    path = str(tmp_path / "cap.wav")
    write_waviq(path, cap, float32=True)
    cap2 = read_waviq(path)
    for a, b in zip(cap.samples[:50], cap2.samples[:50]):
        assert abs(a - b) < 1e-4


def test_wav_sample_rate(tmp_path):
    cap = _small_capture()
    path = str(tmp_path / "cap.wav")
    write_waviq(path, cap)
    cap2 = read_waviq(path)
    assert int(cap2.sample_rate) == int(cap.sample_rate)


def test_wav_center_freq_override(tmp_path):
    cap = _small_capture()
    path = str(tmp_path / "cap.wav")
    write_waviq(path, cap)
    cap2 = read_waviq(path, center_freq=915e6)
    assert cap2.center_freq == 915e6


def test_wav_rejects_non_riff(tmp_path):
    p = tmp_path / "bad.wav"
    p.write_bytes(b"NOTAWAVE" + b"\x00" * 40)
    with pytest.raises(ValueError):
        read_waviq(str(p))


def test_csv_two_column(tmp_path):
    freqs = [0.0, 1.0, 2.0, 3.0]
    powers = [-90.0, -80.0, -70.0, -85.0]
    path = str(tmp_path / "spec.csv")
    write_csv_spectrum(path, freqs, powers)
    cap = read_csv_spectrum(path)
    assert cap.kind == "spectrum"
    assert cap.spectrum_freqs == freqs
    assert cap.spectrum_power == powers


def test_csv_single_column():
    cap = parse_csv_spectrum_text("-90\n-80\n-70\n")
    assert cap.spectrum_power == [-90.0, -80.0, -70.0]
    assert cap.spectrum_freqs == [0.0, 1.0, 2.0]


def test_csv_header_skipped():
    cap = parse_csv_spectrum_text("freq,power\n0,-90\n1,-80\n")
    assert cap.spectrum_power == [-90.0, -80.0]


def test_csv_blank_lines_ignored():
    cap = parse_csv_spectrum_text("0,-90\n\n1,-80\n")
    assert len(cap.spectrum_power) == 2


def test_load_capture_dispatch_sigmf(tmp_path):
    cap = _small_capture()
    base = str(tmp_path / "cap")
    write_sigmf(base, cap)
    loaded = load_capture(base + ".sigmf-meta")
    assert len(loaded.samples) == len(cap.samples)


def test_load_capture_dispatch_wav(tmp_path):
    cap = _small_capture()
    path = str(tmp_path / "cap.wav")
    write_waviq(path, cap)
    loaded = load_capture(path)
    assert len(loaded.samples) == len(cap.samples)


def test_load_capture_dispatch_csv(tmp_path):
    path = str(tmp_path / "s.csv")
    write_csv_spectrum(path, [0.0, 1.0], [-90.0, -80.0])
    loaded = load_capture(path)
    assert loaded.kind == "spectrum"


def test_load_capture_unknown_extension(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"\x00")
    with pytest.raises(ValueError):
        load_capture(str(p))


def test_capture_summary_keys():
    cap = _small_capture()
    s = cap.summary()
    for k in ["kind", "n_samples", "sample_rate", "duration_s", "has_position", "source"]:
        assert k in s


def test_capture_duration():
    cap = Capture(samples=[0j] * 1000, sample_rate=1000.0)
    assert math.isclose(cap.duration, 1.0)


def test_capture_len_spectrum():
    cap = Capture(kind="spectrum", spectrum_power=[1, 2, 3])
    assert len(cap) == 3
