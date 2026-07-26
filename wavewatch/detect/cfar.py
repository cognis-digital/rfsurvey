"""CFAR / energy peak detection and band segmentation on a power spectrum."""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple  # noqa: F401

from ..dsp.util import db10, median, percentile
from .model import Band


def cfar_1d(psd: Sequence[float], guard: int = 2, train: int = 8,
            threshold_db: float = 6.0) -> List[int]:
    """Cell-averaging CFAR peak detector over a 1-D power spectrum.

    For each cell, estimate the local noise level from ``train`` reference cells
    on each side (skipping ``guard`` cells), and flag the cell if it exceeds the
    noise estimate by ``threshold_db`` decibels *and* is a local maximum.

    Returns the indices of detected peaks.
    """
    n = len(psd)
    if n == 0:
        return []
    factor = 10 ** (threshold_db / 10.0)
    peaks: List[int] = []
    for i in range(n):
        lo1 = max(0, i - guard - train)
        lo2 = max(0, i - guard)
        hi1 = min(n, i + guard + 1)
        hi2 = min(n, i + guard + train + 1)
        ref = list(psd[lo1:lo2]) + list(psd[hi1:hi2])
        if not ref:
            continue
        noise = sum(ref) / len(ref)
        if psd[i] > noise * factor:
            left = psd[i - 1] if i > 0 else -math.inf
            right = psd[i + 1] if i < n - 1 else -math.inf
            if psd[i] >= left and psd[i] >= right:
                peaks.append(i)
    return peaks


def estimate_noise_floor(psd: Sequence[float]) -> float:
    """Robust noise-floor estimate: the lower-quartile power level."""
    if not psd:
        return 0.0
    return percentile(list(psd), 25.0)


def detect_bands(freqs: Sequence[float], psd: Sequence[float],
                 threshold_db: float = 6.0, min_bins: int = 1,
                 merge_gap: float = 0.0) -> List[Band]:
    """Segment occupied spectrum into contiguous :class:`Band` objects.

    A bin is 'occupied' if it exceeds the noise floor by ``threshold_db`` dB.
    Runs of occupied bins become bands; runs separated by a frequency gap
    smaller than ``merge_gap`` (Hz) are merged (so a bumpy wideband hump becomes
    a single band). Each band records its peak power/SNR.
    """
    n = len(psd)
    if n == 0:
        return []
    floor = estimate_noise_floor(psd)
    floor_db = db10(floor) if floor > 0 else db10(max(psd) * 1e-6 + 1e-30)
    thresh = floor * (10 ** (threshold_db / 10.0))
    dfb = abs(freqs[1] - freqs[0]) if n > 1 else 1.0

    occupied = [p > thresh for p in psd]
    # collect [start, stop) index runs of occupied bins
    runs: List[Tuple[int, int]] = []
    i = 0
    while i < n:
        if occupied[i]:
            j = i
            while j < n and occupied[j]:
                j += 1
            runs.append((i, j))
            i = j
        else:
            i += 1

    if not runs:
        return []

    # merge runs whose frequency gap is below merge_gap
    merged: List[Tuple[int, int]] = [runs[0]]
    for start, stop in runs[1:]:
        prev_start, prev_stop = merged[-1]
        gap = freqs[start] - freqs[prev_stop - 1]
        if gap <= merge_gap:
            merged[-1] = (prev_start, stop)
        else:
            merged.append((start, stop))

    bands: List[Band] = []
    for start, stop in merged:
        if (stop - start) < min_bins:
            continue
        seg = list(psd[start:stop])
        peak_local = max(seg)
        peak_idx = start + seg.index(peak_local)
        f_lo = freqs[start]
        f_hi = freqs[stop - 1]
        if f_hi < f_lo:
            f_lo, f_hi = f_hi, f_lo
        if stop - start == 1 and n > 1:
            f_lo -= dfb / 2.0
            f_hi += dfb / 2.0
        bands.append(Band(
            f_lo=f_lo,
            f_hi=f_hi,
            center=freqs[peak_idx],
            peak_power=peak_local,
            peak_db=db10(peak_local),
            noise_db=floor_db,
        ))
    return bands
