"""SARIF-style findings writer.

Emits a SARIF 2.1.0 log where each classified emitter and each interference flag
is a ``result``. This lets RF triage output drop into the same tooling that
consumes static-analysis findings.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .. import __version__

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

_SEVERITY_TO_LEVEL = {"info": "note", "low": "note", "medium": "warning", "high": "error"}


def _rules() -> List[Dict]:
    return [
        {"id": "emitter.classified",
         "name": "EmitterClassified",
         "shortDescription": {"text": "An RF emitter was detected and classified."}},
        {"id": "interference.detected",
         "name": "InterferenceDetected",
         "shortDescription": {"text": "An interference signature was detected."}},
    ]


def to_sarif(report: Any) -> Dict:
    """Build a SARIF log dict from an analysis report."""
    obj = report.to_dict() if hasattr(report, "to_dict") else report
    results: List[Dict] = []

    src = obj.get("capture", {}).get("source", "capture")
    for er in obj.get("emitters", []):
        e = er["emitter"]
        c = er["classification"]
        level = "warning" if c["label"] in ("drone-link", "gnss") else "note"
        msg = (f"Emitter #{e['id']} classified as '{c['label']}' "
               f"(confidence {c['confidence']:.2f}) at "
               f"{e['rf_center_hz']/1e6:.3f} MHz, BW {e['bandwidth_hz']/1e3:.1f} kHz.")
        results.append({
            "ruleId": "emitter.classified",
            "level": level,
            "message": {"text": msg},
            "properties": {
                "label": c["label"],
                "confidence": c["confidence"],
                "rf_center_hz": e["rf_center_hz"],
                "bandwidth_hz": e["bandwidth_hz"],
                "hopping": e["hopping"],
                "decision_trace": c.get("decision_trace", []),
                "features": c.get("features", {}),
            },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": src},
                    "region": {"startLine": e["id"] + 1},
                }
            }],
        })

    for f in obj.get("interference", []):
        level = _SEVERITY_TO_LEVEL.get(f.get("severity", "medium"), "warning")
        results.append({
            "ruleId": "interference.detected",
            "level": level,
            "message": {"text": f["message"]},
            "properties": {
                "kind": f["kind"],
                "severity": f["severity"],
                "confidence": f["confidence"],
                "evidence": f.get("evidence", {}),
            },
            "locations": [{
                "physicalLocation": {"artifactLocation": {"uri": src}}
            }],
        })

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {
                "driver": {
                    "name": "wavewatch",
                    "informationUri": "https://github.com/cognis-digital/wavewatch",
                    "version": __version__,
                    "rules": _rules(),
                }
            },
            "results": results,
        }],
    }


def write_sarif(report: Any, path: str, indent: int = 2) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(to_sarif(report), fh, indent=indent)
    return path
