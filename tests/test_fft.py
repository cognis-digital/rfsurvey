"""Tests for the pure-Python FFT core."""

from __future__ import annotations

import cmath
import math

import pytest

from wavewatch.dsp import fft as fftmod
from wavewatch.dsp.fft import (
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
from tests.conftest import FFT_SIZES, approx_equal_seq, random_complex, random_real


@pytest.mark.parametrize("n", FFT_SIZES)
def test_fft_matches_dft(n):
    x = random_complex(n, seed=n)
    assert approx_equal_seq(fft(x), dft(x), tol=1e-6)


@pytest.mark.parametrize("n", FFT_SIZES)
def test_ifft_roundtrip(n):
    x = random_complex(n, seed=n + 1)
    assert approx_equal_seq(ifft(fft(x)), x, tol=1e-6)


@pytest.mark.parametrize("n", FFT_SIZES)
def test_idft_roundtrip(n):
    x = random_complex(n, seed=n + 2)
    assert approx_equal_seq(idft(dft(x)), x, tol=1e-6)


@pytest.mark.parametrize("n", FFT_SIZES)
def test_fft_output_length(n):
    x = random_complex(n, seed=n)
    assert len(fft(x)) == n


@pytest.mark.parametrize("n", FFT_SIZES)
def test_fft_linearity(n):
    a = random_complex(n, seed=n)
    b = random_complex(n, seed=n + 100)
    fa = fft(a)
    fb = fft(b)
    fsum = fft([a[i] + b[i] for i in range(n)])
    assert approx_equal_seq(fsum, [fa[i] + fb[i] for i in range(n)], tol=1e-6)


@pytest.mark.parametrize("n", FFT_SIZES)
def test_parseval(n):
    x = random_complex(n, seed=n + 7)
    X = fft(x)
    time_energy = sum(abs(v) ** 2 for v in x)
    freq_energy = sum(abs(v) ** 2 for v in X) / n
    assert math.isclose(time_energy, freq_energy, rel_tol=1e-6, abs_tol=1e-9)


@pytest.mark.parametrize("n", FFT_SIZES)
def test_fft_scaling(n):
    x = random_complex(n, seed=n)
    fx = fft(x)
    f2 = fft([2 * v for v in x])
    assert approx_equal_seq(f2, [2 * v for v in fx], tol=1e-6)


def test_delta_transforms_to_ones():
    assert approx_equal_seq(fft([1, 0, 0, 0]), [1, 1, 1, 1])


def test_constant_transforms_to_impulse():
    assert approx_equal_seq(fft([1, 1, 1, 1]), [4, 0, 0, 0])


def test_empty_fft():
    assert fft([]) == []
    assert ifft([]) == []
    assert dft([]) == []


def test_single_sample_fft():
    assert approx_equal_seq(fft([3 + 4j]), [3 + 4j])


@pytest.mark.parametrize("n", [1, 2, 4, 8, 16, 32, 64, 128])
def test_is_power_of_two_true(n):
    assert is_power_of_two(n)


@pytest.mark.parametrize("n", [0, 3, 5, 6, 7, 9, 100, 127])
def test_is_power_of_two_false(n):
    assert not is_power_of_two(n)


@pytest.mark.parametrize("n,expected", [
    (1, 1), (2, 2), (3, 4), (5, 8), (7, 8), (9, 16), (100, 128), (127, 128), (128, 128),
])
def test_next_power_of_two(n, expected):
    assert next_power_of_two(n) == expected


@pytest.mark.parametrize("n", [4, 8, 16, 32])
def test_pure_tone_single_bin(n):
    # a complex exponential at bin k should concentrate energy in bin k
    k = 1
    x = [cmath.exp(2j * math.pi * k * m / n) for m in range(n)]
    X = fft(x)
    mags = [abs(v) for v in X]
    peak = mags.index(max(mags))
    assert peak == k
    # off-bins near zero
    for i, m in enumerate(mags):
        if i != k:
            assert m < 1e-6


@pytest.mark.parametrize("n", [2, 4, 8, 16, 32])
def test_rfft_length(n):
    x = random_real(n, seed=n)
    assert len(rfft(x)) == n // 2 + 1


@pytest.mark.parametrize("n", [4, 8, 16])
def test_rfft_matches_fft_prefix(n):
    x = random_real(n, seed=n)
    full = fft([complex(v) for v in x])
    r = rfft(x)
    assert approx_equal_seq(r, full[: n // 2 + 1], tol=1e-6)


def test_fftfreq_even():
    assert approx_equal_seq(fftfreq(4, 1.0), [0.0, 0.25, -0.5, -0.25])


def test_fftfreq_odd():
    assert approx_equal_seq(fftfreq(5, 1.0), [0.0, 0.2, 0.4, -0.4, -0.2])


def test_fftfreq_with_spacing():
    f = fftfreq(8, d=0.5)
    assert math.isclose(f[1], 1.0 / (8 * 0.5))


def test_fftfreq_empty():
    assert fftfreq(0) == []


@pytest.mark.parametrize("n", [2, 3, 4, 5, 8])
def test_fftshift_roundtrip(n):
    x = list(range(n))
    assert ifftshift(fftshift(x)) == x


def test_fftshift_even():
    assert fftshift([0, 1, 2, 3]) == [2, 3, 0, 1]


def test_fftshift_empty():
    assert fftshift([]) == []


@pytest.mark.parametrize("n", [3, 5, 6, 7, 12, 15])
def test_bluestein_nonpow2_accuracy(n):
    x = random_complex(n, seed=n * 3)
    assert approx_equal_seq(fft(x), dft(x), tol=1e-6)


@pytest.mark.parametrize("n", FFT_SIZES)
def test_dc_component_is_sum(n):
    x = random_complex(n, seed=n)
    X = fft(x)
    assert abs(X[0] - sum(x)) < 1e-6
