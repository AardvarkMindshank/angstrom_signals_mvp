"""Oscillators in the Market Cipher style (signal_library/signals_oscillators.py), checked against the published
WaveTrend / VuManChu Cipher B formulas written out independently here."""

import numpy as np
import pandas as pd

from signal_library import DataContext, SignalRef, REGISTRY, engine, evaluate
from signal_library.core import INSUFFICIENT, OK


def _frame(close, freq="1D", open_=None, spread=0.01):
    close = np.asarray(close, float)
    n = len(close)
    df = pd.DataFrame({"open": open_ if open_ is not None else np.r_[close[0], close[:-1]],
                       "high": close * (1 + spread), "low": close * (1 - spread), "close": close,
                       "volume": np.full(n, 100.0)},
                      index=pd.date_range("2023-01-01", periods=n, freq=freq, tz="UTC"))
    df["forming"] = False
    df.iloc[-1, df.columns.get_loc("forming")] = True            # the newest candle is still forming
    return df


def _run(signal_id, frame, tf="1D", frames=None, **params):
    engine.clear_cache()
    loader = (lambda kind, asset, t: {"frame": frames[t], "session": None, "source": "t"}) if frames else \
        (lambda *a: {"frame": frame, "session": None, "source": "t"})
    ctx = DataContext("crypto", "bitcoin", candle_loader=loader)
    ref = SignalRef.make(REGISTRY.get(signal_id, 1), tf, **params)
    return evaluate([ref], ctx)[ref.instance_key]


def _walk(n=500, seed=4):
    rng = np.random.default_rng(seed)
    return 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))


def test_wavetrend_matches_the_published_formula():
    f = _frame(_walk())
    r = _run("osc.wavetrend", f)
    assert r.status == OK
    c = f.iloc[:-1]
    ap = (c["high"] + c["low"] + c["close"]) / 3
    esa = ap.ewm(span=9, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=9, adjust=False).mean()
    wt1 = ((ap - esa) / (0.015 * d)).ewm(span=12, adjust=False).mean()
    wt2 = wt1.rolling(3).mean()
    assert abs(r.value["wt1"] - wt1.iloc[-1]) < 1e-3 and abs(r.value["wt2"] - wt2.iloc[-1]) < 1e-3
    assert r.value["zone"] in ("overbought", "oversold", "neutral")


def test_wavetrend_turn_up_from_oversold():
    close = np.r_[np.linspace(200, 100, 120), [100.5, 102, 104], 0]          # a long fall, then a bounce
    r = _run("osc.wavetrend", _frame(close))
    found = False
    for cut in range(len(close) - 6, len(close)):
        res = _run("osc.wavetrend", _frame(np.r_[close[:cut], 0]))
        if res.status == OK and res.value["turned_up_from_oversold"]:
            found = True
            assert res.value["zone"] == "oversold" and res.value["cross"] == "up"
    assert found and r.status == OK


def test_money_flow_in_and_out():
    up_close = np.linspace(100, 130, 200)
    rising = _run("flow.money", _frame(np.r_[up_close, 0], open_=np.r_[up_close * 0.995, 0]))
    assert rising.status == OK and rising.value["direction"] == "in" and rising.value["value"] > 0
    falling = _run("flow.money", _frame(np.r_[up_close, 0], open_=np.r_[up_close * 1.005, 0]))
    assert falling.value["direction"] == "out"


def test_stochastic_on_ohlc4():
    f = _frame(_walk(200))
    r = _run("osc.stoch_ohlc4", f)
    c = f.iloc[:-1]
    src = (c["open"] + c["high"] + c["low"] + c["close"]) / 4
    raw = 100 * (src - c["low"].rolling(14).min()) / (c["high"].rolling(14).max() - c["low"].rolling(14).min())
    k = raw.rolling(3).mean()
    assert abs(r.value["k"] - k.iloc[-1]) < 0.01 and abs(r.value["d"] - k.rolling(3).mean().iloc[-1]) < 0.01


def test_divergence_counts_timeframes_and_leaves_out_what_it_cannot_read():
    walk = _walk(400, seed=9)
    frames = {"1D": _frame(walk), "12h": _frame(walk, "12h"), "4h": _frame(walk, "4h"), "1h": _frame(walk[:50], "1h")}
    r = _run("divergence.mtf", None, frames=frames)
    assert r.status == OK and r.value["timeframes_read"] == 3             # 1h has too few candles: not read
    assert 0 <= r.value["bullish_count"] <= 3 and "of 3 timeframes" in r.value["summary"]


def test_not_enough_history_says_so():
    assert _run("osc.wavetrend", _frame(_walk(30))).status == INSUFFICIENT


def test_every_new_signal_is_offered_with_its_settings():
    import lattice_editor as le

    by_id = {s["id"]: s for s in le.catalogue()}
    for sid in ("osc.wavetrend", "flow.money", "osc.stoch_ohlc4", "divergence.mtf"):
        assert sid in by_id and by_id[sid]["params"], sid
