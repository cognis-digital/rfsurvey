"""Tests for the top-level pipeline, MCP server, and CLI."""

from __future__ import annotations

import io
import json

import pytest

from wavewatch import __version__
from wavewatch.analyze import AnalysisReport, analyze_capture
from wavewatch.io.generator import generate
from wavewatch.mcp.server import (
    TOOLS,
    build_response,
    handle_request,
    serve_stdio,
    tool_analyze_capture,
)
from wavewatch import cli


# --------------------------------------------------------------------------- #
# analyze_capture
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("scenario", ["noise", "tone", "wifi", "drone-link", "ble", "gnss"])
def test_analyze_returns_report(scenario):
    cap, _ = generate(scenario)
    rep = analyze_capture(cap)
    assert isinstance(rep, AnalysisReport)
    assert rep.version == __version__


@pytest.mark.parametrize("scenario", ["tone", "wifi", "drone-link", "ble", "gnss"])
def test_analyze_report_dict(scenario):
    cap, _ = generate(scenario)
    d = analyze_capture(cap).to_dict()
    assert d["tool"] == "wavewatch"
    assert "summary" in d
    assert d["summary"]["n_emitters"] == len(d["emitters"])


def test_analyze_summary_labels():
    cap, _ = generate("drone-link")
    rep = analyze_capture(cap)
    s = rep.summary()
    assert "drone-link" in s["labels"]


def test_analyze_label_map():
    cap, _ = generate("wifi")
    rep = analyze_capture(cap)
    lm = rep.label_map()
    assert all(isinstance(k, int) for k in lm)


@pytest.mark.parametrize("nperseg", [128, 256, 512])
def test_analyze_nperseg_variants(nperseg):
    cap, _ = generate("wifi")
    rep = analyze_capture(cap, nperseg=nperseg)
    assert rep.params["nperseg"] == nperseg


# --------------------------------------------------------------------------- #
# MCP server
# --------------------------------------------------------------------------- #
def test_mcp_initialize():
    resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["serverInfo"]["name"] == "wavewatch"
    assert "protocolVersion" in resp["result"]


def test_mcp_tools_list():
    resp = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "analyze_capture" in names


def test_mcp_tool_has_schema():
    assert TOOLS[0]["inputSchema"]["type"] == "object"
    assert "path" in TOOLS[0]["inputSchema"]["properties"]


def test_mcp_call_scenario():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "analyze_capture", "arguments": {"scenario": "drone-link"}},
    })
    assert resp["result"]["isError"] is False
    text = resp["result"]["content"][0]["text"]
    obj = json.loads(text)
    assert obj["tool"] == "wavewatch"


def test_mcp_call_sarif_format():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "analyze_capture", "arguments": {"scenario": "ble", "format": "sarif"}},
    })
    obj = json.loads(resp["result"]["content"][0]["text"])
    assert obj["version"] == "2.1.0"


def test_mcp_call_unknown_tool():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 5, "method": "tools/call",
        "params": {"name": "nope", "arguments": {}},
    })
    assert "error" in resp


def test_mcp_call_missing_args_is_error():
    resp = handle_request({
        "jsonrpc": "2.0", "id": 6, "method": "tools/call",
        "params": {"name": "analyze_capture", "arguments": {}},
    })
    assert resp["result"]["isError"] is True


def test_mcp_unknown_method():
    resp = handle_request({"jsonrpc": "2.0", "id": 7, "method": "bogus/method"})
    assert "error" in resp


def test_mcp_notification_no_response():
    assert handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_mcp_build_response_result():
    r = build_response(1, result={"ok": True})
    assert r["jsonrpc"] == "2.0" and r["result"]["ok"]


def test_mcp_build_response_error():
    r = build_response(1, error={"code": -1, "message": "x"})
    assert "error" in r


def test_tool_analyze_capture_direct():
    result = tool_analyze_capture({"scenario": "wifi"})
    assert result["isError"] is False
    assert "structuredContent" in result


def test_serve_stdio_roundtrip():
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
    out = io.StringIO()
    serve_stdio(stdin=io.StringIO(req), stdout=out)
    lines = [l for l in out.getvalue().splitlines() if l.strip()]
    resp = json.loads(lines[0])
    assert "result" in resp


def test_serve_stdio_parse_error():
    out = io.StringIO()
    serve_stdio(stdin=io.StringIO("{not json}\n"), stdout=out)
    resp = json.loads(out.getvalue().splitlines()[0])
    assert resp["error"]["code"] == -32700


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_info(capsys):
    rc = cli.main(["info"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "wavewatch" in out


def test_cli_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])


def test_cli_analyze_scenario_stdout(capsys):
    rc = cli.main(["analyze", "--scenario", "wifi", "--json", "-"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "wavewatch" in out


def test_cli_analyze_writes_json(tmp_path, capsys):
    p = str(tmp_path / "r.json")
    rc = cli.main(["analyze", "--scenario", "ble", "--json", p])
    assert rc == 0
    with open(p) as fh:
        obj = json.load(fh)
    assert obj["tool"] == "wavewatch"


def test_cli_analyze_all_outputs(tmp_path):
    d = str(tmp_path)
    rc = cli.main([
        "analyze", "--scenario", "drone-link",
        "--json", f"{d}/r.json", "--sarif", f"{d}/r.sarif", "--png", f"{d}/r.png",
    ])
    assert rc == 0
    import os
    assert os.path.exists(f"{d}/r.json")
    assert os.path.exists(f"{d}/r.sarif")
    assert os.path.exists(f"{d}/r.png")


def test_cli_generate_sigmf(tmp_path, capsys):
    base = str(tmp_path / "cap")
    rc = cli.main(["generate", "wifi", "--out", base])
    assert rc == 0
    import os
    assert os.path.exists(base + ".sigmf-meta")


def test_cli_generate_wav(tmp_path):
    path = str(tmp_path / "cap.wav")
    rc = cli.main(["generate", "tone", "--out", path])
    assert rc == 0
    import os
    assert os.path.exists(path)


def test_cli_analyze_from_file(tmp_path, capsys):
    base = str(tmp_path / "cap")
    cli.main(["generate", "drone-link", "--out", base])
    rc = cli.main(["analyze", base + ".sigmf-meta", "--json", "-"])
    assert rc == 0


def test_cli_no_command_prints_help(capsys):
    rc = cli.main([])
    assert rc == 0
    assert "usage" in capsys.readouterr().out.lower()


def test_cli_build_parser():
    parser = cli.build_parser()
    assert parser.prog == "wavewatch"
