"""End-to-end emitter detection over a capture."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ..dsp.psd import welch
from ..dsp.spectrogram import Spectrogram, spectrogram
from ..dsp.util import db10
from ..io.capture import Capture
from .burst import duty_cycle, segment_bursts
from .cfar import detect_bands
from .hopping import group_emitters
from .model import Band, Emitter


@dataclass
class DetectionResult:
    """Bundle of everything the detector produced (reused by the classifier and
    output writers)."""

    emitters: List[Emitter]
    spectrogram: Optional[Spectrogram]
    psd_freqs: List[float] = field(default_factory=list)
    psd: List[float] = field(default_factory=list)
    bands: List[Band] = field(default_factory=list)
    fs: float = 1.0
    duration: float = 0.0


def detect_emitters(capture: Capture, nperseg: int = 256, noverlap: int | None = None,
                    window: str = "hann", threshold_db: float = 6.0,
                    min_bins: int = 1) -> DetectionResult:
    """Detect emitters from an IQ or spectrum capture."""
    if capture.kind == "spectrum":
        return _detect_from_spectrum(capture, threshold_db=threshold_db, min_bins=min_bins)

    x = capture.samples
    fs = capture.sample_rate
    if not x:
        return DetectionResult(emitters=[], spectrogram=None, fs=fs, duration=0.0)

    if nperseg > len(x):
        nperseg = max(1, len(x))
    spec = spectrogram(x, fs=fs, nperseg=nperseg, noverlap=noverlap, window=window)
    freqs, psd = welch(x, fs=fs, nperseg=nperseg, window=window)

    merge_gap = 0.08 * fs
    bands = detect_bands(freqs, psd, threshold_db=threshold_db, min_bins=min_bins,
                         merge_gap=merge_gap)
    total_time = capture.duration

    band_bursts: List[List] = []
    band_duty: List[float] = []
    for b in bands:
        bursts = segment_bursts(spec, b, threshold_db=threshold_db)
        band_bursts.append(bursts)
        band_duty.append(duty_cycle(bursts, total_time))

    emitters = group_emitters(bands, band_bursts, band_duty, fs=fs, total_time=total_time)
    return DetectionResult(
        emitters=emitters,
        spectrogram=spec,
        psd_freqs=freqs,
        psd=psd,
        bands=bands,
        fs=fs,
        duration=total_time,
    )


def _detect_from_spectrum(capture: Capture, threshold_db: float = 6.0,
                          min_bins: int = 1) -> DetectionResult:
    freqs = capture.spectrum_freqs
    power_db = capture.spectrum_power
    # spectrum values are typically dB; convert to linear for band detection
    psd = [10 ** (v / 10.0) for v in power_db]
    span = abs(freqs[-1] - freqs[0]) if len(freqs) > 1 else 1.0
    bands = detect_bands(freqs, psd, threshold_db=threshold_db, min_bins=min_bins,
                         merge_gap=0.04 * span)
    emitters: List[Emitter] = []
    for i, b in enumerate(bands):
        emitters.append(Emitter(
            id=i,
            center_freq=b.center,
            bandwidth_hz=b.bandwidth,
            f_lo=b.f_lo,
            f_hi=b.f_hi,
            snr_db=b.snr_db,
            duty=1.0,  # no temporal information in a spectrum capture
            bursts=[],
            hopping=False,
            channels=[b.center],
            peak_db=b.peak_db,
            noise_db=b.noise_db,
        ))
    fs = capture.sample_rate or (abs(freqs[-1] - freqs[0]) if len(freqs) > 1 else 1.0)
    return DetectionResult(
        emitters=emitters,
        spectrogram=None,
        psd_freqs=list(freqs),
        psd=psd,
        bands=bands,
        fs=fs,
        duration=0.0,
    )
