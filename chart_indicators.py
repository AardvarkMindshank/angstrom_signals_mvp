"""Indicators drawn on the chart only. They are not part of the scored indicators (scoring.calculate_indicators,
whose code is certified), so adding one here changes no score, signal or saved result."""

from __future__ import annotations

import numpy as np
import pandas as pd


def stoch_rsi(df: pd.DataFrame, rsi_length: int = 14, stoch_length: int = 14, k: int = 3, d: int = 3) -> pd.DataFrame:
    """Stoch RSI as TradingView draws it with RSI Source (O + H + L + C)/4: the RSI of OHLC4 (Wilder's smoothing),
    where it sits in its own range over the last stoch_length bars (0 to 100), smoothed into %K, and %D its average."""
    src = (df["open"] + df["high"] + df["low"] + df["close"]) / 4 if "open" in df.columns else df["close"]
    change = src.diff()
    gain = change.clip(lower=0).ewm(alpha=1 / rsi_length, adjust=False, min_periods=rsi_length).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=1 / rsi_length, adjust=False, min_periods=rsi_length).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.where(loss != 0, 100.0).where(gain.notna())
    low, high = rsi.rolling(stoch_length).min(), rsi.rolling(stoch_length).max()
    raw = 100 * (rsi - low) / (high - low).replace(0, np.nan)
    k_line = raw.rolling(k).mean()
    return pd.DataFrame({"k": k_line, "d": k_line.rolling(d).mean()}, index=df.index)
