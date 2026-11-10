"""Candle-level building blocks (signal_library/signals_candles.py), checked against the Pine formulas they mirror
(Drew's BTC Hybrid script: ta.ema, ta.sma, ta.rma, retest = low <= EMA and close > EMA, early = close[1] < EMA and close >
EMA, body > ta.sma(body, 10), atr > ta.sma(atr, 20))."""

import numpy as np
import pandas as pd

from signal_library import DataContext, SignalRef, REGISTRY, engine, evaluate
from signal_library.core import INSUFFICIENT, OK


def setup_function(_):
    engine.clear_cache()


def _frame(close, high=None, low=None, open_=None, n_extra_forming=True):
    close = np.asarray(close, float)
    n = len(close)
    df = pd.DataFrame({"open": open_ if open_ is not None else np.r_[close[0], close[:-1]],
                       "high": high if high is not None else close * 1.01,
                       "low": low if low is not None else close * 0.99, "close": close,
                       "volume": np.full(n, 100.0)},
                      index=pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC"))
    df["forming"] = False
    if n_extra_forming:                         # the newest candle is still forming and must be ignored
        df.iloc[-1, df.columns.get_loc("forming")] = True
    return df


def _run(signal_id, frame, tf="1D", **params):
    engine.clear_cache()                        # each call reads its own frame
    ctx = DataContext("crypto", "bitcoin", candle_loader=lambda *a: {"frame": frame, "session": None, "source": "t"})
    ref = SignalRef.make(REGISTRY.get(signal_id, 1), tf, **params)
    return evaluate([ref], ctx)[ref.instance_key]


def _walk(n=400, seed=3):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))


def test_ema_matches_the_pine_formula():
    close = _walk()
    r = _run("ma.line", _frame(close), kind="EMA", length=20)
    assert r.status == OK
    closed = pd.Series(close[:-1])
    expected = closed.ewm(alpha=2 / 21, adjust=False).mean().iloc[-1]
    assert abs(r.value["average"] - expected) < 1e-6 * expected
    sma = _run("ma.line", _frame(close), kind="SMA", length=50)
    assert abs(sma.value["average"] - closed.tail(50).mean()) < 1e-6 * closed.tail(50).mean()


def test_retest_and_cross():
    close = np.r_[np.linspace(100, 120, 200), 0]                 # last row is forming
    frame = _frame(close)
    # The last closed candle dips to the EMA and closes above it: a retest from above.
    ema = pd.Series(close[:-1]).ewm(span=20, adjust=False).mean().iloc[-1]
    frame.iloc[-2, frame.columns.get_loc("low")] = ema - 0.1
    frame.iloc[-2, frame.columns.get_loc("close")] = ema + 0.5
    r = _run("ma.line", frame, kind="EMA", length=20)
    assert r.value["retest_from_above"] is True and r.value["position"] == "above"
    assert r.value["crossed_up"] is False and r.value["retest_from_below"] is False
    # Previous close under the average, this one above: crossed up.
    frame2 = _frame(close)
    frame2.iloc[-3, frame2.columns.get_loc("close")] = 90
    r2 = _run("ma.line", frame2, kind="EMA", length=20)
    assert r2.value["crossed_up"] is True


def test_two_averages_order_and_cross():
    up = _run("ma.pair", _frame(np.r_[np.linspace(100, 150, 300), 0]), kind="EMA", fast=20, slow=50)
    assert up.value["order"] == "fast_above" and up.value["gap_pct"] > 0
    down = _run("ma.pair", _frame(np.r_[np.linspace(150, 100, 300), 0]), kind="EMA", fast=20, slow=50)
    assert down.value["order"] == "fast_below"
    bad = _run("ma.pair", _frame(np.r_[np.linspace(100, 150, 300), 0]), kind="EMA", fast=50, slow=20)
    assert bad.status == INSUFFICIENT


def test_candle_shape():
    close = np.r_[np.full(30, 100.0), 105.0, 0]
    open_ = np.r_[np.full(30, 99.5), 100.0, 0]
    r = _run("candle.shape", _frame(close, open_=open_, high=close + 1, low=open_ - 1), average=10)
    v = r.value
    assert v["colour"] == "green" and v["close_vs_previous"] == "higher"
    # Body 5 against the average of the last 10 bodies (nine of 0.5 and this 5) = 5 / 0.95
    assert abs(v["body_vs_average"] - 5 / 0.95) < 1e-6


def test_volatility_expanding():
    calm = np.r_[100 + np.sin(np.arange(200)) * 0.2, 0]
    spread = np.full(len(calm), 0.3)
    spread[-8:-1] = 4.0                                            # the last candles swing much wider
    quiet = _run("volatility.atr_trend", _frame(calm, high=calm + 0.3, low=calm - 0.3))
    assert quiet.status == OK and abs(quiet.value["ratio"] - 1) < 0.05
    w = _run("volatility.atr_trend", _frame(calm, high=calm + spread, low=calm - spread), length=14, average=20)
    assert w.status == OK and w.value["expanding"] is True and w.value["ratio"] > 1


def test_not_enough_history_says_so():
    r = _run("ma.line", _frame(_walk(30)), kind="EMA", length=20)       # an EMA needs about 3 lengths
    assert r.status == INSUFFICIENT


def test_every_new_signal_is_offered_with_its_settings():
    import lattice_editor as le

    by_id = {s["id"]: s for s in le.catalogue()}
    for sid in ("ma.line", "ma.pair", "candle.shape", "volatility.atr_trend"):
        assert sid in by_id and by_id[sid]["params"], sid
    assert by_id["ma.line"]["params"]["kind"]["choices"] == ["EMA", "SMA"]
