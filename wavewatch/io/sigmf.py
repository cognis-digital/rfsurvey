"""Minimal SigMF reader/writer (pure stdlib).

SigMF stores a JSON ``*.sigmf-meta`` sidecar plus a raw ``*.sigmf-data`` binary.
This implements the common subset needed for offline triage: the ``global``
object (datatype, sample_rate) and ``captures`` (frequency, geolocation).

Supported datatypes: ``cf32_le``, ``cf64_le``, ``ci16_le``, ``ci8``, ``cu8``,
``rf32_le`` and their real ``r*`` counterparts.
"""

from __future__ import annotations

import json
import os
import struct
from typing import List, Tuple

from .capture import Capture

Complex = complex

_FMT = {
    "cf32_le": ("<f", 4, True), "cf32": ("<f", 4, True),
    "cf64_le": ("<d", 8, True), "cf64": ("<d", 8, True),
    "ci16_le": ("<h", 2, True), "ci16": ("<h", 2, True),
    "ci8": ("<b", 1, True), "cu8": ("<B", 1, True),
    "rf32_le": ("<f", 4, False), "rf32": ("<f", 4, False),
    "ri16_le": ("<h", 2, False), "ri16": ("<h", 2, False),
}


def _meta_path(path: str) -> str:
    if path.endswith(".sigmf-meta"):
        return path
    if path.endswith(".sigmf-data"):
        return path[: -len(".sigmf-data")] + ".sigmf-meta"
    return path + ".sigmf-meta"


def _data_path(path: str) -> str:
    if path.endswith(".sigmf-data"):
        return path
    if path.endswith(".sigmf-meta"):
        return path[: -len(".sigmf-meta")] + ".sigmf-data"
    return path + ".sigmf-data"


def read_sigmf(path: str) -> Capture:
    """Read a SigMF recording. ``path`` may be the meta, data, or base path."""
    meta_path = _meta_path(path)
    data_path = _data_path(path)
    with open(meta_path, "r", encoding="utf-8") as fh:
        meta = json.load(fh)

    g = meta.get("global", {})
    datatype = g.get("core:datatype", "cf32_le")
    fs = float(g.get("core:sample_rate", 1.0))

    center_freq = 0.0
    position = None
    caps = meta.get("captures", [])
    if caps:
        first = caps[0]
        center_freq = float(first.get("core:frequency", 0.0))
        geo = first.get("core:geolocation")
        if isinstance(geo, dict):
            coords = geo.get("coordinates")
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                # GeoJSON Point: [lon, lat]
                position = (float(coords[1]), float(coords[0]))

    samples = _read_raw(data_path, datatype)
    return Capture(
        samples=samples,
        sample_rate=fs,
        center_freq=center_freq,
        position=position,
        source=data_path,
        metadata={"datatype": datatype, "sigmf_global": g},
        kind="iq",
    )


def _read_raw(data_path: str, datatype: str) -> List[Complex]:
    if datatype not in _FMT:
        raise ValueError(f"unsupported SigMF datatype: {datatype!r}")
    fmt, size, is_complex = _FMT[datatype]
    is_unsigned = datatype.startswith("cu")
    with open(data_path, "rb") as fh:
        raw = fh.read()
    count = len(raw) // size
    vals = [v[0] for v in struct.iter_unpack(fmt, raw[: count * size])]

    if datatype in ("ci16_le", "ci16", "ri16_le", "ri16"):
        vals = [v / 32768.0 for v in vals]
    elif datatype == "ci8":
        vals = [v / 128.0 for v in vals]
    elif datatype == "cu8":
        vals = [(v - 127.5) / 127.5 for v in vals]

    if is_complex:
        out: List[Complex] = []
        for i in range(0, len(vals) - 1, 2):
            out.append(complex(vals[i], vals[i + 1]))
        return out
    return [complex(v, 0.0) for v in vals]


def write_sigmf(path: str, capture: Capture, datatype: str = "cf32_le",
                description: str = "") -> Tuple[str, str]:
    """Write a capture to SigMF meta+data. Returns ``(meta_path, data_path)``."""
    if datatype not in _FMT:
        raise ValueError(f"unsupported SigMF datatype: {datatype!r}")
    meta_path = _meta_path(path)
    data_path = _data_path(path)
    fmt, size, is_complex = _FMT[datatype]

    with open(data_path, "wb") as fh:
        for s in capture.samples:
            re, im = _encode_pair(s.real, s.imag, datatype)
            if is_complex:
                fh.write(struct.pack(fmt, re))
                fh.write(struct.pack(fmt, im))
            else:
                fh.write(struct.pack(fmt, re))

    cap_obj = {"core:sample_start": 0, "core:frequency": capture.center_freq}
    if capture.position is not None:
        lat, lon = capture.position
        cap_obj["core:geolocation"] = {"type": "Point", "coordinates": [lon, lat]}
    meta = {
        "global": {
            "core:datatype": datatype,
            "core:sample_rate": capture.sample_rate,
            "core:version": "1.0.0",
            "core:description": description,
        },
        "captures": [cap_obj],
        "annotations": [],
    }
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta_path, data_path


def _encode_pair(re: float, im: float, datatype: str):
    if datatype in ("ci16_le", "ci16", "ri16_le", "ri16"):
        return _q(re, 32767), _q(im, 32767)
    if datatype == "ci8":
        return _q(re, 127), _q(im, 127)
    if datatype == "cu8":
        return _clamp_int(round(re * 127.5 + 127.5), 0, 255), _clamp_int(round(im * 127.5 + 127.5), 0, 255)
    return re, im


def _q(v: float, full: int) -> int:
    return _clamp_int(round(v * full), -full - 1, full)


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(v)))
