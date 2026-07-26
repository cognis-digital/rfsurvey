"""Optional live-capture adapter stub.

wavewatch is a *file-based, offline* analysis tool by design. This module defines
the interface a live SDR adapter would implement, but ships no hardware driver
and performs no capture. It exists so an out-of-tree adapter can feed samples
into the same :class:`~wavewatch.io.capture.Capture` pipeline.

There is deliberately no transmit path here -- receive/analysis only.
"""

from __future__ import annotations

from typing import List, Optional

from .capture import Capture

Complex = complex


class LiveCaptureAdapter:
    """Abstract receive-only live-capture adapter.

    Concrete adapters (out of tree) implement :meth:`read` to return baseband IQ
    samples. The base class raises :class:`NotImplementedError`, keeping the core
    package hardware-free and offline.
    """

    def __init__(self, sample_rate: float, center_freq: float = 0.0) -> None:
        self.sample_rate = sample_rate
        self.center_freq = center_freq

    def available(self) -> bool:
        """Whether a backing device is present. Always False in the core."""
        return False

    def read(self, n_samples: int) -> List[Complex]:
        raise NotImplementedError(
            "No live-capture backend is bundled. wavewatch analyzes capture "
            "files offline. Provide an out-of-tree receive-only adapter."
        )

    def snapshot(self, n_samples: int) -> Capture:
        samples = self.read(n_samples)
        return Capture(
            samples=samples,
            sample_rate=self.sample_rate,
            center_freq=self.center_freq,
            source="live-adapter",
            metadata={"live": True},
        )
