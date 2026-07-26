"""The :class:`Capture` container -- wavewatch's in-memory representation of a
recording, independent of source file format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

Complex = complex


@dataclass
class Capture:
    """An IQ (or spectrum) capture loaded into memory.

    Attributes
    ----------
    samples : list of complex
        Baseband IQ samples. Empty for pure spectrum captures.
    sample_rate : float
        Sample rate in Hz.
    center_freq : float
        RF center frequency in Hz (0.0 if unknown / baseband).
    metadata : dict
        Free-form metadata (datatype, hardware, description, ...).
    position : tuple(lat, lon) or None
        Optional geo position where the capture was taken.
    source : str
        Path or label the capture was loaded from.
    kind : str
        ``"iq"`` or ``"spectrum"``.
    spectrum_freqs / spectrum_power : list of float
        For spectrum captures, the frequency axis (Hz) and power values.
    """

    samples: List[Complex] = field(default_factory=list)
    sample_rate: float = 1.0
    center_freq: float = 0.0
    metadata: Dict = field(default_factory=dict)
    position: Optional[tuple] = None
    source: str = ""
    kind: str = "iq"
    spectrum_freqs: List[float] = field(default_factory=list)
    spectrum_power: List[float] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.samples) if self.kind == "iq" else len(self.spectrum_power)

    @property
    def duration(self) -> float:
        """Capture duration in seconds (0 for spectrum captures)."""
        if self.kind != "iq" or self.sample_rate <= 0:
            return 0.0
        return len(self.samples) / self.sample_rate

    @property
    def n_samples(self) -> int:
        return len(self.samples)

    def has_position(self) -> bool:
        return self.position is not None

    def summary(self) -> Dict:
        """A small JSON-friendly summary dict."""
        return {
            "kind": self.kind,
            "n_samples": self.n_samples,
            "sample_rate": self.sample_rate,
            "center_freq": self.center_freq,
            "duration_s": self.duration,
            "has_position": self.has_position(),
            "position": list(self.position) if self.position is not None else None,
            "source": self.source,
        }
