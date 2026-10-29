import pandas as pd
import pytest

pytest.importorskip("pandas_ta")  # scoring imports it; the checks below use ready-made columns

import score_rules as sr
from scoring import _label_for, compute_score

NAMES = {
    "rsi": "RSI", "stochastic": "Stochastic", "sma": "Moving Averages", "adx": "ADX Trend",
    "macd": "MACD & Hist", "ichimoku": "Ichimoku Cloud", "bb": "Bollinger Bands",
    "volume": "Volume", "obv": "OBV", "performance": "Performance",
}


def bars(bull: bool) -> pd.DataFrame:
    """Thirty identical bars that push every indicator as far as it goes, up or down."""
    sign = 1 if bull else -1
    price = 100.0
    row = {
        "open": price - sign, "high": price + 1, "low": price - 1, "close": price, "volume": 1.0,
        "rsi": 30.0 if bull else 70.0,
        "stoch_k": 10.0 if bull else 90.0,
        "sma_20": price - 5 * sign, "sma_50": price - 5 * sign, "sma_200": price - 5 * sign,
        "adx": 30.0,
        "MACD_12_26_9": 2.0 * sign, "MACDs_12_26_9": 1.0 * sign, "MACDh_12_26_9": 1.0 * sign,
        "ichi_span_a": price - 10 * sign, "ichi_span_b": price - 12 * sign,
        "ichi_tenkan": price + sign, "ichi_kijun": price - sign,
        "BBU_20_2.0": price + (10 if not bull else 1) , "BBL_20_2.0": price - (1 if not bull else 10),
        "volume_ratio": 2.0,
        "obv": 10.0 * sign, "obv_sma_20": 5.0 * sign if bull else 5.0 * sign,
        "change_7d": 20.0 * sign,
    }
    if not bull:
        row["BBU_20_2.0"], row["BBL_20_2.0"] = price + 1, price - 10
        row["obv"], row["obv_sma_20"] = -10.0, -5.0
    else:
        row["BBU_20_2.0"], row["BBL_20_2.0"] = price + 10, price - 1
        row["obv"], row["obv_sma_20"] = 10.0, 5.0
    return pd.DataFrame([row] * 30, index=pd.date_range("2024-01-01", periods=30))


def test_every_indicators_maximum_matches_the_written_rules():
    up = compute_score(bars(True))["contributions"]
    down = compute_score(bars(False))["contributions"]
    for rule in sr.RULES:
        key = NAMES[rule["weight"]]
        assert up[key] == rule["max_points"], (key, up[key])
        assert down[key] == -rule["max_points"], (key, down[key])


def test_listed_points_never_exceed_the_stated_maximum():
    for rule in sr.RULES:
        assert max(abs(points) for _, points in rule["rows"]) <= rule["max_points"], rule["name"]


def test_label_bands_match():
    for low, label in sr.BANDS:
        assert _label_for(low) == label
        if low:
            assert _label_for(low - 0.1) != label


def test_weights_scale_the_rows_and_bad_values_fall_back():
    rows = sr.weighted_rows({"rsi": 2, "macd": "x"})
    rsi = rows[0]
    assert rsi["rows"][0] == ("Below 35 (oversold)", 16.0) and rsi["max_points"] == 16.0
    macd = [row for row in rows if row["name"] == "MACD"][0]
    assert macd["weight"] == 1.0
    assert sr.band_lines()[0] == "70 or more: Strongly positive reading"
    assert sr.band_lines()[-1] == "under 30: Strongly negative reading"
