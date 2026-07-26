"""CSV power-spectrum reader/writer.

Reads a pre-computed power spectrum (e.g. exported by a spectrum analyzer) into
a spectrum :class:`Capture`. Two accepted layouts:

  * two columns ``frequency_hz, power`` (one row per bin), or
  * a single column of power values (a synthetic frequency axis is generated).

An optional header row is auto-detected and skipped.
"""

from __future__ import annotations

import csv
import io
from typing import List, Tuple

from .capture import Capture


def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def read_csv_spectrum(path: str, sample_rate: float = 0.0,
                      center_freq: float = 0.0) -> Capture:
    """Read a CSV power spectrum into a spectrum capture."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    return _parse_rows(rows, source=path, sample_rate=sample_rate, center_freq=center_freq)


def parse_csv_spectrum_text(text: str, source: str = "<text>") -> Capture:
    """Parse CSV spectrum content from a string (used by tests)."""
    rows = list(csv.reader(io.StringIO(text)))
    return _parse_rows(rows, source=source)


def _parse_rows(rows, source: str, sample_rate: float = 0.0,
                center_freq: float = 0.0) -> Capture:
    freqs: List[float] = []
    powers: List[float] = []
    for row in rows:
        cells = [c.strip() for c in row if c.strip() != ""]
        if not cells:
            continue
        if not _is_float(cells[0]):
            # header line
            continue
        if len(cells) >= 2 and _is_float(cells[1]):
            freqs.append(float(cells[0]))
            powers.append(float(cells[1]))
        else:
            powers.append(float(cells[0]))
    if not freqs:
        freqs = [float(i) for i in range(len(powers))]
    cap = Capture(
        samples=[],
        sample_rate=sample_rate,
        center_freq=center_freq,
        source=source,
        kind="spectrum",
        spectrum_freqs=freqs,
        spectrum_power=powers,
        metadata={"format": "csv-spectrum", "n_bins": len(powers)},
    )
    return cap


def write_csv_spectrum(path: str, freqs: List[float], powers: List[float],
                       header: bool = True) -> str:
    """Write a power spectrum to CSV."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        if header:
            w.writerow(["frequency_hz", "power_db"])
        for f, p in zip(freqs, powers):
            w.writerow([f, p])
    return path
