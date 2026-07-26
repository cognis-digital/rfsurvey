"""Shared pytest fixtures and helpers for the wavewatch test suite."""

from __future__ import annotations

import cmath
import math
import random

import pytest

from wavewatch.io.capture import Capture


def approx_equal_seq(a, b, tol=1e-6):
    """True if two numeric sequences are elementwise close."""
    if len(a) != len(b):
        return False
    return all(abs(complex(x) - complex(y)) <= tol for x, y in zip(a, b))


def random_complex(n, seed=0):
    rng = random.Random(seed)
    return [complex(rng.gauss(0, 1), rng.gauss(0, 1)) for _ in range(n)]


def random_real(n, seed=0):
    rng = random.Random(seed)
    return [rng.gauss(0, 1) for _ in range(n)]


@pytest.fixture
def rng():
    return random.Random(1234)


@pytest.fixture
def tone_capture():
    from wavewatch.io.generator import gen_tone
    cap, label = gen_tone()
    return cap, label


@pytest.fixture
def drone_capture():
    from wavewatch.io.generator import gen_drone_link
    cap, label = gen_drone_link()
    return cap, label


# Common size grids used across many parametrized tests.
FFT_SIZES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 15, 16, 17, 24, 31, 32, 63, 64, 100, 128]
WINDOW_NAMES = ["rectangular", "hann", "hamming", "blackman", "blackman_harris", "bartlett"]
SCENARIOS = ["noise", "tone", "wifi", "drone-link", "ble", "gnss", "sweep", "barrage"]
CLASSIFY_SCENARIOS = {
    "tone": "unknown",
    "wifi": "wifi",
    "drone-link": "drone-link",
    "ble": "ble",
    "gnss": "gnss",
}
