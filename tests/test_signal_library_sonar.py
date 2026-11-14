"""🛰️ Sonar markers and the Stoch RSI pair (signal_library/signals_sonar.py), checked against the published formulas
written out independently here."""

import numpy as np
import pandas as pd

from signal_library.core import INSUFFICIENT, OK
from signal_library.signals_sonar import MARKERS, candles_ago, markers_frame, stoch_rsi_frame
from tests.test_signal_library_oscillators import _frame, _run, _walk


def _ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def test_candles_ago_counts_from_the_last_candle():
    s = pd.Series([False, True, False, False])
    assert candles_ago(s, 10) == 2
    assert candles_ago(pd.Series([False, False, True]), 10) == 0
    assert candles_ago(pd.Series([True] + [False] * 20), 10) == 10      # outside the window: the window's size


def test_markers_match_the_published_crosses():
    f = _frame(_walk(400, seed=7)).iloc[:-1]
    mk = markers_frame(f)
    e5, e11, e15, e34 = (_ema(f["close"], n) for n in (5, 11, 15, 34))
    turn = (e11 > e15) & (e11.shift(1) <= e15.shift(1))
    red = (e5 < e11) & (e5.shift(1) >= e11.shift(1))
    green = (e11 > e34) & (e11.shift(1) <= e34.shift(1))
    assert mk["trend_turn_up"].equals(turn)
    assert mk["red_cross"].equals(red)
    assert mk["long_cross"].equals(green)
    assert (mk["blood_diamond"] == (mk["red_diamond"] & mk["red_cross"])).all()
    assert not (mk["yellow_cross"] & ~mk["red_diamond"]).any()        # a yellow cross is always a red diamond too
    assert turn.sum() > 0 and red.sum() > 0


def test_signal_reads_candles_ago_for_every_marker():
    f = _frame(_walk(400, seed=7))
    r = _run("sonar.markers", f, lookback=60)
    assert r.status == OK
    mk = markers_frame(f.iloc[:-1])
    for name, _words in MARKERS:
        assert r.value[f"{name}_ago"] == candles_ago(mk[name], 60), name
        assert 0 <= r.value[f"{name}_ago"] <= 60
    assert r.value["band"] in ("above", "inside", "below")
    assert r.value["band_order"] in ("rising", "falling", "mixed")


def test_a_steady_rise_sits_above_a_rising_band():
    close = np.r_[np.linspace(100, 200, 200), 0]
    r = _run("sonar.markers", _frame(close))
    assert r.value["band"] == "above" and r.value["band_order"] == "rising"
    assert r.value["red_cross_ago"] == 50                                 # none in the window


def test_stoch_rsi_pair_and_crosses():
    f = _frame(_walk(300, seed=3))
    r = _run("osc.stoch_rsi", f)
    assert r.status == OK
    s = stoch_rsi_frame(f.iloc[:-1])
    assert abs(r.value["k"] - s["k"].iloc[-1]) < 0.01 and abs(r.value["d"] - s["d"].iloc[-1]) < 0.01
    up = (s["k"] > s["d"]) & (s["k"].shift(1) <= s["d"].shift(1))
    assert r.value["cross_up_ago"] == candles_ago(up, 50)
    assert r.value["cross_up_from_low_ago"] >= r.value["cross_up_ago"]   # a narrower kind is never more recent
    assert r.value["pair"] in ("both_high", "both_low", "apart")


def test_stoch_rsi_matches_the_chart_panel():
    import chart_indicators as ci

    f = _frame(_walk(300, seed=5)).iloc[:-1]
    a, b = stoch_rsi_frame(f), ci.stoch_rsi(f)
    assert np.allclose(a["k"].dropna(), b["k"].dropna()) and np.allclose(a["d"].dropna(), b["d"].dropna())


def test_short_history_says_so():
    assert _run("sonar.markers", _frame(_walk(40))).status == INSUFFICIENT
    assert _run("osc.stoch_rsi", _frame(_walk(20))).status == INSUFFICIENT


def test_offered_in_the_editor():
    import lattice_editor as le

    by_id = {s["id"]: s for s in le.catalogue()}
    assert "sonar.markers" in by_id and "osc.stoch_rsi" in by_id
    fields = {o["field"] for o in by_id["sonar.markers"]["operands"]}
    assert "yellow_cross_ago" in fields and "big_green_dot_ago" in fields


def test_snake_eyes_are_two_dots_close_together():
    from signal_library.signals_sonar import _pair

    dots = pd.Series([False, True, False, False, True, False, False, False, False, False, True])
    level = pd.Series([0.0] * 11)
    hits = _pair(dots, level, 4, None)
    assert hits.tolist()[4] and not hits.tolist()[1] and not hits.tolist()[10]    # 3 apart: yes; 6 apart: no
    assert not _pair(dots, level, 4, lambda x: x <= -53).any()                     # none beyond −53
    r = _run("sonar.markers", _frame(_walk(400, seed=7)), snake_gap=10)
    assert "snake_eyes_green_ago" in r.value and "snake_eyes_red_ago" in r.value
