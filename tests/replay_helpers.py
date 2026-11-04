"""Small pure-pandas stand-in for scoring.calculate_indicators, so replay tests run without pandas_ta.
Every column is causal (uses only rows up to its own). CI certifies with the real indicators."""

import numpy as np
import pandas as pd


def simple_indicators(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw[["open", "high", "low", "close", "volume"]].astype(float).copy()
    s = df["close"]
    df["sma_20"], df["sma_50"], df["sma_200"] = s.rolling(20).mean(), s.rolling(50).mean(), s.rolling(200).mean()
    delta = s.diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    macd = s.ewm(span=12).mean() - s.ewm(span=26).mean()
    df["MACD_12_26_9"], df["MACDs_12_26_9"] = macd, macd.ewm(span=9).mean()
    df["MACDh_12_26_9"] = macd - df["MACDs_12_26_9"]
    true_range = pd.concat([df["high"] - df["low"], (df["high"] - s.shift()).abs(), (df["low"] - s.shift()).abs()],
                           axis=1).max(axis=1)
    df["atr"] = true_range.rolling(14).mean()
    move = s.diff(14).abs()
    path = s.diff().abs().rolling(14).sum()
    df["adx"] = (move / path.replace(0, np.nan) * 60).rolling(5).mean()
    mid = s.rolling(20).mean()
    sd = s.rolling(20).std()
    df["BBM_20_2.0"], df["BBU_20_2.0"], df["BBL_20_2.0"] = mid, mid + 2 * sd, mid - 2 * sd
    df["vol_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["vol_sma_20"]
    df["obv"] = (np.sign(s.diff().fillna(0)) * df["volume"]).cumsum()
    return df


def full_indicators(raw: pd.DataFrame) -> pd.DataFrame:
    """simple_indicators plus the remaining columns signals_v2 reads (Stochastic, OBV average, 7-candle change,
    Ichimoku), all causal."""
    df = simple_indicators(raw)
    s = df["close"]
    low14, high14 = df["low"].rolling(14).min(), df["high"].rolling(14).max()
    df["stoch_k"] = ((s - low14) / (high14 - low14) * 100).rolling(3).mean()
    df["obv_sma_20"] = df["obv"].rolling(20).mean()
    df["change_7d"] = s.pct_change(7) * 100
    tenkan = (df["high"].rolling(9).max() + df["low"].rolling(9).min()) / 2
    kijun = (df["high"].rolling(26).max() + df["low"].rolling(26).min()) / 2
    df["ichi_tenkan"], df["ichi_kijun"] = tenkan, kijun
    df["ichi_span_a"] = ((tenkan + kijun) / 2).shift(26)
    df["ichi_span_b"] = ((df["high"].rolling(52).max() + df["low"].rolling(52).min()) / 2).shift(26)
    return df
