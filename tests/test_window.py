"""Tests for window functions."""

from __future__ import annotations

import math

import pytest

from wavewatch.dsp.window import (
    bartlett,
    blackman,
    blackman_harris,
    get_window,
    hamming,
    hann,
    rectangular,
    window_names,
)
from tests.conftest import WINDOW_NAMES

SIZES = [1, 2, 3, 4, 8, 16, 32, 64, 128, 256]


@pytest.mark.parametrize("name", WINDOW_NAMES)
@pytest.mark.parametrize("n", SIZES)
def test_window_length(name, n):
    assert len(get_window(name, n)) == n


@pytest.mark.parametrize("name", WINDOW_NAMES)
@pytest.mark.parametrize("n", SIZES)
def test_window_values_in_range(name, n):
    w = get_window(name, n)
    assert all(-1e-9 <= v <= 1.0 + 1e-9 for v in w)


@pytest.mark.parametrize("name", WINDOW_NAMES)
def test_window_symmetry(name):
    n = 33
    w = get_window(name, n)
    for i in range(n):
        assert math.isclose(w[i], w[n - 1 - i], abs_tol=1e-9)


@pytest.mark.parametrize("n", SIZES)
def test_rectangular_all_ones(n):
    assert rectangular(n) == [1.0] * n


def test_hann_endpoints_zero():
    w = hann(16)
    assert math.isclose(w[0], 0.0, abs_tol=1e-9)
    assert math.isclose(w[-1], 0.0, abs_tol=1e-9)


def test_hamming_endpoints():
    w = hamming(16)
    assert math.isclose(w[0], 0.08, abs_tol=1e-9)


def test_hann_center_is_one():
    w = hann(9)
    assert math.isclose(max(w), 1.0, abs_tol=1e-9)


@pytest.mark.parametrize("fn", [hann, hamming, blackman, blackman_harris, bartlett])
def test_window_single_sample(fn):
    assert fn(1) == [1.0]


@pytest.mark.parametrize("fn", [hann, hamming, blackman, blackman_harris, bartlett, rectangular])
def test_window_zero_length(fn):
    assert fn(0) == []


def test_get_window_unknown_raises():
    with pytest.raises(ValueError):
        get_window("not-a-window", 8)


def test_window_names_nonempty():
    assert "hann" in window_names()
    assert "blackman" in window_names()


@pytest.mark.parametrize("alias,canonical", [
    ("hanning", hann), ("boxcar", rectangular), ("rect", rectangular),
    ("triangular", bartlett), ("blackmanharris", blackman_harris),
])
def test_window_aliases(alias, canonical):
    assert get_window(alias, 16) == canonical(16)


def test_bartlett_triangular_peak():
    w = bartlett(9)
    assert math.isclose(max(w), 1.0, abs_tol=1e-9)
    assert math.isclose(w[0], 0.0, abs_tol=1e-9)
