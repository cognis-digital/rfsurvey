"""Short-time Fourier transform and spectrogram (pure Python)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from .fft import fft, fftfreq, fftshift
from .window import get_window

Complex = complex


@dataclass
class Spectrogram:
    """Result of :func:`spectrogram`.

    Attributes
    ----------
    freqs : list of float
        Frequency bin centers (Hz), centered around 0 for complex input.
    times : list of float
        Frame center times (seconds).
    power : list of list of float
        ``power[t][f]`` linear power at frame ``t``, bin ``f``.
    fs : float
        Sample rate.
    nperseg, noverlap : int
        STFT parameters used.
    """

    freqs: List[float]
    times: List[float]
    power: List[List[float]]
    fs: float
    nperseg: int
    noverlap: int

    @property
    def n_frames(self) -> int:
        return len(self.power)

    @property
    def n_bins(self) -> int:
        return len(self.freqs)

    def frame_power(self) -> List[float]:
        """Total power per time frame (sum across frequency bins)."""
        return [math.fsum(row) for row in self.power]

    def average_spectrum(self) -> List[float]:
        """Time-averaged power spectrum (mean across frames)."""
        if not self.power:
            return [0.0] * len(self.freqs)
        nb = len(self.freqs)
        acc = [0.0] * nb
        for row in self.power:
            for i in range(nb):
                acc[i] += row[i]
        nf = len(self.power)
        return [a / nf for a in acc]


def stft(
    x: Sequence[Complex],
    nperseg: int = 256,
    noverlap: int | None = None,
    window: str = "hann",
    detrend: bool = False,
) -> List[List[Complex]]:
    """Short-time Fourier transform.

    Returns a list of complex spectra, one per frame (each ``nperseg`` long).
    """
    n = len(x)
    if n == 0:
        return []
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
    frames: List[List[Complex]] = []
    start = 0
    while start + nperseg <= n:
        seg = [complex(x[start + i]) * win[i] for i in range(nperseg)]
        if detrend:
            m = sum(seg) / nperseg
            seg = [v - m for v in seg]
        frames.append(fft(seg))
        start += step
    return frames


def spectrogram(
    x: Sequence[Complex],
    fs: float = 1.0,
    nperseg: int = 256,
    noverlap: int | None = None,
    window: str = "hann",
    shift: bool = True,
) -> Spectrogram:
    """Compute a spectrogram (linear power) from an IQ/real signal."""
    n = len(x)
    if nperseg > max(1, n):
        nperseg = max(1, n)
    if noverlap is None:
        noverlap = nperseg // 2
    if noverlap >= nperseg:
        noverlap = nperseg - 1
    if noverlap < 0:
        noverlap = 0
    step = nperseg - noverlap

    win = get_window(window, nperseg)
    wpow = math.fsum(w * w for w in win)
    scale = 1.0 / (fs * wpow) if fs > 0 and wpow > 0 else 1.0

    frames = stft(x, nperseg=nperseg, noverlap=noverlap, window=window)
    power_rows: List[List[float]] = []
    for spec in frames:
        row = [(v.real * v.real + v.imag * v.imag) * scale for v in spec]
        if shift:
            row = fftshift(row)
        power_rows.append(row)

    freqs = fftfreq(nperseg, 1.0 / fs)
    if shift:
        freqs = fftshift(freqs)

    times: List[float] = []
    for k in range(len(frames)):
        center = (k * step + nperseg / 2.0) / fs if fs > 0 else float(k)
        times.append(center)

    return Spectrogram(
        freqs=freqs,
        times=times,
        power=power_rows,
        fs=fs,
        nperseg=nperseg,
        noverlap=noverlap,
    )
