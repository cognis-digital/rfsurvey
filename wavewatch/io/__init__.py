"""Capture ingest, synthetic generation, and format readers/writers."""

from __future__ import annotations

import os

from .capture import Capture
from .csvspec import parse_csv_spectrum_text, read_csv_spectrum, write_csv_spectrum
from .generator import SCENARIOS, generate
from .sigmf import read_sigmf, write_sigmf
from .waviq import read_waviq, write_waviq

__all__ = [
    "Capture", "generate", "SCENARIOS",
    "read_sigmf", "write_sigmf",
    "read_waviq", "write_waviq",
    "read_csv_spectrum", "write_csv_spectrum", "parse_csv_spectrum_text",
    "load_capture",
]


def load_capture(path: str, **kwargs) -> Capture:
    """Load a capture, dispatching on file extension.

    ``.sigmf-meta`` / ``.sigmf-data`` -> SigMF; ``.wav`` -> WAV-IQ;
    ``.csv`` -> CSV spectrum.
    """
    low = path.lower()
    if low.endswith((".sigmf-meta", ".sigmf-data")):
        return read_sigmf(path)
    if low.endswith(".wav"):
        return read_waviq(path, **kwargs)
    if low.endswith(".csv"):
        return read_csv_spectrum(path, **kwargs)
    # try sigmf base path
    if os.path.exists(path + ".sigmf-meta"):
        return read_sigmf(path)
    raise ValueError(f"unrecognized capture format: {path!r}")
