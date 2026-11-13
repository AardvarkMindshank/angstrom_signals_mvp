"""🎛️ Stoch RSI on the chart, set up as TradingView's (K 3, D 3, RSI 14, Stochastic 14, source OHLC4)."""

import numpy as np
import pandas as pd

import chart_plan
import lw_chart
from chart_indicators import stoch_rsi


def _frame(n=200, seed=1):
    c = pd.Series(100 + np.cumsum(np.random.default_rng(seed).normal(0, 1, n)))
    return pd.DataFrame({"open": c.shift(1).fillna(100), "high": c + 1, "low": c - 1, "close": c})


def test_range_and_smoothing():
    df = _frame()
    r = stoch_rsi(df)
    k, d = r["k"].dropna(), r["d"].dropna()
    assert k.between(0, 100).all() and d.between(0, 100).all()
    assert k.index[0] == 14 + 14 - 1 + 3 - 1          # RSI warm-up, then the 14-bar range, then %K's 3
    assert np.isclose(r["d"].iloc[-1], r["k"].iloc[-3:].mean())


def test_uses_ohlc4_not_close():
    df = _frame()
    other = df.copy()
    other["open"] = other["open"] * 1.02
    assert not np.allclose(stoch_rsi(df)["k"].dropna(), stoch_rsi(other)["k"].dropna())


def test_on_the_chart_plan_and_panel():
    df = _frame()
    sr = stoch_rsi(df)
    df["stochrsi_k"], df["stochrsi_d"] = sr["k"], sr["d"]
    df["volume"] = 1.0
    assert "stochrsi" in chart_plan.available(df.columns)
    layout = chart_plan.plan(["stochrsi"], df.columns)
    assert "stochrsi" in layout["panels"]
    over = chart_plan.plan(["stochrsi"], df.columns, overlay_curves=True)
    assert "stochrsi" in over["secondary"] and "stochrsi" not in over["panels"]
    assert "stochrsi" in lw_chart.FIXED_0_100 and "stochrsi" in lw_chart.PANEL_TITLES
