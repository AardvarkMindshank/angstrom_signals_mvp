import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pandas_ta")  # compute_score imports it; regime itself does not need it

import backtest
from regime import CONFIRM, latest_regime, multipliers_for, regime_series
from scoring import compute_score


def frame(adx, close=100.0, sma50=90.0, sma200=80.0):
    n = len(adx)
    return pd.DataFrame(
        {"close": [close] * n, "adx": adx, "sma_50": [sma50] * n, "sma_200": [sma200] * n},
        index=pd.date_range("2024-01-01", periods=n),
    )


def test_states_follow_adx():
    assert latest_regime(frame([30.0] * 10))["state"] == "trending"
    assert latest_regime(frame([15.0] * 10))["state"] == "ranging"
    assert latest_regime(frame([22.0] * 10))["state"] == "transitional"


def test_direction():
    up = latest_regime(frame([30.0] * 10, close=100, sma50=90, sma200=80))
    down = latest_regime(frame([30.0] * 10, close=70, sma50=80, sma200=90))
    mixed = latest_regime(frame([30.0] * 10, close=100, sma50=110, sma200=80))
    assert up["label"] == "trending_up"
    assert down["label"] == "trending_down"
    assert mixed["direction"] == "mixed"


def test_no_adx_gives_no_regime():
    assert latest_regime(frame([float("nan")] * 10)) is None
    assert latest_regime(pd.DataFrame({"close": [1.0] * 10})) is None


def test_change_needs_confirmation_bars():
    adx = [30.0] * 8 + [15.0] * (CONFIRM - 1)
    assert regime_series(frame(adx))["state"].iloc[-1] == "trending"
    adx = [30.0] * 8 + [15.0] * CONFIRM
    assert regime_series(frame(adx))["state"].iloc[-1] == "ranging"


def test_single_blip_does_not_flip():
    adx = [30.0] * 8 + [15.0, 30.0, 30.0]
    assert set(regime_series(frame(adx))["state"]) == {"trending"}


def test_multipliers_favour_the_right_tools():
    trending, ranging = multipliers_for("trending"), multipliers_for("ranging")
    assert trending["macd"] > 1 > trending["rsi"]
    assert ranging["rsi"] > 1 > ranging["macd"]
    assert multipliers_for("transitional") == {}


def indicated(rsi, adx):
    """One indicated bar set where only RSI and ADX speak: RSI oversold."""
    row = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0,
           "rsi": rsi, "adx": adx, "sma_50": 100.0}
    return pd.DataFrame([row] * 30, index=pd.date_range("2024-01-01", periods=30))


def test_adaptive_changes_weights_only_when_asked():
    data = indicated(rsi=30.0, adx=15.0)  # ranging: RSI oversold is worth more
    fixed = compute_score(data)
    adapt = compute_score(data, adaptive=True)
    assert fixed["contributions"]["RSI"] == 8.0
    assert adapt["contributions"]["RSI"] == 12.0
    assert adapt["regime"]["state"] == "ranging"
    assert fixed["regime"]["state"] == "ranging"


def test_adaptive_trending_cuts_rsi():
    data = indicated(rsi=30.0, adx=35.0)
    assert compute_score(data, adaptive=True)["contributions"]["RSI"] == 4.0


def test_user_weight_of_zero_stays_off():
    data = indicated(rsi=30.0, adx=15.0)
    assert compute_score(data, weights={"rsi": 0}, adaptive=True)["contributions"]["RSI"] == 0.0


def test_compare_adaptive_reports_both_scores():
    rng = np.random.default_rng(1)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, 400)), index=pd.date_range("2023-01-01", periods=400))
    data = pd.DataFrame({"close": close})
    scores = pd.Series(rng.normal(50, 10, 200), index=close.index[200:])
    out = backtest.compare_adaptive(data, horizons=(1, 5), static_fn=lambda: scores, adaptive_fn=lambda: scores)
    assert set(out) == {1, 5}
    assert out[5]["change"] == 0.0
    assert "noise floor" in backtest.format_compare_adaptive({"X": out}, (1, 5))
