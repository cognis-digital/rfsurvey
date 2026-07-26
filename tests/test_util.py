"""Tests for DSP numeric helpers."""

from __future__ import annotations

import math

import pytest

from wavewatch.dsp.util import (
    clamp,
    db10,
    db20,
    diff,
    dot_conj,
    linspace,
    magnitude,
    mean,
    median,
    normalize_unit,
    percentile,
    power,
    rms,
    std,
    to_db,
    unwrap,
    variance,
)


def test_mean_basic():
    assert mean([1, 2, 3, 4]) == 2.5


def test_mean_empty():
    assert mean([]) == 0.0


def test_variance_population():
    assert math.isclose(variance([1, 2, 3, 4, 5]), 2.0)


def test_variance_sample():
    assert math.isclose(variance([1, 2, 3, 4, 5], ddof=1), 2.5)


def test_std():
    assert math.isclose(std([2, 4, 4, 4, 5, 5, 7, 9]), 2.0)


def test_std_empty():
    assert std([]) == 0.0


def test_median_odd():
    assert median([3, 1, 2]) == 2


def test_median_even():
    assert median([1, 2, 3, 4]) == 2.5


def test_median_empty():
    assert median([]) == 0.0


@pytest.mark.parametrize("q,expected", [(0, 1), (100, 5), (50, 3)])
def test_percentile(q, expected):
    assert percentile([1, 2, 3, 4, 5], q) == expected


def test_percentile_empty():
    assert percentile([], 50) == 0.0


def test_percentile_single():
    assert percentile([7], 25) == 7


def test_magnitude():
    assert magnitude([3 + 4j, 0]) == [5.0, 0.0]


def test_power():
    assert power([3 + 4j]) == [25.0]


def test_to_db():
    assert to_db([1.0, 10.0, 100.0]) == [0.0, 10.0, 20.0]


def test_to_db_floor():
    assert to_db([0.0])[0] == -300.0


def test_db10_db20():
    assert math.isclose(db10(100), 20.0)
    assert math.isclose(db20(10), 20.0)


def test_db10_floor():
    assert db10(0) == -300.0


def test_diff():
    assert diff([1, 3, 6, 10]) == [2, 3, 4]


def test_diff_short():
    assert diff([5]) == []


def test_unwrap_no_jump():
    p = [0.0, 0.1, 0.2]
    assert unwrap(p) == p


def test_unwrap_jump():
    p = [0.0, 3.0, -3.0]  # wraps around
    u = unwrap(p)
    # difference between consecutive unwrapped should be small
    assert abs(u[2] - u[1]) < math.pi


def test_unwrap_empty():
    assert unwrap([]) == []


@pytest.mark.parametrize("num", [0, 1, 2, 5, 10])
def test_linspace_length(num):
    assert len(linspace(0, 1, num)) == num


def test_linspace_endpoints():
    ls = linspace(0, 10, 11)
    assert ls[0] == 0 and ls[-1] == 10


def test_linspace_no_endpoint():
    ls = linspace(0, 10, 10, endpoint=False)
    assert ls[0] == 0 and ls[-1] == 9


@pytest.mark.parametrize("v,lo,hi,expected", [
    (5, 0, 10, 5), (-1, 0, 10, 0), (11, 0, 10, 10), (0, 0, 10, 0),
])
def test_clamp(v, lo, hi, expected):
    assert clamp(v, lo, hi) == expected


def test_normalize_unit():
    assert normalize_unit([0, 5, 10]) == [0.0, 0.5, 1.0]


def test_normalize_unit_flat():
    assert normalize_unit([3, 3, 3]) == [0.0, 0.0, 0.0]


def test_normalize_unit_empty():
    assert normalize_unit([]) == []


def test_rms():
    assert math.isclose(rms([3, 4]), math.sqrt(12.5))


def test_rms_empty():
    assert rms([]) == 0.0


def test_dot_conj():
    assert dot_conj([1 + 1j], [1 + 1j]) == 2 + 0j
