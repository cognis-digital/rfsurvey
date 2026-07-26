"""Pure-Python DSP core for wavewatch (no NumPy at runtime)."""

from __future__ import annotations

from .fft import (
    dft,
    fft,
    fftfreq,
    fftshift,
    idft,
    ifft,
    ifftshift,
    is_power_of_two,
    next_power_of_two,
    rfft,
)
from .psd import average_psd_db, periodogram, welch
from .spectrogram import Spectrogram, spectrogram, stft
from .window import get_window, window_names

__all__ = [
    "dft", "idft", "fft", "ifft", "rfft",
    "fftfreq", "fftshift", "ifftshift",
    "is_power_of_two", "next_power_of_two",
    "periodogram", "welch", "average_psd_db",
    "spectrogram", "stft", "Spectrogram",
    "get_window", "window_names",
]
