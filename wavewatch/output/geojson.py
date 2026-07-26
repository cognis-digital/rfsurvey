"""GeoJSON writer -- emitted only when the capture carries a position."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional


def to_geojson(report: Any, position: Optional[tuple] = None) -> Optional[Dict]:
    """Build a GeoJSON FeatureCollection of classified emitters.

    Returns ``None`` when no position is available (nothing to geolocate).
    ``position`` is ``(lat, lon)``.
    """
    obj = report.to_dict() if hasattr(report, "to_dict") else report
    if position is None:
        cap = obj.get("capture", {})
        pos = cap.get("position")
        if not cap.get("has_position") or not pos:
            return None
        position = (pos[0], pos[1])
    lat, lon = position

    features = []
    for er in obj.get("emitters", []):
        e = er["emitter"]
        c = er["classification"]
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "emitter_id": e["id"],
                "label": c["label"],
                "confidence": c["confidence"],
                "rf_center_hz": e["rf_center_hz"],
                "bandwidth_hz": e["bandwidth_hz"],
                "hopping": e["hopping"],
                "snr_db": e["snr_db"],
            },
        })
    for f in obj.get("interference", []):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "interference": f["kind"],
                "severity": f["severity"],
                "confidence": f["confidence"],
                "message": f["message"],
            },
        })

    return {"type": "FeatureCollection", "features": features}


def write_geojson(report: Any, path: str, position: Optional[tuple] = None,
                  indent: int = 2) -> Optional[str]:
    """Write GeoJSON. Returns the path, or ``None`` if no position was present."""
    gj = to_geojson(report, position=position)
    if gj is None:
        return None
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(gj, fh, indent=indent)
    return path
