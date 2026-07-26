"""Command-line interface for wavewatch."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .analyze import analyze_capture
from .io import generate, load_capture
from .io.sigmf import write_sigmf
from .io.waviq import write_waviq
from .output.geojson import write_geojson
from .output.json_out import to_json, write_json
from .output.sarif import to_sarif, write_sarif
from .output.spectro_png import render_spectrogram_png


def _load(args) -> "object":
    if getattr(args, "scenario", None):
        capture, _ = generate(args.scenario)
        return capture
    if not args.path:
        raise SystemExit("error: provide a capture path or --scenario")
    return load_capture(args.path)


def cmd_analyze(args) -> int:
    capture = _load(args)
    report = analyze_capture(
        capture, nperseg=args.nperseg, noverlap=args.noverlap,
        window=args.window, threshold_db=args.threshold_db,
    )

    wrote_any = False
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)
    base = args.out_dir or "."

    if args.json:
        p = args.json if args.json != "-" else None
        if p:
            write_json(report, p)
            print(f"wrote JSON: {p}")
            wrote_any = True
    if args.sarif:
        write_sarif(report, args.sarif)
        print(f"wrote SARIF: {args.sarif}")
        wrote_any = True
    if args.geojson:
        res = write_geojson(report, args.geojson, position=capture.position)
        if res:
            print(f"wrote GeoJSON: {res}")
        else:
            print("no position metadata; GeoJSON skipped")
        wrote_any = True
    if args.png:
        det = report.detection
        render_spectrogram_png(
            det.spectrogram if det else None,
            det.emitters if det else [],
            args.png,
            labels=report.label_map(),
            center_freq=capture.center_freq,
            title=f"wavewatch: {os.path.basename(capture.source or 'capture')}",
        )
        print(f"wrote PNG: {args.png}")
        wrote_any = True

    if not wrote_any or args.json == "-":
        print(to_json(report))
    else:
        s = report.summary()
        print(f"emitters={s['n_emitters']} labels={s['labels']} "
              f"interference={s['interference_kinds']}")
    return 0


def cmd_generate(args) -> int:
    capture, label = generate(args.scenario)
    out = args.out
    if out.lower().endswith(".wav"):
        write_waviq(out, capture)
        print(f"wrote WAV-IQ: {out} (scenario={args.scenario}, expected={label})")
    else:
        meta, data = write_sigmf(out, capture, description=f"synthetic:{args.scenario}")
        print(f"wrote SigMF: {meta} / {data} (scenario={args.scenario}, expected={label})")
    return 0


def cmd_serve_mcp(args) -> int:
    from .mcp.server import serve_stdio

    serve_stdio()
    return 0


def cmd_info(args) -> int:
    from .io.generator import SCENARIOS

    info = {
        "tool": "wavewatch",
        "version": __version__,
        "scope": "defensive/offline RF triage; no transmit, no jamming, no payload demod",
        "scenarios": sorted(SCENARIOS.keys()),
        "formats_in": ["sigmf", "wav-iq", "csv-spectrum"],
        "formats_out": ["json", "sarif", "geojson", "png"],
    }
    print(json.dumps(info, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wavewatch",
        description="Offline RF signal reconnaissance and triage (defensive, lawful-by-design).",
    )
    p.add_argument("--version", action="version", version=f"wavewatch {__version__}")
    sub = p.add_subparsers(dest="command")

    a = sub.add_parser("analyze", help="analyze a capture file or synthetic scenario")
    a.add_argument("path", nargs="?", help="capture file path (.sigmf-meta/.wav/.csv)")
    a.add_argument("--scenario", help="use a synthetic scenario instead of a file")
    a.add_argument("--nperseg", type=int, default=256, help="FFT segment length")
    a.add_argument("--noverlap", type=int, default=None, help="segment overlap")
    a.add_argument("--window", default="hann", help="window function")
    a.add_argument("--threshold-db", dest="threshold_db", type=float, default=6.0,
                   help="detection threshold in dB above noise floor")
    a.add_argument("--json", nargs="?", const="-", help="write JSON (path, or '-' for stdout)")
    a.add_argument("--sarif", help="write SARIF findings to path")
    a.add_argument("--geojson", help="write GeoJSON to path (if position present)")
    a.add_argument("--png", help="write annotated spectrogram PNG to path")
    a.add_argument("--out-dir", dest="out_dir", help="output directory")
    a.set_defaults(func=cmd_analyze)

    g = sub.add_parser("generate", help="write a synthetic capture to disk")
    g.add_argument("scenario", help="scenario name (noise/tone/wifi/drone-link/ble/gnss/sweep/barrage)")
    g.add_argument("--out", required=True, help="output path (.wav or SigMF base)")
    g.set_defaults(func=cmd_generate)

    m = sub.add_parser("serve-mcp", help="run the stdio MCP server")
    m.set_defaults(func=cmd_serve_mcp)

    i = sub.add_parser("info", help="print tool info")
    i.set_defaults(func=cmd_info)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
