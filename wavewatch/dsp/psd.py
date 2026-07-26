"""Power spectral density estimation: periodogram and Welch's method.

Pure Python, built on :mod:`wavewatch.dsp.fft`. Handles complex IQ (two-sided
spectrum) and real signals (one-sided).
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

from .fft import fft, fftfreq, fftshift
from .window import get_window

Complex = complex


def _apply_window(seg: Sequence[Complex], win: Sequence[float]) -> List[Complex]:
    return [complex(seg[i]) * win[i] for i in range(len(seg))]


def _window_power(win: Sequence[float]) -> float:
    return math.fsum(w * w for w in win)


def periodogram(
    x: Sequence[Complex],
    fs: float = 1.0,
    window: str = "hann",
    detrend: bool = False,
    shift: bool = True,
) -> Tuple[List[float], List[float]]:
    """Single-segment periodogram PSD estimate.

    Returns ``(freqs, psd)``. For complex input the two-sided spectrum is
    returned (centered when ``shift`` is True).
    """
    n = len(x)
    if n == 0:
        return [], []
    seg = [complex(v) for v in x]
    if detrend:
        m = sum(seg) / n
        seg = [v - m for v in seg]
    win = get_window(window, n)
    wpow = _window_power(win)
    scale = 1.0 / (fs * wpow) if fs > 0 and wpow > 0 else 0.0
    spec = fft(_apply_window(seg, win))
    psd = [(v.real * v.real + v.imag * v.imag) * scale for v in spec]
    freqs = fftfreq(n, 1.0 / fs)
    if shift:
        freqs = fftshift(freqs)
        psd = fftshift(psd)
    return freqs, psd


def welch(
    x: Sequence[Complex],
    fs: float = 1.0,
    nperseg: int = 256,
    noverlap: int | None = None,
    window: str = "hann",
    detrend: bool = True,
    shift: bool = True,
) -> Tuple[List[float], List[float]]:
    """Welch's averaged, modified periodogram PSD estimate.

    Returns ``(freqs, psd)``. Segments are windowed, transformed, and averaged.
    """
    n = len(x)
    if n == 0:
        return [], []
    if nperseg > n:
        nperseg = n
    if nperseg <= 0:
        nperseg = 1
    if noverlap is None:
        noverlap = nperseg // 2
    if noverlap >= nperseg:
        noverlap = nperseg - 1
    if noverlap < 0:
        noverlap = 0
    step = nperseg - noverlap
    win = get_window(window, nperseg)
    wpow = _window_power(win)
    scale = 1.0 / (fs * wpow) if fs > 0 and wpow > 0 else 0.0

    accum = [0.0] * nperseg
    count = 0
    start = 0
    while start + nperseg <= n:
        seg = [complex(x[start + i]) for i in range(nperseg)]
        if detrend:
            m = sum(seg) / nperseg
            seg = [v - m for v in seg]
        spec = fft(_apply_window(seg, win))
        for i in range(nperseg):
            v = spec[i]
            accum[i] += (v.real * v.real + v.imag * v.imag) * scale
        count += 1
        start += step
    if count == 0:
        # Signal shorter than one segment: fall back to a single periodogram.
        return periodogram(x, fs=fs, window=window, detrend=detrend, shift=shift)
    psd = [a / count for a in accum]
    freqs = fftfreq(nperseg, 1.0 / fs)
    if shift:
        freqs = fftshift(freqs)
        psd = fftshift(psd)
    return freqs, psd


def average_psd_db(
    x: Sequence[Complex],
    fs: float = 1.0,
    nperseg: int = 256,
    window: str = "hann",
) -> Tuple[List[float], List[float]]:
    """Welch PSD converted to dB. Returns ``(freqs, psd_db)``."""
    freqs, psd = welch(x, fs=fs, nperseg=nperseg, window=window)
    from .util import to_db

    return freqs, to_db(psd)
