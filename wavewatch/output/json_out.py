"""JSON report writer."""

from __future__ import annotations

import json
from typing import Any


def to_json(report: Any, indent: int = 2) -> str:
    """Serialize an analysis report (or dict) to a JSON string."""
    obj = report.to_dict() if hasattr(report, "to_dict") else report
    return json.dumps(obj, indent=indent, sort_keys=False)


def write_json(report: Any, path: str, indent: int = 2) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(to_json(report, indent=indent))
    return path
