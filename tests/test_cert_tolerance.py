"""Slice equivalence within a stated tolerance (docs/design/point_in_time.md §13)."""

import json

from signal_library import certification
from signal_library import certify as cf


def _j(x):
    return json.dumps(x, sort_keys=True)


def test_last_digit_noise_is_equal_and_reported_without_raw_digits():
    a = {"value": {"standard_score": 0.7347059897980095, "close": 101.25}, "status": "ok"}
    b = {"value": {"standard_score": 0.7347059898057529, "close": 101.25}, "status": "ok"}
    assert cf._slice_difference(_j(a), _j(b)) == ""
    c = {"value": {"standard_score": -0.1689131161684083}}
    d = {"value": {"standard_score": -0.1689131161684084}}
    assert cf._slice_difference(_j(c), _j(d)) == ""


def test_real_differences_still_fail():
    a = {"value": {"standard_score": 0.73, "rsi": 55.0}, "status": "ok"}
    assert cf._slice_difference(_j(a), _j({**a, "value": {"standard_score": 0.7301, "rsi": 55.0}})) == \
        ".value.standard_score: differs by 1.0e-04 (beyond the 1e-09 tolerance)"
    assert "vs" in cf._slice_difference(_j(a), _j({**a, "status": "stale"}))
    assert "missing on one side" in cf._slice_difference(_j(a), _j({"value": a["value"]}))
    assert cf._slice_difference(_j({"x": [1, 2]}), _j({"x": [1]})) == ".x: 2 vs 1 items"
    assert cf._slice_difference(_j({"x": True}), _j({"x": 1})) == ".x: different kinds of value"


def test_tolerance_scales_with_large_numbers_only_upwards():
    big = 4.2e9
    assert cf._slice_difference(_j({"v": big}), _j({"v": big + 1.0})) == ""        # 1 part in 4e9
    assert cf._slice_difference(_j({"v": big}), _j({"v": big + 100.0}))            # 2.4e-8 relative
    assert cf._slice_difference(_j({"v": 0.0}), _j({"v": 5e-10})) == ""            # absolute floor of 1e-9
    assert cf._slice_difference(_j({"v": 0.0}), _j({"v": 5e-9}))


def test_suite_version_records_the_method_change():
    assert certification.SUITE_VERSION == 2
    assert cf.SLICE_TOLERANCE == 1e-9
