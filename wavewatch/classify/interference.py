"""Interference detection: jamming *signatures* and GNSS-spoofing *hints*.

DETECTION ONLY. These routines flag the spectral signatures of interference so
an analyst or automated pipeline can triage a link's health. wavewatch does not
generate, transmit, or counter any signal -- there is no jamming capability here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..dsp.spectrogram import Spectrogram
from ..dsp.util import diff, mean, percentile, std
from ..detect.model import Emitter
from ..io.capture import Capture

# GNSS downlink center frequencies (Hz) where received power should be low/noise-like.
GNSS_BANDS = {
    "GPS L1 / Galileo E1": 1_575_420_000.0,
    "GPS L2": 1_227_600_000.0,
    "GPS L5 / Galileo E5a": 1_176_450_000.0,
    "GLONASS L1": 1_602_000_000.0,
}
GNSS_BAND_TOL = 30_000_000.0


@dataclass
class InterferenceFlag:
    kind: str
    severity: str            # "info" | "low" | "medium" | "high"
    confidence: float
    message: str
    evidence: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "confidence": round(self.confidence, 4),
            "message": self.message,
            "evidence": self.evidence,
        }


def _frame_peak_freqs(spec: Spectrogram, floor: float, factor: float = 4.0):
    """Return (peak_freqs, occupancy, peak_ratio_db) per frame."""
    peaks: List[Optional[float]] = []
    occ: List[float] = []
    ratio_db: List[float] = []
    thresh = floor * factor
    for row in spec.power:
        if not row:
            peaks.append(None)
            occ.append(0.0)
            ratio_db.append(0.0)
            continue
        pmax = max(row)
        idx = row.index(pmax)
        peaks.append(spec.freqs[idx])
        above = sum(1 for v in row if v > thresh)
        occ.append(above / len(row))
        med = percentile(row, 50.0)
        ratio_db.append(10.0 * math.log10(pmax / med) if med > 0 and pmax > 0 else 0.0)
    return peaks, occ, ratio_db


def detect_sweep_jamming(spec: Optional[Spectrogram]) -> Optional[InterferenceFlag]:
    """Flag a swept-carrier (chirp) jamming signature.

    Signature: a *strong, narrow* instantaneous peak whose center frequency
    migrates *coherently* (long same-direction runs) across a *wide* span over
    time -- low per-frame occupancy, high time-integrated coverage, and a clearly
    directional peak track (this last test rejects random noise-peak jitter).
    """
    if spec is None or spec.n_frames < 6 or spec.n_bins < 8:
        return None
    all_power = [v for row in spec.power for v in row]
    floor = percentile(all_power, 25.0)
    if floor <= 0:
        floor = (max(all_power) * 1e-6) + 1e-30
    peaks, occ, ratio_db = _frame_peak_freqs(spec, floor)
    valid = [p for p in peaks if p is not None]
    if len(valid) < 6:
        return None

    span = spec.freqs[-1] - spec.freqs[0]
    if span <= 0:
        return None
    coverage = (max(valid) - min(valid)) / span
    mean_occ = mean(occ)
    strong_peak = mean(ratio_db)  # dB above per-frame median

    # coherence: fraction of steps that continue in the same direction as the
    # previous step. A chirp sawtooth -> high; random noise peaks -> ~0.5.
    steps = diff(valid)
    signs = [1 if s > 0 else (-1 if s < 0 else 0) for s in steps]
    same_dir = 0
    total = 0
    for i in range(1, len(signs)):
        if signs[i] != 0 and signs[i - 1] != 0:
            total += 1
            if signs[i] == signs[i - 1]:
                same_dir += 1
    coherence = (same_dir / total) if total > 0 else 0.0

    is_sweep = (coverage > 0.5 and mean_occ < 0.5 and strong_peak > 8.0
                and coherence > 0.6)
    if not is_sweep:
        return None
    confidence = min(0.98, 0.3 + 0.4 * coverage + 0.3 * coherence)
    return InterferenceFlag(
        kind="sweep_jamming",
        severity="high",
        confidence=max(0.3, confidence),
        message="Swept narrowband carrier traversing the band (sweep-jamming signature).",
        evidence={
            "frequency_coverage": round(coverage, 3),
            "mean_instantaneous_occupancy": round(mean_occ, 3),
            "track_coherence": round(coherence, 3),
            "peak_above_median_db": round(strong_peak, 2),
        },
    )


def detect_barrage_jamming(emitters: Sequence[Emitter], fs: float,
                           features_by_id: Optional[Dict[int, Dict[str, float]]] = None
                           ) -> Optional[InterferenceFlag]:
    """Flag broadband high-power (barrage) jamming.

    Signature: a *wideband*, *continuous*, high-power (high-SNR), noise-like
    emitter occupying a large fraction of the band -- energy dumped across the
    whole channel rather than a structured transmission. Distinguished from a
    weak, noise-like GNSS hump by its high SNR.
    """
    features_by_id = features_by_id or {}
    if fs <= 0:
        return None
    for e in emitters:
        bw_frac = e.bandwidth_hz / fs
        if bw_frac >= 0.5 and e.duty >= 0.85 and e.snr_db >= 15.0 and not e.hopping:
            feats = features_by_id.get(e.id, {})
            flat = feats.get("spectral_flatness", 1.0)
            confidence = min(0.98, 0.5 + (e.snr_db - 15.0) / 40.0)
            return InterferenceFlag(
                kind="barrage_jamming",
                severity="high",
                confidence=max(0.4, confidence),
                message="Sustained broadband high-power energy across the band "
                        "(barrage-jamming signature).",
                evidence={
                    "emitter_id": e.id,
                    "bandwidth_frac": round(bw_frac, 3),
                    "duty_cycle": round(e.duty, 3),
                    "snr_db": round(e.snr_db, 2),
                    "spectral_flatness": round(flat, 3),
                },
            )
    return None


def detect_gnss_spoof_hint(capture: Capture, emitters: Sequence[Emitter],
                           features_by_id: Dict[int, Dict[str, float]]) -> List[InterferenceFlag]:
    """Flag hints of GNSS spoofing.

    Real received GNSS is a weak, noise-like spread-spectrum signal. An
    abnormally *strong* and *clean* (low phase-jitter, high SNR) emitter sitting
    in a GNSS band is a spoofing hint -- not proof.
    """
    flags: List[InterferenceFlag] = []
    cf = capture.center_freq
    band_name = None
    for name, f0 in GNSS_BANDS.items():
        if abs(cf - f0) <= GNSS_BAND_TOL:
            band_name = name
            break
    if band_name is None:
        return flags

    for e in emitters:
        feats = features_by_id.get(e.id, {})
        snr = e.snr_db
        jitter = feats.get("phase_jitter_rad", 1.0)
        stable = feats.get("freq_stability_frac", 1.0)
        # too strong + too clean for genuine GNSS
        if snr > 15.0 and jitter < 0.3 and stable < 0.01:
            conf = min(0.95, 0.3 + (snr - 15.0) / 40.0 + (0.3 - jitter))
            flags.append(InterferenceFlag(
                kind="gnss_spoof_hint",
                severity="medium",
                confidence=max(0.3, conf),
                message=(f"Unusually strong, stable emitter in {band_name} band "
                         f"-- possible GNSS spoofing (hint, not confirmation)."),
                evidence={
                    "band": band_name,
                    "emitter_id": e.id,
                    "snr_db": round(snr, 2),
                    "phase_jitter_rad": round(jitter, 4),
                    "freq_stability_frac": round(stable, 5),
                    "interop_note": "cross-check with spoofwatch for confirmation",
                },
            ))
    return flags


def scan_interference(capture: Capture, spec: Optional[Spectrogram],
                      psd: Optional[Sequence[float]], emitters: Sequence[Emitter],
                      features_by_id: Dict[int, Dict[str, float]]) -> List[InterferenceFlag]:
    """Run all interference detectors and collect their flags."""
    flags: List[InterferenceFlag] = []
    fs = capture.sample_rate
    sweep = detect_sweep_jamming(spec)
    if sweep:
        flags.append(sweep)
    barrage = detect_barrage_jamming(emitters, fs, features_by_id)
    if barrage:
        flags.append(barrage)
    flags.extend(detect_gnss_spoof_hint(capture, emitters, features_by_id))
    return flags
