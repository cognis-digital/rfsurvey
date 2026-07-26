"""Data structures shared by the detection pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Band:
    """A contiguous region of occupied spectrum found on the averaged PSD."""

    f_lo: float
    f_hi: float
    center: float
    peak_power: float
    peak_db: float
    noise_db: float

    @property
    def bandwidth(self) -> float:
        return max(0.0, self.f_hi - self.f_lo)

    @property
    def snr_db(self) -> float:
        return self.peak_db - self.noise_db


@dataclass
class Burst:
    """A time-contiguous active segment within a band."""

    t_start: float
    t_end: float
    frame_start: int
    frame_end: int
    center: float

    @property
    def duration(self) -> float:
        return max(0.0, self.t_end - self.t_start)


@dataclass
class Emitter:
    """A detected emitter: a band (or a group of hopping channels) plus its
    temporal activity and measured signal statistics."""

    id: int
    center_freq: float                 # baseband offset (Hz)
    bandwidth_hz: float
    f_lo: float
    f_hi: float
    snr_db: float
    duty: float
    bursts: List[Burst] = field(default_factory=list)
    hopping: bool = False
    channels: List[float] = field(default_factory=list)
    peak_db: float = 0.0
    noise_db: float = 0.0

    @property
    def n_bursts(self) -> int:
        return len(self.bursts)

    @property
    def n_channels(self) -> int:
        return len(self.channels) if self.channels else 1

    @property
    def mean_burst_dur(self) -> float:
        if not self.bursts:
            return 0.0
        return sum(b.duration for b in self.bursts) / len(self.bursts)

    @property
    def char_burst_dur(self) -> float:
        """Duration-weighted characteristic burst length.

        ``sum(d^2) / sum(d)`` -- robust to spurious single-frame fragments from
        spectral leakage, which drag a plain mean down but carry little energy.
        """
        if not self.bursts:
            return 0.0
        s1 = sum(b.duration for b in self.bursts)
        if s1 <= 0:
            return 0.0
        s2 = sum(b.duration * b.duration for b in self.bursts)
        return s2 / s1

    def rf_center(self, capture_center: float) -> float:
        return capture_center + self.center_freq

    def to_dict(self, capture_center: float = 0.0) -> dict:
        return {
            "id": self.id,
            "center_freq_hz": self.center_freq,
            "rf_center_hz": self.rf_center(capture_center),
            "bandwidth_hz": self.bandwidth_hz,
            "f_lo_hz": self.f_lo,
            "f_hi_hz": self.f_hi,
            "snr_db": self.snr_db,
            "duty_cycle": self.duty,
            "n_bursts": self.n_bursts,
            "mean_burst_dur_s": self.mean_burst_dur,
            "char_burst_dur_s": self.char_burst_dur,
            "hopping": self.hopping,
            "n_channels": self.n_channels,
            "channels_hz": list(self.channels),
        }
