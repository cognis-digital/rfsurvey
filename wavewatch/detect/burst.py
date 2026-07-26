"""Burst segmentation: find time-contiguous active segments within a band."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from ..dsp.spectrogram import Spectrogram
from ..dsp.util import percentile
from .model import Band, Burst


def _band_bins(freqs: Sequence[float], f_lo: float, f_hi: float) -> Tuple[int, int]:
    """Return [lo, hi) bin indices overlapping the frequency range."""
    lo = None
    hi = None
    for i, f in enumerate(freqs):
        if f_lo <= f <= f_hi:
            if lo is None:
                lo = i
            hi = i
    if lo is None:
        # nearest single bin to band center
        center = 0.5 * (f_lo + f_hi)
        nearest = min(range(len(freqs)), key=lambda i: abs(freqs[i] - center))
        return nearest, nearest + 1
    return lo, hi + 1


def band_frame_power(spec: Spectrogram, band: Band) -> List[float]:
    """Per-frame summed power within the band's frequency span."""
    lo, hi = _band_bins(spec.freqs, band.f_lo, band.f_hi)
    out: List[float] = []
    for row in spec.power:
        out.append(sum(row[lo:hi]))
    return out


def segment_bursts(spec: Spectrogram, band: Band, threshold_db: float = 6.0,
                   min_frames: int = 1, bridge_frames: int = 3) -> List[Burst]:
    """Segment a band's activity over time into bursts.

    A frame is 'active' when its in-band power exceeds a per-band floor (the
    lower quartile of the frame-power series) by ``threshold_db`` dB. Short
    inactive gaps (< ``bridge_frames``) between active runs are bridged so a
    single dwell is not fragmented by windowing ripple.
    """
    series = band_frame_power(spec, band)
    n = len(series)
    if n == 0:
        return []
    floor = percentile(series, 25.0)
    peak = max(series)
    if floor <= 0:
        floor = peak * 1e-6 + 1e-30
    thresh = floor * (10 ** (threshold_db / 10.0))
    # If the band is continuously on, floor ~ peak; guarantee detection of a
    # strong continuous signal by also accepting anything above a fraction of peak.
    if peak > 0:
        thresh = min(thresh, 0.3 * peak)

    active = [v > thresh for v in series]

    # bridge short inactive gaps between active frames
    if bridge_frames > 0:
        i = 0
        last_active = -1
        for i in range(n):
            if active[i]:
                if 0 <= last_active < i - 1 and (i - last_active - 1) <= bridge_frames:
                    for k in range(last_active + 1, i):
                        active[k] = True
                last_active = i

    bursts: List[Burst] = []
    i = 0
    dt = (spec.times[1] - spec.times[0]) if len(spec.times) > 1 else \
        (spec.nperseg / spec.fs if spec.fs else 1.0)
    while i < n:
        if active[i]:
            j = i
            while j < n and active[j]:
                j += 1
            if (j - i) >= min_frames:
                t0 = spec.times[i] - dt / 2.0
                t1 = spec.times[j - 1] + dt / 2.0
                bursts.append(Burst(
                    t_start=max(0.0, t0),
                    t_end=t1,
                    frame_start=i,
                    frame_end=j,
                    center=band.center,
                ))
            i = j
        else:
            i += 1
    return bursts


def duty_cycle(bursts: Sequence[Burst], total_time: float) -> float:
    """Fraction of ``total_time`` covered by bursts."""
    if total_time <= 0 or not bursts:
        return 0.0
    covered = sum(b.duration for b in bursts)
    return min(1.0, covered / total_time)
