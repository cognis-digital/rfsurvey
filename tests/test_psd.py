"""Tests for PSD estimation (periodogram, Welch)."""

from __future__ import annotations

import cmath
import math

import pytest

from wavewatch.dsp.psd import average_psd_db, periodogram, welch
from tests.conftest import random_complex

FS = 1000.0


@pytest.mark.parametrize("n", [16, 32, 64, 128, 256])
def test_periodogram_length(n):
    x = random_complex(n, seed=n)
    freqs, psd = periodogram(x, fs=FS)
    assert len(freqs) == n
    assert len(psd) == n


@pytest.mark.parametrize("n", [16, 32, 64, 128])
def test_periodogram_nonnegative(n):
    x = random_complex(n, seed=n)
    _, psd = periodogram(x, fs=FS)
    assert all(p >= 0 for p in psd)


def test_periodogram_empty():
    freqs, psd = periodogram([], fs=FS)
    assert freqs == [] and psd == []


def test_periodogram_tone_peak_location():
    n = 128
    fs = 1000.0
    f0 = 125.0  # a bin center
    x = [cmath.exp(2j * math.pi * f0 * k / fs) for k in range(n)]
    freqs, psd = periodogram(x, fs=fs, window="rectangular", shift=True)
    peak_idx = psd.index(max(psd))
    assert abs(freqs[peak_idx] - f0) < fs / n * 1.5


@pytest.mark.parametrize("nperseg", [16, 32, 64])
def test_welch_length(nperseg):
    x = random_complex(1024, seed=1)
    freqs, psd = welch(x, fs=FS, nperseg=nperseg)
    assert len(freqs) == nperseg
    assert len(psd) == nperseg


@pytest.mark.parametrize("nperseg", [16, 32, 64, 128])
def test_welch_nonnegative(nperseg):
    x = random_complex(1024, seed=2)
    _, psd = welch(x, fs=FS, nperseg=nperseg)
    assert all(p >= 0 for p in psd)


def test_welch_empty():
    freqs, psd = welch([], fs=FS)
    assert freqs == [] and psd == []


def test_welch_short_signal_falls_back():
    x = random_complex(10, seed=3)
    freqs, psd = welch(x, fs=FS, nperseg=256)
    assert len(psd) == len(x)


def test_welch_reduces_variance_vs_periodogram():
    # Welch averaging should give a smoother (lower-variance) estimate.
    from wavewatch.dsp.util import std
    x = random_complex(2048, seed=5)
    _, p_per = periodogram(x, fs=FS)
    _, p_wel = welch(x, fs=FS, nperseg=128)
    assert std(p_wel) < std(p_per)


def test_welch_tone_peak():
    n = 2048
    fs = 1000.0
    f0 = 250.0
    x = [cmath.exp(2j * math.pi * f0 * k / fs) for k in range(n)]
    freqs, psd = welch(x, fs=fs, nperseg=256, window="hann")
    peak_idx = psd.index(max(psd))
    assert abs(freqs[peak_idx] - f0) < 20.0


def test_average_psd_db_length():
    x = random_complex(512, seed=7)
    freqs, psd_db = average_psd_db(x, fs=FS, nperseg=64)
    assert len(freqs) == 64
    assert len(psd_db) == 64


@pytest.mark.parametrize("noverlap", [0, 16, 32, 48])
def test_welch_overlap_variants(noverlap):
    x = random_complex(512, seed=9)
    _, psd = welch(x, fs=FS, nperseg=64, noverlap=noverlap)
    assert len(psd) == 64
