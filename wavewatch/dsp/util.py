"""Small pure-Python numeric helpers used across the DSP core.

No third-party dependencies. Operates on plain Python ``list`` objects of
``float`` or ``complex`` values.
"""

from __future__ import annotations

import cmath
import math
from typing import Iterable, List, Sequence

Number = float
Complex = complex

_TINY = 1e-30


def mean(values: Sequence[float]) -> float:
    """Arithmetic mean; returns 0.0 for an empty sequence."""
    n = len(values)
    if n == 0:
        return 0.0
    return math.fsum(values) / n


def variance(values: Sequence[float], ddof: int = 0) -> float:
    """Population (ddof=0) or sample (ddof=1) variance."""
    n = len(values)
    if n - ddof <= 0:
        return 0.0
    mu = mean(values)
    return math.fsum((v - mu) ** 2 for v in values) / (n - ddof)


def std(values: Sequence[float], ddof: int = 0) -> float:
    """Standard deviation."""
    return math.sqrt(variance(values, ddof))


def median(values: Sequence[float]) -> float:
    """Median of a sequence; 0.0 for empty."""
    n = len(values)
    if n == 0:
        return 0.0
    s = sorted(values)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, ``q`` in [0, 100]."""
    n = len(values)
    if n == 0:
        return 0.0
    if n == 1:
        return float(values[0])
    s = sorted(values)
    if q <= 0:
        return s[0]
    if q >= 100:
        return s[-1]
    rank = (q / 100.0) * (n - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return s[lo]
    frac = rank - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


def magnitude(x: Sequence[Complex]) -> List[float]:
    """Element-wise magnitude ``|z|``."""
    return [abs(v) for v in x]


def power(x: Sequence[Complex]) -> List[float]:
    """Element-wise instantaneous power ``|z|**2``."""
    return [(v.real * v.real + v.imag * v.imag) if isinstance(v, complex)
            else v * v for v in x]


def to_db(values: Sequence[float], ref: float = 1.0, floor_db: float = -300.0) -> List[float]:
    """Convert linear power values to decibels: ``10*log10(v/ref)``.

    Non-positive values are clamped to ``floor_db`` to avoid math domain errors.
    """
    out: List[float] = []
    for v in values:
        r = v / ref if ref else v
        if r <= _TINY:
            out.append(floor_db)
        else:
            out.append(10.0 * math.log10(r))
    return out


def db10(v: float, floor_db: float = -300.0) -> float:
    """Scalar power-to-dB (10*log10)."""
    if v <= _TINY:
        return floor_db
    return 10.0 * math.log10(v)


def db20(v: float, floor_db: float = -300.0) -> float:
    """Scalar amplitude-to-dB (20*log10)."""
    if v <= _TINY:
        return floor_db
    return 20.0 * math.log10(v)


def unwrap(phase: Sequence[float], discont: float = math.pi) -> List[float]:
    """Unwrap radian phase by removing 2*pi jumps larger than ``discont``."""
    if not phase:
        return []
    out = [float(phase[0])]
    offset = 0.0
    prev = phase[0]
    for p in phase[1:]:
        d = p - prev
        while d > discont:
            offset -= 2.0 * math.pi
            d -= 2.0 * math.pi
        while d < -discont:
            offset += 2.0 * math.pi
            d += 2.0 * math.pi
        out.append(p + offset)
        prev = p
    return out


def diff(values: Sequence[float]) -> List[float]:
    """First difference ``v[i+1] - v[i]``."""
    return [values[i + 1] - values[i] for i in range(len(values) - 1)]


def linspace(start: float, stop: float, num: int, endpoint: bool = True) -> List[float]:
    """Evenly spaced values, ``num`` samples, matching NumPy semantics."""
    if num <= 0:
        return []
    if num == 1:
        return [float(start)]
    div = (num - 1) if endpoint else num
    step = (stop - start) / div
    return [start + step * i for i in range(num)]


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp ``value`` into ``[lo, hi]``."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def normalize_unit(values: Sequence[float]) -> List[float]:
    """Scale values into [0, 1] using min/max; a flat input maps to zeros."""
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    span = hi - lo
    if span <= _TINY:
        return [0.0 for _ in values]
    return [(v - lo) / span for v in values]


def rms(x: Sequence[Complex]) -> float:
    """Root-mean-square of a (possibly complex) signal."""
    if not x:
        return 0.0
    return math.sqrt(mean(power(x)))


def dot_conj(a: Sequence[Complex], b: Sequence[Complex]) -> Complex:
    """Complex inner product ``sum(a * conj(b))``."""
    total = 0j
    for ai, bi in zip(a, b):
        total += ai * (bi.conjugate() if isinstance(bi, complex) else bi)
    return total
