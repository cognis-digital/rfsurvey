"""wavewatch -- offline RF signal reconnaissance and triage.

A Cognis Digital tool. Detects, fingerprints, and classifies RF emitters from
standard capture files (SigMF / WAV-IQ / CSV spectra) using a pure-Python DSP
core. Defensive and lawful-by-design: analysis only. No transmit path, no
jamming, no payload demodulation, no weaponization.
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Cognis Digital LLC"
__license__ = "MIT"

from .analyze import AnalysisReport, EmitterReport, analyze_capture
from .io import Capture, generate, load_capture

__all__ = [
    "__version__",
    "analyze_capture",
    "AnalysisReport",
    "EmitterReport",
    "Capture",
    "load_capture",
    "generate",
]
