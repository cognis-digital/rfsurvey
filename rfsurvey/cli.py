"""Command-line interface for RFSURVEY."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Optional

from . import TOOL_NAME, TOOL_VERSION
from .core import SurveyError, analyze, SurveyReport


def _fmt_hz(hz: float) -> str:
    if hz >= 1e9:
        return f"{hz / 1e9:.4g} GHz"
    if hz >= 1e6:
        return f"{hz / 1e6:.4g} MHz"
    if hz >= 1e3:
        return f"{hz / 1e3:.4g} kHz"
    return f"{hz:.0f} Hz"


def _render_table(report: SurveyReport) -> str:
    lines: list[str] = []
    lines.append(f"{TOOL_NAME} {TOOL_VERSION} - spectrum survey report")
    lines.append(
        "samples=%d  sweeps=%d  range=%s..%s  noise_floor=%.2f dBm  squelch=%.2f dBm"
        % (
            report.samples,
            report.sweeps,
            _fmt_hz(report.freq_min_hz),
            _fmt_hz(report.freq_max_hz),
            report.noise_floor_dbm,
            report.squelch_dbm,
        )
    )
    lines.append("")
    lines.append("BAND OCCUPANCY")
    lines.append(
        "%-20s %5s %5s %8s %8s %8s  %s"
        % ("band", "bins", "occ", "occ%", "peak", "mean", "peak_freq")
    )
    lines.append("-" * 78)
    for b in report.bands:
        lines.append(
            "%-20s %5d %5d %7.1f%% %8.2f %8.2f  %s"
            % (
                b.name[:20],
                b.bins,
                b.occupied_bins,
                b.occupancy * 100.0,
                b.peak_dbm,
                b.mean_dbm,
                _fmt_hz(b.peak_freq_hz),
            )
        )
    lines.append("")
    lines.append(f"ANOMALIES ({len(report.anomalies)})")
    if not report.anomalies:
        lines.append("  none")
    else:
        lines.append("%-10s %-22s %10s %8s  %s" % ("kind", "band", "freq", "power", "z/score"))
        lines.append("-" * 78)
        for a in report.anomalies:
            lines.append(
                "%-10s %-22s %10s %8.2f  %.2f"
                % (a.kind, a.band[:22], _fmt_hz(a.freq_hz), a.power_dbm, a.z_score)
            )
    return "\n".join(lines)


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Analyze RF spectrum-occupancy CSV for band usage, interference, and anomalies.",
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    parser.add_argument(
        "--format", choices=("table", "json"), default="table", help="output format"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_an = sub.add_parser(
        "analyze", help="analyze a spectrum sweep CSV (use '-' for stdin)"
    )
    p_an.add_argument("input", help="path to sweep CSV, or '-' for stdin")
    p_an.add_argument(
        "--squelch-offset",
        type=float,
        default=10.0,
        help="dB above estimated noise floor counted as occupied (default 10)",
    )
    p_an.add_argument(
        "--z-thresh",
        type=float,
        default=6.0,
        help="robust z-score threshold for power-spike anomalies (default 6.0)",
    )
    p_an.add_argument(
        "--persist-sweeps",
        type=int,
        default=3,
        help="min distinct sweeps a bin must occupy to flag as persistent (default 3)",
    )
    p_an.add_argument(
        "--fail-on-anomaly",
        action="store_true",
        help="exit non-zero if any anomaly is detected (for monitoring pipelines)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        try:
            text = _read_input(args.input)
        except OSError as exc:
            print(f"{TOOL_NAME}: cannot read input: {exc}", file=sys.stderr)
            return 2
        try:
            report = analyze(
                text,
                squelch_offset_db=args.squelch_offset,
                z_thresh=args.z_thresh,
                persist_min_sweeps=args.persist_sweeps,
            )
        except SurveyError as exc:
            print(f"{TOOL_NAME}: {exc}", file=sys.stderr)
            return 2

        if args.format == "json":
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(_render_table(report))

        if args.fail_on_anomaly and report.anomalies:
            return 1
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
