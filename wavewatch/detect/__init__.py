"""Emitter detection: CFAR band detection, burst segmentation, hop grouping."""

from __future__ import annotations

from .burst import band_frame_power, duty_cycle, segment_bursts
from .cfar import cfar_1d, detect_bands, estimate_noise_floor
from .hopping import HOP_MIN_CHANNELS, group_emitters
from .model import Band, Burst, Emitter
from .pipeline import DetectionResult, detect_emitters

__all__ = [
    "cfar_1d", "detect_bands", "estimate_noise_floor",
    "segment_bursts", "band_frame_power", "duty_cycle",
    "group_emitters", "HOP_MIN_CHANNELS",
    "Band", "Burst", "Emitter",
    "detect_emitters", "DetectionResult",
]
