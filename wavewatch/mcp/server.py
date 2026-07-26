"""A tiny, self-contained MCP server over JSON-RPC 2.0 / stdio.

No external MCP SDK. Implements just enough of the Model Context Protocol for an
agent to discover and call the ``analyze_capture`` tool:

  * ``initialize``
  * ``tools/list``
  * ``tools/call``  (tool name ``analyze_capture``)

Each JSON-RPC message is exchanged as one line of JSON on stdin/stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from .. import __version__
from ..analyze import analyze_capture
from ..io import generate, load_capture
from ..output.json_out import to_json
from ..output.sarif import to_sarif

PROTOCOL_VERSION = "2024-11-05"

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "analyze_capture",
        "description": (
            "Analyze an RF capture file offline and return structured emitter "
            "findings (detection, classification, decision trace, interference "
            "flags). Defensive analysis only; no payload demodulation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to a capture (.sigmf-meta/.sigmf-data, .wav, .csv).",
                },
                "scenario": {
                    "type": "string",
                    "description": "Instead of a path, generate a synthetic scenario "
                                   "(noise, tone, wifi, drone-link, ble, gnss, sweep, barrage).",
                },
                "nperseg": {"type": "integer", "description": "FFT segment length.", "default": 256},
                "threshold_db": {"type": "number", "description": "Detection threshold (dB).", "default": 6.0},
                "format": {
                    "type": "string",
                    "enum": ["json", "sarif"],
                    "description": "Output shape.",
                    "default": "json",
                },
            },
        },
    }
]


def tool_analyze_capture(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the ``analyze_capture`` tool and return a result payload."""
    path = arguments.get("path")
    scenario = arguments.get("scenario")
    nperseg = int(arguments.get("nperseg", 256))
    threshold_db = float(arguments.get("threshold_db", 6.0))
    out_format = arguments.get("format", "json")

    if scenario:
        capture, _ = generate(scenario)
    elif path:
        capture = load_capture(path)
    else:
        raise ValueError("either 'path' or 'scenario' is required")

    report = analyze_capture(capture, nperseg=nperseg, threshold_db=threshold_db)
    if out_format == "sarif":
        text = json.dumps(to_sarif(report), indent=2)
    else:
        text = to_json(report)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": False,
        "structuredContent": report.summary(),
    }


def build_response(req_id: Any, result: Any = None, error: Any = None) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 response object."""
    msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if error is not None:
        msg["error"] = error
    else:
        msg["result"] = result
    return msg


def handle_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC request; return a response (or None for notifications)."""
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params", {}) or {}

    # notifications (no id) get no response
    is_notification = "id" not in request

    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "wavewatch", "version": __version__},
        }
        return build_response(req_id, result=result)

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "tools/list":
        return build_response(req_id, result={"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments", {}) or {}
        if name != "analyze_capture":
            err = {"code": -32602, "message": f"unknown tool: {name!r}"}
            return build_response(req_id, error=err)
        try:
            result = tool_analyze_capture(arguments)
            return build_response(req_id, result=result)
        except Exception as exc:  # surface tool errors as JSON-RPC results
            result = {
                "content": [{"type": "text", "text": f"error: {exc}"}],
                "isError": True,
            }
            return build_response(req_id, result=result)

    if is_notification:
        return None
    return build_response(req_id, error={"code": -32601, "message": f"method not found: {method}"})


def serve_stdio(stdin=None, stdout=None) -> None:
    """Run the stdio server loop (one JSON message per line)."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            resp = build_response(None, error={"code": -32700, "message": "parse error"})
            stdout.write(json.dumps(resp) + "\n")
            stdout.flush()
            continue
        response = handle_request(request)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()


if __name__ == "__main__":
    serve_stdio()
