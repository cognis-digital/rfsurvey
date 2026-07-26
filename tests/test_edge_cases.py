"""Edge cases: empty captures, DC-only, pure noise, clipping, tiny signals."""

from __future__ import annotations

import pytest

from wavewatch.analyze import analyze_capture
from wavewatch.detect.pipeline import detect_emitters
from wavewatch.dsp.fft import fft
from wavewatch.dsp.spectrogram import spectrogram
from wavewatch.io.capture import Capture
from wavewatch.io.generator import complex_noise, tone


def _cap(samples, fs=1_000_000.0, center=0.0):
    return Capture(samples=list(samples), sample_rate=fs, center_freq=center)


def test_empty_capture_analyze():
    rep = analyze_capture(_cap([]))
    assert rep.summary()["n_emitters"] == 0


def test_empty_capture_detect():
    det = detect_emitters(_cap([]))
    assert det.emitters == []
    assert det.spectrogram is None


def test_dc_only_signal():
    # constant (DC) signal: energy only at bin 0
    rep = analyze_capture(_cap([1 + 0j] * 4096))
    # should not crash; may or may not detect an emitter at DC
    assert isinstance(rep.summary()["n_emitters"], int)


def test_dc_only_spectrogram():
    spec = spectrogram([1 + 0j] * 1024, fs=1e6, nperseg=128)
    assert spec.n_frames > 0


def test_pure_noise_few_emitters():
    rep = analyze_capture(_cap(complex_noise(8192, 1.0)))
    # pure noise should not produce a forest of false emitters
    assert rep.summary()["n_emitters"] <= 2


def test_clipping_signal_no_crash():
    # heavily clipped / saturated samples
    n = 4096
    sig = tone(n, 100_000.0, 1e6, amp=1000.0)
    clipped = [complex(max(-1.0, min(1.0, s.real)), max(-1.0, min(1.0, s.imag))) for s in sig]
    rep = analyze_capture(_cap(clipped))
    assert isinstance(rep.to_dict(), dict)


def test_all_zeros_signal():
    rep = analyze_capture(_cap([0j] * 4096))
    assert rep.summary()["n_emitters"] == 0


def test_single_sample_capture():
    rep = analyze_capture(_cap([1 + 0j]))
    assert isinstance(rep.summary()["n_emitters"], int)


def test_two_sample_capture():
    rep = analyze_capture(_cap([1 + 0j, 0 + 1j]))
    assert isinstance(rep.to_dict(), dict)


def test_very_short_capture_no_crash():
    for n in range(1, 20):
        rep = analyze_capture(_cap(complex_noise(n, 1.0)))
        assert isinstance(rep.summary()["n_emitters"], int)


def test_fft_of_zeros():
    assert fft([0j] * 8) == [0j] * 8


def test_nperseg_larger_than_signal():
    rep = analyze_capture(_cap(complex_noise(100, 1.0)), nperseg=1024)
    assert isinstance(rep.to_dict(), dict)


def test_negative_and_large_amplitudes():
    n = 2048
    sig = [complex(1e6, -1e6)] * n
    rep = analyze_capture(_cap(sig))
    assert isinstance(rep.to_dict(), dict)


def test_spectrum_capture_empty():
    cap = Capture(kind="spectrum", spectrum_freqs=[], spectrum_power=[])
    det = detect_emitters(cap)
    assert det.emitters == []


def test_analyze_deterministic():
    s = complex_noise(4096, 1.0, __import__("random").Random(7))
    a = analyze_capture(_cap(s)).summary()
    b = analyze_capture(_cap(s)).summary()
    assert a == b
