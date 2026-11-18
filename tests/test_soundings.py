"""Soundings: moves are marked from later candles only, conditions come from fixed cuts, and the corrections."""

import numpy as np
import pandas as pd

import soundings as so


def _frame(closes, spread=1.0):
    idx = pd.date_range("2020-01-01", periods=len(closes), freq="D", tz="UTC")
    c = np.asarray(closes, float)
    return pd.DataFrame({"open": c, "high": c + spread, "low": c - spread, "close": c, "volume": 1.0}, index=idx)


def test_a_rise_needs_two_typical_moves_before_one_down():
    closes = [100.0] * 40 + [100, 101, 103, 106, 110, 112, 112, 112, 112] + [112] * 10
    mv = so.moves(_frame(closes), cut=pd.Timestamp("2030-01-01"))
    i = 40                                     # the close before the climb
    assert mv["rise"].iloc[i] == 1.0 and mv["fall"].iloc[i] == 0.0
    assert np.isnan(mv["rise"].iloc[-1])       # no complete window at the end


def test_nothing_after_the_cut_is_used():
    closes = [100.0] * 60
    mv = so.moves(_frame(closes), cut=pd.Timestamp("2020-02-15"))
    last = mv["rise"].dropna().index.max().tz_localize(None)
    assert last + pd.Timedelta(days=so.WINDOW) <= pd.Timestamp("2020-02-15")


def test_conditions_use_fixed_cuts_and_labels():
    idx = pd.date_range("2020-01-01", periods=4, freq="D", tz="UTC")
    table = pd.DataFrame({"rsi.level|rsi": [25, 50, 75, None], "trend.direction|": ["up", "down", "up", None]},
                         index=idx)
    c = so.conditions(table)
    assert list(c["RSI (14) under 30"].fillna(-1)) == [1, 0, 0, -1]
    assert list(c["RSI (14) 70 or more"].fillna(-1)) == [0, 0, 1, -1]
    assert list(c["Trend: up"].fillna(-1)) == [1, 0, 1, -1]
    assert so.family("RSI (14) under 30") == so.family("RSI (14) 70 or more")


def test_benjamini_hochberg():
    assert so.bh([0.001, 0.02, 0.5, 0.04], q=0.1) == [True, True, False, True]
    assert so.bh([0.5, 0.6]) == [False, False]


def test_every_reading_is_a_real_signal_field():
    import lattice_editor as le

    cat = {s["id"]: {o["field"] for o in s["operands"]} for s in le.catalogue()}
    for sig, field, _, _ in so.READINGS:
        sig = sig.partition(":")[0]          # tides.current:dollar is tides.current with a setting
        assert sig in cat, sig
        assert field in cat[sig] or field.replace(".0.", ".*.") in cat[sig] or field == "", (sig, field)


def test_tides_columns_read_the_saved_history():
    got = so.tides_columns(pd.DatetimeIndex(["2020-03-16", "2022-06-15"], tz="UTC"))
    assert got.loc["2020-03-16", "tides.tide|tide"] == "out"
    assert got.loc["2020-03-16", "tides.tide|sea"] == "storm"
    assert got.loc["2022-06-15", "tides.current:dollar|direction"] in ("rising", "flat", "falling")


def test_chart_builds_from_the_saved_grid():
    import soundings_view as v

    class S:
        class context:
            class theme:
                type = "light"

    report, grid = v.load(), v.load_grid()
    coin = grid["coins"]["BTC-USD"]
    for target in ("rise", "fall"):
        rows = v.chart_rows(report, target, True)
        fig, summary, base = v.build_figure(S, coin, rows, target, "2023-01-01", "2023-12-31")
        assert 0 < base < 1
        assert len(summary) == len([r for r in rows if v.fired(coin, r["condition"]) is not None])
    assert v.fired(coin, ["Tide: in"]).count("1") > 100
