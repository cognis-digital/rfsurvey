"""High-level analysis pipeline: capture -> emitters -> classifications -> report.

This is the single entry point used by the CLI and the MCP server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import __version__
from .classify.classifier import Classification, classify_features
from .classify.features import extract_features
from .classify.interference import InterferenceFlag, scan_interference
from .detect.pipeline import DetectionResult, detect_emitters
from .io.capture import Capture


@dataclass
class EmitterReport:
    emitter: dict
    classification: dict

    def to_dict(self) -> dict:
        return {"emitter": self.emitter, "classification": self.classification}


@dataclass
class AnalysisReport:
    capture: dict
    emitters: List[EmitterReport] = field(default_factory=list)
    interference: List[dict] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    tool: str = "wavewatch"
    version: str = __version__

    # kept for downstream renderers (not serialized directly)
    detection: Optional[DetectionResult] = None
    _capture_obj: Optional[Capture] = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "version": self.version,
            "capture": self.capture,
            "params": self.params,
            "emitters": [e.to_dict() for e in self.emitters],
            "interference": self.interference,
            "summary": self.summary(),
        }

    def summary(self) -> dict:
        labels: Dict[str, int] = {}
        for e in self.emitters:
            lab = e.classification.get("label", "unknown")
            labels[lab] = labels.get(lab, 0) + 1
        return {
            "n_emitters": len(self.emitters),
            "labels": labels,
            "n_interference_flags": len(self.interference),
            "interference_kinds": sorted({f["kind"] for f in self.interference}),
        }

    def label_map(self) -> Dict[int, str]:
        out: Dict[int, str] = {}
        for e in self.emitters:
            out[e.emitter["id"]] = e.classification["label"]
        return out


def analyze_capture(capture: Capture, nperseg: int = 256, noverlap: int | None = None,
                    window: str = "hann", threshold_db: float = 6.0) -> AnalysisReport:
    """Run the full detect -> fingerprint -> classify -> flag pipeline."""
    detection = detect_emitters(
        capture, nperseg=nperseg, noverlap=noverlap, window=window,
        threshold_db=threshold_db,
    )

    emitter_reports: List[EmitterReport] = []
    features_by_id: Dict[int, Dict[str, float]] = {}
    for e in detection.emitters:
        features = extract_features(capture, e)
        features_by_id[e.id] = features
        cls: Classification = classify_features(features)
        emitter_reports.append(EmitterReport(
            emitter=e.to_dict(capture.center_freq),
            classification=cls.to_dict(),
        ))

    flags: List[InterferenceFlag] = scan_interference(
        capture,
        detection.spectrogram,
        detection.psd,
        detection.emitters,
        features_by_id,
    )

    report = AnalysisReport(
        capture=capture.summary(),
        emitters=emitter_reports,
        interference=[f.to_dict() for f in flags],
        params={
            "nperseg": nperseg,
            "noverlap": noverlap if noverlap is not None else nperseg // 2,
            "window": window,
            "threshold_db": threshold_db,
        },
        detection=detection,
        _capture_obj=capture,
    )
    return report
