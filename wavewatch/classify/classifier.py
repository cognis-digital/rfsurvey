"""Rule-based emitter classifier with an explainable decision trace.

Emitters are scored against interpretable membership rules built from the
fingerprint features. The highest-scoring class wins; every score, threshold,
and contributing feature is recorded so a decision can be reproduced and audited.

Classes: ``drone-link``, ``wifi``, ``ble``, ``gnss``, ``unknown``.

This is a heuristic triage classifier. It never demodulates a payload and makes
no claim of protocol-decode certainty -- it labels *signatures*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from ..io.capture import Capture
from ..detect.model import Emitter
from .features import extract_features

CLASSES = ["drone-link", "wifi", "ble", "gnss", "unknown"]
MIN_CONFIDENCE = 0.35

# Named thresholds -- surfaced in the decision trace for reproducibility.
THRESHOLDS = {
    "narrowband_frac": 0.12,
    "wideband_frac": 0.25,
    "gnss_wide_frac": 0.30,
    "hop_min_channels": 4.0,
    "ble_burst_max_s": 4.0e-4,
    "drone_burst_min_s": 1.0e-3,
    "gnss_snr_max_db": 12.0,
    "wifi_snr_min_db": 8.0,
    "continuous_duty": 0.85,
    "min_confidence": MIN_CONFIDENCE,
}


@dataclass
class Classification:
    """Result of classifying a single emitter."""

    label: str
    confidence: float
    scores: Dict[str, float]
    features: Dict[str, float]
    thresholds: Dict[str, float]
    trace: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "features": {k: round(v, 6) for k, v in self.features.items()},
            "thresholds": self.thresholds,
            "decision_trace": self.trace,
        }


def _ramp_up(x: float, a: float, b: float) -> float:
    if b <= a:
        return 1.0 if x >= b else 0.0
    if x <= a:
        return 0.0
    if x >= b:
        return 1.0
    return (x - a) / (b - a)


def _ramp_down(x: float, a: float, b: float) -> float:
    return 1.0 - _ramp_up(x, a, b)


def _band(x: float, lo: float, hi: float, skirt: float = 0.15) -> float:
    if lo <= x <= hi:
        return 1.0
    if x < lo:
        return max(0.0, 1.0 - (lo - x) / max(skirt, 1e-9))
    return max(0.0, 1.0 - (x - hi) / max(skirt, 1e-9))


def _score_classes(f: Dict[str, float]) -> Dict[str, float]:
    bw = f["bandwidth_frac"]
    duty = f["duty_cycle"]
    snr = f["snr_db"]
    hop = f["hopping"]
    nch = f["n_channels"]
    burst = f.get("char_burst_dur_s", f["mean_burst_dur_s"])
    flat = f["spectral_flatness"]
    freq_stab = f["freq_stability_frac"]
    phase_jit = f["phase_jitter_rad"]

    not_hop = 1.0 - hop

    drone = _mean([
        hop,
        _ramp_up(nch, 2.0, 4.0),
        _ramp_down(bw, 0.06, 0.15),
        _ramp_up(burst, 5.0e-4, 1.5e-3),
    ])
    ble = _mean([
        hop,
        _ramp_up(nch, 2.0, 4.0),
        _ramp_down(bw, 0.05, 0.12),
        _ramp_down(burst, 1.0e-4, 4.0e-4),
    ])
    wifi = _mean([
        not_hop,
        _ramp_up(bw, 0.20, 0.35),
        _ramp_up(flat, 0.20, 0.50),
        _band(duty, 0.10, 0.85, skirt=0.15),
        _ramp_up(snr, 8.0, 20.0),
    ])
    gnss = _mean([
        not_hop,
        _ramp_up(bw, 0.30, 0.50),
        _ramp_up(duty, 0.70, 0.95),
        _ramp_down(snr, 8.0, 20.0),
        _ramp_up(phase_jit, 0.30, 1.00),
    ])
    unknown = _mean([
        _ramp_down(bw, 0.05, 0.12),
        _ramp_up(duty, 0.70, 0.95),
        _ramp_down(freq_stab, 0.001, 0.02),
        not_hop,
    ])
    unknown = max(unknown, 0.25)  # floor: default to unknown when nothing fits

    return {
        "drone-link": drone,
        "wifi": wifi,
        "ble": ble,
        "gnss": gnss,
        "unknown": unknown,
    }


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def classify_features(features: Dict[str, float]) -> Classification:
    """Classify from a pre-computed feature dict."""
    scores = _score_classes(features)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    label, top = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
    margin = top - runner_up

    if top < MIN_CONFIDENCE:
        label = "unknown"
        top = scores["unknown"]

    # confidence blends absolute score and separation from the runner-up
    confidence = max(0.0, min(0.99, 0.65 * top + 0.35 * min(1.0, top + margin)))

    trace = _build_trace(features, scores, label, margin)
    return Classification(
        label=label,
        confidence=confidence,
        scores=scores,
        features=features,
        thresholds=dict(THRESHOLDS),
        trace=trace,
    )


def classify_emitter(capture: Capture, emitter: Emitter) -> Classification:
    """Extract features for an emitter and classify it."""
    features = extract_features(capture, emitter)
    return classify_features(features)


def _build_trace(f: Dict[str, float], scores: Dict[str, float],
                 label: str, margin: float) -> List[str]:
    t: List[str] = []
    t.append(
        f"bandwidth={f['bandwidth_frac']:.3f} of fs; duty={f['duty_cycle']:.2f}; "
        f"snr={f['snr_db']:.1f} dB; hopping={bool(f['hopping'])}; "
        f"channels={int(f['n_channels'])}; burst={f['mean_burst_dur_s']*1e3:.3f} ms"
    )
    t.append(
        f"phase_jitter={f['phase_jitter_rad']:.3f} rad; "
        f"freq_stability={f['freq_stability_frac']:.4f} of fs; "
        f"flatness={f['spectral_flatness']:.3f}; cyclo={f['cyclo_strength']:.3f}"
    )
    if f["hopping"]:
        if f["mean_burst_dur_s"] < THRESHOLDS["ble_burst_max_s"]:
            t.append(
                f"hopping with short bursts (<{THRESHOLDS['ble_burst_max_s']*1e3:.2f} ms) "
                f"-> BLE-like channel hopping"
            )
        else:
            t.append(
                f"hopping with ms-scale dwell (>{THRESHOLDS['drone_burst_min_s']*1e3:.2f} ms) "
                f"-> FHSS control-link signature"
            )
    if f["bandwidth_frac"] > THRESHOLDS["wideband_frac"]:
        if f["duty_cycle"] > THRESHOLDS["continuous_duty"] and f["snr_db"] < THRESHOLDS["gnss_snr_max_db"]:
            t.append("wideband + continuous + low SNR -> noise-like spread-spectrum (GNSS-like)")
        else:
            t.append("wideband + bursty + higher SNR -> OFDM-like (Wi-Fi signature)")
    ranked = ", ".join(f"{k}={v:.3f}" for k, v in
                       sorted(scores.items(), key=lambda kv: kv[1], reverse=True))
    t.append(f"class scores: {ranked}")
    t.append(f"decision: {label} (margin over runner-up = {margin:.3f})")
    return t
