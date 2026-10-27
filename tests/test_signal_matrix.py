import math

import pytest

pytest.importorskip("pandas_ta")  # signal_matrix imports scoring

import signal_matrix as sm


def test_align_forward_fills_and_leaves_early_days_empty():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    points = [("2024-01-02", 60), ("2024-01-04T10:00:00", 40)]
    assert sm._align(dates, points) == [None, 60.0, 60.0, 40.0]


def test_align_ignores_bad_points():
    assert sm._align(["2024-01-01"], [("2024-01-01", "x"), (None,), "oops"]) == [None]


def test_correlation_needs_enough_pairs():
    assert sm._correlation([1, 2, 3], [1, 2, 3]) is None
    values = list(range(10))
    assert math.isclose(sm._correlation(values, values), 1.0)
    assert sm._correlation([5] * 10, values) is None


def test_forward_returns():
    out = sm._forward_returns([100.0, 110.0, 99.0], 1)
    assert math.isclose(out[0], 10.0) and math.isclose(out[1], -10.0) and out[2] is None


def test_support_flags_thin_data():
    values = [float(i) for i in range(30)]
    returns = [float(i) for i in range(30)]
    one_day = sm._support(values, returns, 1.0, 1)
    seven_day = sm._support(values, returns, 1.0, 7)
    assert one_day["reliable"] is True
    assert seven_day["effective_n"] < sm._MIN_EFFECTIVE and seven_day["reliable"] is False


def test_support_rejects_lead_inside_noise():
    values = list(range(40))
    returns = list(range(40))
    assert sm._support(values, returns, 0.05, 1)["reliable"] is False


def test_boundary_lines_include_base_rate():
    scores = [80, 80, 80, 80, 80, 20, 20, 20, 20, 20, 50]
    closes = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100]
    high, low = sm.boundary_lines(scores, closes, 70, 30, horizons=(1,))
    assert "all days:" in high and "all days:" in low
    assert "in 5 of 5 cases" in high


def test_boundary_lines_flag_too_few_cases():
    high, _ = sm.boundary_lines([80, 50, 50, 50], [1, 2, 3, 4], 70, 30, horizons=(1,))
    assert "too few to judge" in high


def test_weekend_edges_marks_friday_and_monday():
    days = ["2024-01-04", "2024-01-05", "2024-01-08", "2024-01-09"]
    assert sm.weekend_edges(days) == ["2024-01-05", "2024-01-08"]
