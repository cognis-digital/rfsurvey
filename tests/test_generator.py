"""Tests for the synthetic signal generator."""

from __future__ import annotations

import math

import pytest

from wavewatch.io.capture import Capture
from wavewatch.io.generator import (
    SCENARIOS,
    apply_burst_envelope,
    chirp,
    complex_noise,
    generate,
    spread_spectrum,
    tone,
    wideband_burst,
)
from tests.conftest import SCENARIOS as SCEN_NAMES


@pytest.mark.parametrize("n", [0, 1, 16, 256, 1024])
def test_complex_noise_length(n):
    assert len(complex_noise(n)) == n


def test_complex_noise_deterministic():
    import random
    a = complex_noise(100, 1.0, random.Random(42))
    b = complex_noise(100, 1.0, random.Random(42))
    assert a == b


def test_complex_noise_power_approx():
    from wavewatch.dsp.util import mean, power
    x = complex_noise(20000, 4.0)
    assert math.isclose(mean(power(x)), 4.0, rel_tol=0.1)


@pytest.mark.parametrize("n", [16, 128, 1024])
def test_tone_length(n):
    assert len(tone(n, 100.0, 1000.0)) == n


def test_tone_unit_magnitude():
    x = tone(64, 100.0, 1000.0, amp=1.0)
    assert all(math.isclose(abs(v), 1.0, abs_tol=1e-9) for v in x)


def test_tone_amplitude():
    x = tone(64, 100.0, 1000.0, amp=3.0)
    assert all(math.isclose(abs(v), 3.0, abs_tol=1e-9) for v in x)


@pytest.mark.parametrize("n", [16, 128, 512])
def test_chirp_length(n):
    assert len(chirp(n, 0.0, 100.0, 1000.0)) == n


def test_chirp_single_sample():
    assert len(chirp(1, 0.0, 100.0, 1000.0)) == 1


@pytest.mark.parametrize("n", [64, 256])
def test_wideband_burst_length(n):
    assert len(wideband_burst(n, 500.0, 1000.0)) == n


@pytest.mark.parametrize("n", [64, 256])
def test_spread_spectrum_length(n):
    assert len(spread_spectrum(n, 500.0, 1000.0)) == n


def test_apply_burst_envelope():
    sig = [1 + 0j] * 10
    gated = apply_burst_envelope(sig, 2, 5)
    assert gated[0] == 0j and gated[2] == 1 + 0j and gated[5] == 0j


@pytest.mark.parametrize("scenario", SCEN_NAMES)
def test_generate_returns_capture(scenario):
    cap, label = generate(scenario)
    assert isinstance(cap, Capture)
    assert isinstance(label, str)


@pytest.mark.parametrize("scenario", SCEN_NAMES)
def test_generate_has_samples(scenario):
    cap, _ = generate(scenario)
    assert cap.n_samples > 0
    assert cap.sample_rate > 0


@pytest.mark.parametrize("scenario", SCEN_NAMES)
def test_generate_deterministic(scenario):
    a, _ = generate(scenario)
    b, _ = generate(scenario)
    assert a.samples == b.samples


def test_generate_unknown_scenario():
    with pytest.raises(ValueError):
        generate("does-not-exist")


def test_scenarios_registry_complete():
    for name in ["noise", "tone", "wifi", "drone-link", "ble", "gnss", "sweep", "barrage"]:
        assert name in SCENARIOS


@pytest.mark.parametrize("scenario,expected", [
    ("tone", "unknown"), ("wifi", "wifi"), ("drone-link", "drone-link"),
    ("ble", "ble"), ("gnss", "gnss"), ("noise", "none"),
])
def test_generate_expected_labels(scenario, expected):
    _, label = generate(scenario)
    assert label == expected


def test_position_passthrough():
    cap, _ = generate("wifi", position=(40.0, -75.0))
    assert cap.position == (40.0, -75.0)


def test_gnss_center_freq_in_band():
    cap, _ = generate("gnss")
    assert abs(cap.center_freq - 1_575_420_000.0) < 1e3
