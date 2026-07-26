"""Tests for STFT and spectrogram."""

from __future__ import annotations

import cmath
import math

import pytest

from wavewatch.dsp.spectrogram import Spectrogram, spectrogram, stft
from tests.conftest import random_complex

FS = 1_000_000.0


@pytest.mark.parametrize("nperseg", [32, 64, 128, 256])
def test_stft_frame_length(nperseg):
    x = random_complex(2048, seed=nperseg)
    frames = stft(x, nperseg=nperseg)
    assert all(len(f) == nperseg for f in frames)


def test_stft_empty():
    assert stft([]) == []


@pytest.mark.parametrize("nperseg,noverlap", [(64, 32), (128, 64), (256, 128), (64, 0)])
def test_spectrogram_shape(nperseg, noverlap):
    x = random_complex(4096, seed=1)
    spec = spectrogram(x, fs=FS, nperseg=nperseg, noverlap=noverlap)
    assert spec.n_bins == nperseg
    assert spec.n_frames > 0
    assert all(len(row) == nperseg for row in spec.power)


def test_spectrogram_nonnegative_power():
    x = random_complex(2048, seed=2)
    spec = spectrogram(x, fs=FS, nperseg=128)
    for row in spec.power:
        assert all(v >= 0 for v in row)


def test_spectrogram_times_increasing():
    x = random_complex(2048, seed=3)
    spec = spectrogram(x, fs=FS, nperseg=128)
    for i in range(1, len(spec.times)):
        assert spec.times[i] > spec.times[i - 1]


def test_spectrogram_frame_power_matches():
    x = random_complex(1024, seed=4)
    spec = spectrogram(x, fs=FS, nperseg=128)
    fp = spec.frame_power()
    assert len(fp) == spec.n_frames
    for i, row in enumerate(spec.power):
        assert math.isclose(fp[i], math.fsum(row), rel_tol=1e-9)


def test_spectrogram_average_spectrum_length():
    x = random_complex(1024, seed=5)
    spec = spectrogram(x, fs=FS, nperseg=64)
    assert len(spec.average_spectrum()) == 64


def test_spectrogram_tone_energy_localized():
    n = 4096
    fs = 1_000_000.0
    f0 = 125_000.0
    x = [cmath.exp(2j * math.pi * f0 * k / fs) for k in range(n)]
    spec = spectrogram(x, fs=fs, nperseg=256, window="hann")
    avg = spec.average_spectrum()
    peak_idx = avg.index(max(avg))
    assert abs(spec.freqs[peak_idx] - f0) < fs / 256 * 3


def test_spectrogram_empty_signal():
    spec = spectrogram([], fs=FS, nperseg=128)
    assert spec.n_frames == 0


def test_spectrogram_short_signal():
    x = random_complex(50, seed=6)
    spec = spectrogram(x, fs=FS, nperseg=256)
    assert spec.nperseg <= 50


def test_spectrogram_dataclass_fields():
    x = random_complex(512, seed=7)
    spec = spectrogram(x, fs=FS, nperseg=128)
    assert isinstance(spec, Spectrogram)
    assert spec.fs == FS
    assert spec.nperseg == 128
