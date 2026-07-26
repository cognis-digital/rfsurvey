"""Frequency-hopping grouping.

Narrowband bands that are individually bursty and scattered across the spectrum
are grouped into a single hopping emitter (the signature of FHSS control links
and channel-hopping protocols).
"""

from __future__ import annotations

from typing import List, Sequence

from .model import Band, Burst, Emitter

HOP_MIN_CHANNELS = 3


def group_emitters(bands: Sequence[Band], band_bursts: Sequence[List[Burst]],
                   band_duty: Sequence[float], fs: float, total_time: float,
                   narrow_frac: float = 0.1, hop_duty_max: float = 0.7) -> List[Emitter]:
    """Combine detected bands into emitters, merging hopping channel sets.

    Parameters
    ----------
    bands : detected bands
    band_bursts : bursts per band (parallel to ``bands``)
    band_duty : duty cycle per band (parallel to ``bands``)
    fs : sample rate
    total_time : capture duration (s)
    narrow_frac : bands narrower than ``narrow_frac * fs`` are 'narrowband'
    hop_duty_max : a hopping channel must be bursty (duty below this)
    """
    narrow_thresh = narrow_frac * fs
    hop_idx: List[int] = []
    other_idx: List[int] = []
    for i, b in enumerate(bands):
        if b.bandwidth < narrow_thresh and band_duty[i] < hop_duty_max:
            hop_idx.append(i)
        else:
            other_idx.append(i)

    emitters: List[Emitter] = []
    next_id = 0

    if len(hop_idx) >= HOP_MIN_CHANNELS:
        # merge into one hopping emitter
        channels = sorted(bands[i].center for i in hop_idx)
        all_bursts: List[Burst] = []
        for i in hop_idx:
            all_bursts.extend(band_bursts[i])
        all_bursts.sort(key=lambda x: x.t_start)
        covered = sum(b.duration for b in all_bursts)
        duty = min(1.0, covered / total_time) if total_time > 0 else 0.0
        bws = sorted(bands[i].bandwidth for i in hop_idx)
        med_bw = bws[len(bws) // 2]
        peak_db = max(bands[i].peak_db for i in hop_idx)
        noise_db = min(bands[i].noise_db for i in hop_idx)
        f_lo = min(bands[i].f_lo for i in hop_idx)
        f_hi = max(bands[i].f_hi for i in hop_idx)
        center = channels[len(channels) // 2]
        emitters.append(Emitter(
            id=next_id,
            center_freq=center,
            bandwidth_hz=med_bw,
            f_lo=f_lo,
            f_hi=f_hi,
            snr_db=peak_db - noise_db,
            duty=duty,
            bursts=all_bursts,
            hopping=True,
            channels=channels,
            peak_db=peak_db,
            noise_db=noise_db,
        ))
        next_id += 1
    else:
        # each 'hop' candidate is its own non-hopping emitter
        other_idx = sorted(other_idx + hop_idx)

    for i in other_idx:
        b = bands[i]
        emitters.append(Emitter(
            id=next_id,
            center_freq=b.center,
            bandwidth_hz=b.bandwidth,
            f_lo=b.f_lo,
            f_hi=b.f_hi,
            snr_db=b.snr_db,
            duty=band_duty[i],
            bursts=list(band_bursts[i]),
            hopping=False,
            channels=[b.center],
            peak_db=b.peak_db,
            noise_db=b.noise_db,
        ))
        next_id += 1

    emitters.sort(key=lambda e: e.center_freq)
    for new_id, e in enumerate(emitters):
        e.id = new_id
    return emitters
