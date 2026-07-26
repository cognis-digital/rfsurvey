"""Window functions for spectral estimation (pure Python)."""

from __future__ import annotations

import math
from typing import Callable, Dict, List

__all__ = [
    "rectangular", "hann", "hamming", "blackman", "blackman_harris",
    "bartlett", "get_window", "window_names",
]


def rectangular(n: int) -> List[float]:
    """Rectangular (boxcar) window."""
    return [1.0] * max(0, n)


def _cosine_sum(n: int, coeffs) -> List[float]:
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    out = []
    for i in range(n):
        val = 0.0
        for k, a in enumerate(coeffs):
            sign = 1.0 if k % 2 == 0 else -1.0
            val += sign * a * math.cos(2.0 * math.pi * k * i / (n - 1))
        out.append(val)
    return out


def hann(n: int) -> List[float]:
    """Hann window."""
    return _cosine_sum(n, (0.5, 0.5))


def hamming(n: int) -> List[float]:
    """Hamming window."""
    return _cosine_sum(n, (0.54, 0.46))


def blackman(n: int) -> List[float]:
    """Blackman window."""
    return _cosine_sum(n, (0.42, 0.5, 0.08))


def blackman_harris(n: int) -> List[float]:
    """4-term Blackman-Harris window."""
    return _cosine_sum(n, (0.35875, 0.48829, 0.14128, 0.01168))


def bartlett(n: int) -> List[float]:
    """Bartlett (triangular) window."""
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    out = []
    for i in range(n):
        out.append(1.0 - abs((i - (n - 1) / 2.0) / ((n - 1) / 2.0)))
    return out


_WINDOWS: Dict[str, Callable[[int], List[float]]] = {
    "rectangular": rectangular,
    "boxcar": rectangular,
    "rect": rectangular,
    "hann": hann,
    "hanning": hann,
    "hamming": hamming,
    "blackman": blackman,
    "blackman_harris": blackman_harris,
    "blackmanharris": blackman_harris,
    "bartlett": bartlett,
    "triangular": bartlett,
}


def window_names() -> List[str]:
    """Sorted list of recognised window names."""
    return sorted(_WINDOWS.keys())


def get_window(name: str, n: int) -> List[float]:
    """Return window ``name`` of length ``n``.

    Raises :class:`ValueError` for an unknown name.
    """
    key = (name or "").lower().strip()
    if key not in _WINDOWS:
        raise ValueError(f"unknown window: {name!r}")
    return _WINDOWS[key](n)
