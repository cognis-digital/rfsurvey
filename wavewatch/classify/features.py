"""Signal-statistics feature extraction for emitter fingerprinting.

All features are computed *without demodulating any payload*. They describe the
signal's stability and structure (phase jitter, frequency stability, spectral
flatness, cyclostationary strength), not its information content.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from ..dsp.fft import fft
from ..dsp.util import diff, mean, std, unwrap
from ..io.capture import Capture
from ..detect.model import Emitter

Complex = complex
TWO_PI = 2.0 * math.pi
_MAX_SEG = 4096


def _representative_segment(capture: Capture, emitter: Emitter) -> tuple[List[Complex], float]:
    """Return (segment, center_freq) of the emitter's strongest/longest burst.

    The segment is frequency-shifted so the emitter's carrier sits at DC.
    """
    x = capture.samples
    fs = capture.sample_rate
    n = len(x)
    if n == 0:
        return [], 0.0

    if emitter.bursts:
        longest = max(emitter.bursts, key=lambda b: b.duration)
        i0 = max(0, int(longest.t_start * fs))
        i1 = min(n, int(longest.t_end * fs))
        fc = longest.center
    else:
        i0, i1 = 0, n
        fc = emitter.center_freq

    if i1 - i0 < 8:
        i0, i1 = 0, n
    seg = x[i0:i1]
    if len(seg) > _MAX_SEG:
        seg = seg[:_MAX_SEG]

    # frequency-shift carrier to DC
    if fs > 0 and abs(fc) > 0:
        w = -TWO_PI * fc / fs
        seg = [seg[k] * complex(math.cos(w * k), math.sin(w * k)) for k in range(len(seg))]
    else:
        seg = list(seg)
    return seg, fc


def _linear_detrend(y: Sequence[float]) -> List[float]:
    n = len(y)
    if n < 2:
        return list(y)
    xs = list(range(n))
    mx = (n - 1) / 2.0
    my = mean(y)
    sxx = math.fsum((x - mx) ** 2 for x in xs)
    sxy = math.fsum((xs[i] - mx) * (y[i] - my) for i in range(n))
    slope = sxy / sxx if sxx > 0 else 0.0
    intercept = my - slope * mx
    return [y[i] - (slope * i + intercept) for i in range(n)]


def spectral_flatness(seg: Sequence[Complex]) -> float:
    """Wiener entropy: geometric mean / arithmetic mean of the power spectrum.

    ~1.0 for white/noise-like/OFDM signals, ~0.0 for a pure tone.
    """
    n = len(seg)
    if n < 2:
        return 0.0
    spec = fft(list(seg))
    p = [(v.real * v.real + v.imag * v.imag) + 1e-30 for v in spec]
    am = mean(p)
    if am <= 0:
        return 0.0
    log_gm = mean([math.log(v) for v in p])
    gm = math.exp(log_gm)
    return max(0.0, min(1.0, gm / am))


def cyclo_strength(seg: Sequence[Complex]) -> tuple[float, float]:
    """Crude cyclostationary indicator from the power-envelope spectrum.

    Returns ``(strength, cyclic_freq_bin_frac)``. Strong periodic structure in
    ``|x|^2`` (symbol/hop rate) yields a large peak-to-mean ratio.
    """
    n = len(seg)
    if n < 8:
        return 0.0, 0.0
    env = [(v.real * v.real + v.imag * v.imag) for v in seg]
    m = mean(env)
    env = [e - m for e in env]
    spec = fft([complex(e) for e in env])
    half = n // 2
    mags = [abs(spec[i]) for i in range(1, half)]  # skip DC
    if not mags:
        return 0.0, 0.0
    avg = mean(mags)
    peak = max(mags)
    if avg <= 0:
        return 0.0, 0.0
    peak_idx = mags.index(peak) + 1
    strength = (peak / avg - 1.0) / 20.0  # normalize to ~[0,1] for typical values
    strength = max(0.0, min(1.0, strength))
    return strength, peak_idx / n


def papr(seg: Sequence[Complex]) -> float:
    """Peak-to-average power ratio (linear)."""
    if not seg:
        return 0.0
    p = [(v.real * v.real + v.imag * v.imag) for v in seg]
    avg = mean(p)
    if avg <= 0:
        return 0.0
    return max(p) / avg


def extract_features(capture: Capture, emitter: Emitter) -> Dict[str, float]:
    """Compute the full fingerprint feature dict for one emitter."""
    fs = capture.sample_rate or 1.0
    seg, fc = _representative_segment(capture, emitter)

    bw_frac = emitter.bandwidth_hz / fs if fs > 0 else 0.0

    if len(seg) >= 4:
        phase = unwrap([math.atan2(v.imag, v.real) for v in seg])
        resid = _linear_detrend(phase)
        phase_jitter = std(resid)
        inst = diff(phase)
        # convert rad/sample to Hz then normalize by fs
        inst_hz = [d * fs / TWO_PI for d in inst]
        freq_stability_frac = (std(inst_hz) / fs) if fs > 0 else 0.0
        flat = spectral_flatness(seg)
        cyc, cyc_freq = cyclo_strength(seg)
        p_apr = papr(seg)
    else:
        phase_jitter = 0.0
        freq_stability_frac = 0.0
        flat = 0.0
        cyc, cyc_freq = 0.0, 0.0
        p_apr = 0.0

    return {
        "bandwidth_frac": bw_frac,
        "bandwidth_hz": emitter.bandwidth_hz,
        "duty_cycle": emitter.duty,
        "snr_db": emitter.snr_db,
        "hopping": 1.0 if emitter.hopping else 0.0,
        "n_channels": float(emitter.n_channels),
        "mean_burst_dur_s": emitter.mean_burst_dur,
        "char_burst_dur_s": emitter.char_burst_dur,
        "phase_jitter_rad": phase_jitter,
        "freq_stability_frac": freq_stability_frac,
        "spectral_flatness": flat,
        "cyclo_strength": cyc,
        "cyclo_freq_frac": cyc_freq,
        "papr": p_apr,
        "n_samples_analyzed": float(len(seg)),
    }
