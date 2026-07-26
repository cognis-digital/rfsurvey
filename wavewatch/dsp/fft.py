"""Pure-Python FFT implementation (no NumPy).

Provides:
  * :func:`dft` / :func:`idft` -- direct O(N^2) reference transforms.
  * :func:`fft` / :func:`ifft` -- fast transforms. Radix-2 Cooley-Tukey for
    power-of-two lengths, Bluestein's chirp-z algorithm for arbitrary lengths.
  * :func:`rfft` -- one-sided spectrum of a real signal.
  * :func:`fftfreq` / :func:`fftshift` -- frequency-bin helpers.

All routines operate on plain Python lists of complex/float values.
"""

from __future__ import annotations

import cmath
import math
from typing import List, Sequence

Complex = complex


def is_power_of_two(n: int) -> bool:
    """True if ``n`` is a positive power of two."""
    return n > 0 and (n & (n - 1)) == 0


def next_power_of_two(n: int) -> int:
    """Smallest power of two >= ``n`` (>= 1)."""
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def dft(x: Sequence[Complex]) -> List[Complex]:
    """Direct discrete Fourier transform, O(N^2). Reference implementation."""
    n = len(x)
    out: List[Complex] = []
    for k in range(n):
        acc = 0j
        base = -2j * math.pi * k / n if n else 0j
        for j in range(n):
            acc += x[j] * cmath.exp(base * j)
        out.append(acc)
    return out


def idft(x: Sequence[Complex]) -> List[Complex]:
    """Direct inverse DFT, O(N^2)."""
    n = len(x)
    if n == 0:
        return []
    out: List[Complex] = []
    for k in range(n):
        acc = 0j
        base = 2j * math.pi * k / n
        for j in range(n):
            acc += x[j] * cmath.exp(base * j)
        out.append(acc / n)
    return out


def _fft_radix2(a: List[Complex]) -> List[Complex]:
    """In-place iterative radix-2 Cooley-Tukey FFT. len(a) must be power of two."""
    n = len(a)
    if n <= 1:
        return a
    # Bit-reversal permutation.
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    # Butterfly stages.
    length = 2
    while length <= n:
        ang = -2j * math.pi / length
        wlen = cmath.exp(ang)
        half = length >> 1
        for i in range(0, n, length):
            w = 1 + 0j
            for k in range(half):
                u = a[i + k]
                v = a[i + k + half] * w
                a[i + k] = u + v
                a[i + k + half] = u - v
                w *= wlen
        length <<= 1
    return a


def _bluestein(x: Sequence[Complex]) -> List[Complex]:
    """Bluestein's algorithm for arbitrary-length DFT via power-of-two FFT."""
    n = len(x)
    if n == 0:
        return []
    if n == 1:
        return [complex(x[0])]
    m = next_power_of_two(2 * n + 1)
    # Chirp table exp(-i*pi*k^2 / n).
    exptable = [cmath.exp(-1j * math.pi * ((i * i) % (2 * n)) / n) for i in range(n)]
    a = [complex(x[i]) * exptable[i] for i in range(n)] + [0j] * (m - n)
    b = [0j] * m
    b[0] = exptable[0]
    for i in range(1, n):
        val = exptable[i].conjugate()
        b[i] = val
        b[m - i] = val
    conv = _circular_convolve_pow2(a, b)
    return [conv[i] * exptable[i] for i in range(n)]


def _circular_convolve_pow2(a: List[Complex], b: List[Complex]) -> List[Complex]:
    """Circular convolution of two equal power-of-two length sequences."""
    fa = _fft_radix2(list(a))
    fb = _fft_radix2(list(b))
    prod = [fa[i] * fb[i] for i in range(len(fa))]
    # inverse FFT = conj(fft(conj(x)))/n
    conj = [p.conjugate() for p in prod]
    inv = _fft_radix2(conj)
    n = len(inv)
    return [v.conjugate() / n for v in inv]


def fft(x: Sequence[Complex]) -> List[Complex]:
    """Fast Fourier transform for any length ``N``."""
    n = len(x)
    if n == 0:
        return []
    if is_power_of_two(n):
        return _fft_radix2([complex(v) for v in x])
    return _bluestein(x)


def ifft(x: Sequence[Complex]) -> List[Complex]:
    """Inverse fast Fourier transform for any length ``N``."""
    n = len(x)
    if n == 0:
        return []
    conj = [complex(v).conjugate() for v in x]
    y = fft(conj)
    return [v.conjugate() / n for v in y]


def rfft(x: Sequence[float]) -> List[Complex]:
    """One-sided FFT of a real signal: bins ``0 .. N//2``."""
    full = fft([complex(v) for v in x])
    n = len(full)
    return full[: n // 2 + 1]


def fftfreq(n: int, d: float = 1.0) -> List[float]:
    """DFT sample frequencies (matches numpy.fft.fftfreq)."""
    if n == 0:
        return []
    val = 1.0 / (n * d)
    out = [0.0] * n
    half = (n - 1) // 2 + 1
    for i in range(half):
        out[i] = i * val
    for i in range(half, n):
        out[i] = (i - n) * val
    return out


def fftshift(x: Sequence) -> List:
    """Shift zero-frequency component to the center of the spectrum."""
    n = len(x)
    if n == 0:
        return []
    shift = n // 2
    return list(x[shift:]) + list(x[:shift])


def ifftshift(x: Sequence) -> List:
    """Inverse of :func:`fftshift`."""
    n = len(x)
    if n == 0:
        return []
    shift = (n + 1) // 2
    return list(x[shift:]) + list(x[:shift])
