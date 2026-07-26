"""Fingerprinting, classification, and interference flagging."""

from __future__ import annotations

from .classifier import (
    CLASSES,
    Classification,
    THRESHOLDS,
    classify_emitter,
    classify_features,
)
from .features import extract_features
from .interference import (
    GNSS_BANDS,
    InterferenceFlag,
    detect_barrage_jamming,
    detect_gnss_spoof_hint,
    detect_sweep_jamming,
    scan_interference,
)

__all__ = [
    "extract_features",
    "classify_emitter", "classify_features", "Classification", "CLASSES", "THRESHOLDS",
    "scan_interference", "InterferenceFlag",
    "detect_sweep_jamming", "detect_barrage_jamming", "detect_gnss_spoof_hint",
    "GNSS_BANDS",
]
