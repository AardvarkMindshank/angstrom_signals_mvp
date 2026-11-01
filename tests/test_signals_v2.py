"""Signals v2 engine. Indicator columns come from a simple fixture here (the engine only reads them);
test_signals_v2_integration.py runs the real pandas-ta indicators where that library is installed."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

import signals_v2 as v2


def fixture(n=320, seed=0, drift=0.0, volume=True, start="2025-01-01"):
    """OHLCV plus the indicator columns calculate_indicators provides, computed simply."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="D")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, 0.02, n))), index=idx)
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.01, n)))
    vol = pd.Series(rng.uniform(1e6, 3e6, n), index=idx) if volume else pd.Series(0.0, index=idx)
    f = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol})
    for length in (20, 50, 200):
        f[f"sma_{length}"] = close.rolling(length).mean()
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    f["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    d = close.diff()
    up, dn = d.clip(lower=0).ewm(alpha=1 / 14).mean(), (-d.clip(upper=0)).ewm(alpha=1 / 14).mean()
    f["rsi"] = 100 - 100 / (1 + up / dn)
    f["stoch_k"] = ((close - low.rolling(14).min()) / (high.rolling(14).max() - low.rolling(14).min()) * 100).rolling(3).mean()
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    f["MACD_12_26_9"], f["MACDs_12_26_9"], f["MACDh_12_26_9"] = macd, sig, macd - sig
    mid, sd = close.rolling(20).mean(), close.rolling(20).std()
    f["BBL_20_2.0_2.0"], f["BBM_20_2.0_2.0"], f["BBU_20_2.0_2.0"] = mid - 2 * sd, mid, mid + 2 * sd
    f["vol_sma_20"] = vol.rolling(20).mean()
    f["volume_ratio"] = vol / f["vol_sma_20"].replace(0, np.nan)
    obv = (np.sign(close.diff()).fillna(0) * vol).cumsum()
    f["obv"], f["obv_sma_20"] = obv, obv.rolling(20).mean()
    f["change_7d"] = close.pct_change(7) * 100
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    f["ichi_tenkan"], f["ichi_kijun"] = tenkan, kijun
    f["ichi_span_a"] = ((tenkan + kijun) / 2).shift(26)
    f["ichi_span_b"] = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    f["adx"] = 15 + 20 * np.abs(np.sin(np.arange(n) / 20))
    return f


LATE = datetime(2030, 1, 1, tzinfo=timezone.utc)        # every fixture bar is finished by then


def test_result_carries_version_and_fingerprint_and_no_single_score():
    out = v2.score(fixture(), "Stock", LATE)
    assert out["status"] == "ok" and out["version"] == v2.VERSION and out["fingerprint"] == v2.FINGERPRINT
    assert "score" not in out and "score" not in v2.flat_fields(out)
    assert set(out["clusters"]) == {"trend", "stretch", "flow"}


def test_fingerprint_follows_the_definitions(monkeypatch):
    import hashlib
    import json

    def fp(defs):
        return hashlib.sha256((v2.VERSION + json.dumps(defs, sort_keys=True)).encode()).hexdigest()[:12]

    assert fp(v2.DEFINITIONS) == v2.FINGERPRINT
    changed = {**v2.DEFINITIONS, "rsi_span": 31}
    assert fp(changed) != v2.FINGERPRINT


def test_every_value_is_bounded():
    for seed in range(5):
        out = v2.score(fixture(seed=seed, drift=0.004 * (seed - 2)), "Crypto", LATE)
        for c in out["clusters"].values():
            assert c["value"] is None or -1 <= c["value"] <= 1
            for comp in c["components"].values():
                assert comp["value"] is None or -1 <= comp["value"] <= 1
        for lens in out["lenses"].values():
            assert lens["value"] is None or -1 <= lens["value"] <= 1


def test_clusters_describe_and_lenses_carry_the_hypotheses():
    up = v2.score(fixture(seed=1, drift=0.01), "Stock", LATE)
    down = v2.score(fixture(seed=1, drift=-0.01), "Stock", LATE)
    assert up["clusters"]["trend"]["value"] > 0.3 > -0.3 > down["clusters"]["trend"]["value"]
    # clusters are descriptions with one sign convention: a steady rise is stretched UP
    assert up["clusters"]["stretch"]["value"] > 0 > down["clusters"]["stretch"]["value"]
    # the hypotheses live in the lenses: trend-following leans with it, mean-reversion against it
    assert up["lenses"]["trend_following"]["value"] > 0 > up["lenses"]["mean_reversion"]["value"]
    assert up["lenses"]["mean_reversion"]["value"] == pytest.approx(-up["clusters"]["stretch"]["value"])


def test_no_cliffs_a_tiny_price_change_moves_readings_a_tiny_amount():
    f = fixture(seed=3)
    base = v2.score(f, "Stock", LATE)
    g = f.copy()
    g.iloc[-1, g.columns.get_loc("close")] *= 1.0001          # one tick
    moved = v2.score(g, "Stock", LATE)
    for key in v2.CLUSTERS:
        assert abs(moved["clusters"][key]["value"] - base["clusters"][key]["value"]) < 0.01


def test_crossing_an_average_is_smooth():
    f = fixture(seed=4)
    row = f.index[-1]
    f.loc[row, "close"] = f.loc[row, "sma_50"] * 0.9999
    below = v2.score(f, "Stock", LATE)["clusters"]["trend"]["components"]["moving_averages"]["value"]
    f.loc[row, "close"] = f.loc[row, "sma_50"] * 1.0001
    above = v2.score(f, "Stock", LATE)["clusters"]["trend"]["components"]["moving_averages"]["value"]
    assert abs(above - below) < 0.01                        # v1 jumped 8 points (16 with the ADX vote)


def test_adx_has_no_direction_any_more():
    f = fixture(seed=5)
    a = v2.score(f, "Stock", LATE)
    f["adx"] = 45.0
    b = v2.score(f, "Stock", LATE)
    for key in v2.CLUSTERS:
        assert a["clusters"][key]["value"] == b["clusters"][key]["value"]
    assert b["context"]["trend_strength"]["label"] == "Strong"


def test_macd_counts_each_condition_once():
    every = [c for spec in v2.CLUSTERS.values() for c in spec["components"]]
    assert every.count("macd") == 1 and every.count("macd_acceleration") == 1
    f = fixture(seed=6)
    f["MACDs_12_26_9"] = f["MACDs_12_26_9"] + 1e6           # the signal line itself is never read directly
    a, b = v2.score(fixture(seed=6), "Stock", LATE), v2.score(f, "Stock", LATE)
    assert a["clusters"]["trend"]["value"] == b["clusters"]["trend"]["value"]


def test_missing_volume_is_missing_not_zero():
    out = v2.score(fixture(volume=False), "Crypto", LATE)
    flow = out["clusters"]["flow"]
    assert flow["value"] is None and flow["coverage"] == [0, 2]
    assert any("volume" in w.lower() for w in out["context"]["warnings"])
    assert out["lenses"]["trend_following"]["value"] == pytest.approx(out["clusters"]["trend"]["value"])


def test_short_history_uses_the_parts_it_has_and_says_so():
    out = v2.score(fixture(n=120), "Stock", LATE)
    trend = out["clusters"]["trend"]
    assert trend["value"] is not None
    assert any("200 days" in w for w in out["context"]["warnings"])


def test_unfinished_bar_is_never_scored():
    f = fixture(n=300, start="2026-01-01")
    last_day = f.index[-1]
    during = datetime(last_day.year, last_day.month, last_day.day, 12, 0, tzinfo=timezone.utc)
    crypto = v2.score(f, "Crypto", during)
    assert crypto["as_of"] == str(f.index[-2].date()) and crypto["unfinished_bar_skipped"]
    next_day = during.replace(hour=0) + pd.Timedelta(days=1)
    assert v2.score(f, "Crypto", next_day)["as_of"] == str(last_day.date())
    # US stocks: 15:00 New York is still trading, 17:00 is after the close
    ny_open = datetime(last_day.year, last_day.month, last_day.day, 19, 0, tzinfo=timezone.utc)   # 14:00/15:00 NY
    ny_closed = datetime(last_day.year, last_day.month, last_day.day, 23, 0, tzinfo=timezone.utc)  # 18:00/19:00 NY
    assert v2.score(f, "Stock", ny_open)["as_of"] == str(f.index[-2].date())
    assert v2.score(f, "Stock", ny_closed)["as_of"] == str(last_day.date())


def test_future_rows_never_change_a_past_result():
    f = fixture(n=320)
    cut = f.index[299]
    past = v2.score(f.loc[:cut], "Stock", LATE)
    g = f.copy()
    g.loc[g.index > cut, :] = g.loc[g.index > cut, :] * 3          # rewrite the future
    as_of_cut = v2.score(g.loc[:cut], "Stock", LATE)
    assert past == as_of_cut
    # and the percentile context only looks backwards
    pos = f.index.get_loc(cut)
    series = f["atr"] / f["close"]
    assert v2._percentile(series, pos) == v2._percentile(series.where(series.index <= cut, 999.0), pos)


def test_pullback_inside_an_uptrend_is_named():
    f = fixture(n=320, seed=2, drift=0.008)
    # rebuild the last 8 closes as a sharp drop, then recompute the short-term columns on the fixture
    rng = np.random.default_rng(9)
    close = f["close"].copy()
    for i in range(1, 9):
        close.iloc[-9 + i] = close.iloc[-10 + i] * (1 - 0.012 - rng.uniform(0, 0.003))
    g = fixture(n=320, seed=2, drift=0.008)
    g["close"] = close
    g["open"] = close.shift(1)
    g["high"], g["low"] = np.maximum(g["open"], close) * 1.005, np.minimum(g["open"], close) * 0.995
    d = close.diff()
    up, dn = d.clip(lower=0).ewm(alpha=1 / 14).mean(), (-d.clip(upper=0)).ewm(alpha=1 / 14).mean()
    g["rsi"] = 100 - 100 / (1 + up / dn)
    g["stoch_k"] = ((close - g["low"].rolling(14).min()) / (g["high"].rolling(14).max() - g["low"].rolling(14).min()) * 100).rolling(3).mean()
    mid, sd = close.rolling(20).mean(), close.rolling(20).std()
    g["BBL_20_2.0_2.0"], g["BBU_20_2.0_2.0"] = mid - 2 * sd, mid + 2 * sd
    g["change_7d"] = close.pct_change(7) * 100
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    g["MACD_12_26_9"], g["MACDh_12_26_9"] = macd, macd - macd.ewm(span=9, adjust=False).mean()
    out = v2.score(g, "Stock", LATE)
    assert out["clusters"]["trend"]["value"] > 0.3 and out["clusters"]["stretch"]["value"] < -0.3
    assert out["against_trend"] == "pullback" and "pullback" in out["summary"].lower()
    assert v2.score(fixture(seed=1, drift=0.01), "Stock", LATE)["against_trend"] is None


def test_validation_registry_only_validates_stock_volatility_size():
    validated = [k for k, v in v2.VALIDATION.items() if v["status"] != "unvalidated"]
    assert validated == ["volatility_stock"]
    out_s, out_c = v2.score(fixture(), "Stock", LATE), v2.score(fixture(), "Crypto", LATE)
    assert out_s["context"]["volatility"]["validation"] == "volatility_stock"
    assert out_c["context"]["volatility"]["validation"] == "volatility_crypto"


def test_not_enough_data():
    assert v2.score(pd.DataFrame(), "Stock", LATE)["status"] == "no_data"
    assert v2.score(fixture(n=10), "Stock", LATE)["status"] == "no_data"


def test_component_readings_are_plain_words():
    out = v2.score(fixture(), "Stock", LATE)
    for key in v2.COMPONENT_NAMES:
        text = v2.component_reading(key, out["readings"])
        assert isinstance(text, str) and text
