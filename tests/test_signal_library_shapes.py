"""📐 Chart shapes (signal_library/signals_shapes.py): drawn shapes are found, staged and never change with later
candles."""

import numpy as np
import pandas as pd

from signal_library.core import INSUFFICIENT, OK
from signal_library.signals_shapes import KINDS, find_shapes
from tests.test_signal_library_oscillators import _run, _walk


def _path(points, step=10):
    """A price path through the given turning points, `step` candles between each."""
    out = [points[0]]
    for a, b in zip(points, points[1:]):
        out += list(np.linspace(a, b, step + 1)[1:])
    return np.array(out, float)


def _frame(close):
    close = np.asarray(close, float)
    n = len(close)
    df = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "high": close + 0.4, "low": close - 0.4, "close": close,
                       "volume": np.full(n, 100.0)}, index=pd.date_range("2023-01-01", periods=n, freq="1D", tz="UTC"))
    df["forming"] = False
    df.iloc[-1, df.columns.get_loc("forming")] = True
    return df


HS = [100, 90, 110, 100, 120, 100, 110, 92, 85]        # a lead-in, shoulder, trough, head, trough, shoulder, the break
INV = [120, 130, 110, 120, 100, 120, 110, 128, 135]


def test_head_and_shoulders_is_found_and_confirmed():
    f = _frame(np.r_[_path(HS), 0])
    found = [s for s in find_shapes(f.iloc[:-1]) if s["kind"] == "head_shoulders"]
    assert found and found[-1]["stage"] == "confirmed"
    assert found[-1]["target"] < found[-1]["neckline"] < 101
    r = _run("shape.classic", f)
    assert r.status == OK and r.value["head_shoulders_stage"] == "confirmed"
    assert 0 <= r.value["head_shoulders_ago"] < 20


def test_inverse_is_the_mirror():
    r = _run("shape.classic", _frame(np.r_[_path(INV), 0]))
    assert r.value["inverse_head_shoulders_stage"] == "confirmed"
    assert r.value["inverse_head_shoulders_target"] > r.value["inverse_head_shoulders_neckline"]


def test_forming_before_the_break():
    close = _path(HS)
    cut = len(close) - 15                                  # the right shoulder known, the neckline not yet broken
    r = _run("shape.classic", _frame(np.r_[close[:cut], 0]))
    assert r.value["head_shoulders_stage"] in ("forming", "none")
    assert r.value["head_shoulders_ago"] == 50


def test_double_bottom():
    r = _run("shape.classic", _frame(np.r_[_path([130, 120, 100, 115, 100, 118, 125]), 0]))
    assert r.value["double_bottom_stage"] == "confirmed"


def test_a_shape_never_changes_when_later_candles_arrive():
    close = 100 * np.exp(np.cumsum(np.random.default_rng(5).normal(0, 0.02, 900)))
    full = find_shapes(_frame(close).iloc[:-1])
    for cut in (400, 600, 800):
        early = find_shapes(_frame(close[:cut + 1]).iloc[:-1])
        later = {(s["kind"], s["points"][0][0], s["ready"]): s for s in full}
        for s in early:
            twin = later[(s["kind"], s["points"][0][0], s["ready"])]
            if s["confirmed_index"] is not None:
                assert twin["confirmed_index"] == s["confirmed_index"]


def test_every_kind_is_read_and_short_history_says_so():
    r = _run("shape.classic", _frame(np.r_[_walk(400, seed=3), 0]))
    assert r.status == OK
    for kind in KINDS:
        assert r.value[f"{kind}_stage"] in ("forming", "confirmed", "failed", "none")
        assert 0 <= r.value[f"{kind}_ago"] <= 50
    assert _run("shape.classic", _frame(_walk(30))).status == INSUFFICIENT


def test_offered_in_the_editor_as_recency():
    import lattice_editor as le

    s = next(x for x in le.catalogue() if x["id"] == "shape.classic")
    kinds = {o["field"]: o["type"] for o in s["operands"]}
    assert kinds["head_shoulders_ago"] == le.RECENCY and kinds["double_top_stage"] == "label"


def test_chart_draws_recent_shapes_only():
    import lw_chart

    f = _frame(np.r_[_path(HS), 0])
    drawn = lw_chart.shape_overlay(f)
    assert any(s["kind"] == "head_shoulders" and s["stage"] == "confirmed" for s in drawn)
    assert all("Head and shoulders" in s["words"] or s["kind"] != "head_shoulders" for s in drawn)


def test_golden_and_death_crosses():
    from signal_library.signals_shapes import crosses

    down_up = np.r_[np.linspace(200, 100, 260), np.linspace(100, 190, 120)]
    golden, death = crosses(_frame(down_up).iloc[:-1])
    assert golden.sum() == 1 and death.sum() == 0
    r = _run("shape.classic", _frame(np.r_[down_up, 0]), lookback=150)
    assert r.value["golden_cross_ago"] < 150 and r.value["death_cross_ago"] == 150
    import lw_chart

    stars = lw_chart.cross_symbols(_frame(np.r_[down_up, 0]))
    assert len(stars) == 1 and stars[0][1] == "star" and "Golden" in stars[0][5]
