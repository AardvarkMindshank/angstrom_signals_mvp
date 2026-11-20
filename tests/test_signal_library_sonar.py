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


# ---- 🔆 Sonar dot build-up (osc.dot_pressure), 20 Nov 2026

def test_dot_pressure_never_looks_ahead():
    from signal_library.signals_oscillators import wavetrend
    from signal_library.signals_sonar import dot_pressure

    f = _frame(_walk(500, seed=11))
    w = wavetrend(f, 9, 12, 3)
    full = dot_pressure(w["wt1"], w["wt2"])
    for cut in (120, 260, 499):
        wc = wavetrend(f.iloc[:cut], 9, 12, 3)
        part = dot_pressure(wc["wt1"], wc["wt2"])
        pd.testing.assert_frame_equal(part, full.iloc[:cut])


def test_dot_pressure_by_hand():
    from signal_library.signals_sonar import dot_pressure

    w2 = pd.Series([40.0, 53.0, 60.0, 60.0, -60.0])
    w1 = pd.Series([60.0, 63.0, 63.0, 58.0, -63.0])
    p = dot_pressure(w1, w2)
    # candle 0: depth (40-30)/23, gap 20 > 15: closeness 0
    assert p["red"][0] == 0.0
    # candle 1: depth 1, gap 10 (narrowing from 20): 100 x 1/3
    assert p["red"][1] == round(100 * (1 - 10 / 15), 1)
    # candle 2: gap 3, narrowing: 100 x 0.8
    assert p["red"][2] == 80.0
    # candle 3: crossed (WT1 below WT2): the turn has happened, no pressure left
    assert p["red"][3] == 0.0
    # candle 4: deep oversold, gap 3 (WT2 - WT1) but not narrowing from -2: x 0.6
    assert p["green"][4] == round(100 * 0.8 * 0.6, 1)
    assert (p["green"][:4] == 0).all()


def test_signal_reads_the_build_up():
    f = _frame(_walk(400, seed=7))
    r = _run("osc.dot_pressure", f)
    assert r.status == OK
    v = r.value
    assert 0 <= v["red_pressure"] <= 100 and 0 <= v["green_pressure"] <= 100
    assert v["building"] in ("red", "green", "none")
    assert (v["building"] == "none") == (v["building_candles"] == 0)
    assert _run("osc.dot_pressure", _frame(_walk(20, seed=1))).status == INSUFFICIENT


def test_buildup_alphas_lead_and_trail():
    import lw_chart

    pressure = [0, 5, 20, 60, 95, 0, 0, 0, 0, 0]
    dots = [False] * 5 + [True] + [False] * 4
    a = lw_chart.buildup_alphas(pressure, dots)
    assert a[0] == 0 and a[1] == 0                      # below the floor: nothing
    assert 0 < a[2] < a[3] < a[4] <= 0.9                # stronger as it nears
    assert a[5] == 0                                    # the big dot itself draws it
    assert a[6] > a[7] > a[8] > 0 and a[9] == 0         # fades over three candles


def test_strip_draws_build_up_only_when_asked():
    import chart_indicators
    import lw_chart

    f = _frame(_walk(300, seed=5))
    df = f.join(chart_indicators.cipher_b(f))
    assert {"mc_press_r", "mc_press_g"} <= set(df.columns)
    ids = [s["id"] for s in lw_chart.cipher_series(df, 1)]
    assert "mc_build_r" not in ids
    ids = [s["id"] for s in lw_chart.cipher_series(df, 1, buildup=True)]
    assert ids.index("mc_build_r") < ids.index("mc_sell")        # under the big dots
