"""Indicators drawn on the chart only. They are not part of the scored indicators (scoring.calculate_indicators,
whose code is certified), so adding one here changes no score, signal or saved result."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(src: pd.Series, length: int = 14) -> pd.Series:
    """RSI with Wilder's smoothing (TradingView's ta.rsi)."""
    change = src.diff()
    gain = change.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = (-change.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    out = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    return out.where(loss != 0, 100.0).where(gain.notna())


def _stoch_of(series: pd.Series, stoch_length: int, k: int, d: int) -> pd.DataFrame:
    low, high = series.rolling(stoch_length).min(), series.rolling(stoch_length).max()
    raw = 100 * (series - low) / (high - low).replace(0, np.nan)
    k_line = raw.rolling(k).mean()
    return pd.DataFrame({"k": k_line, "d": k_line.rolling(d).mean()}, index=series.index)


def stoch_rsi(df: pd.DataFrame, rsi_length: int = 14, stoch_length: int = 14, k: int = 3, d: int = 3) -> pd.DataFrame:
    """Stoch RSI as TradingView draws it with RSI Source (O + H + L + C)/4: the RSI of OHLC4 (Wilder's smoothing),
    where it sits in its own range over the last stoch_length bars (0 to 100), smoothed into %K, and %D its average."""
    src = (df["open"] + df["high"] + df["low"] + df["close"]) / 4 if "open" in df.columns else df["close"]
    return _stoch_of(rsi(src, rsi_length), stoch_length, k, d)


# ------------------------------------------------------------------------------ Market Cipher B (VuManChu, free)

CIPHER = {   # the free VuManChu Cipher B defaults; every one can be changed to match Drew's paid Market Cipher B
    "wt_channel": 9, "wt_average": 12, "wt_signal": 3,
    "ob1": 53, "ob2": 60, "os1": -53, "os2": -60,
    "mf_period": 60, "mf_multiplier": 150.0, "mf_shift": 2.5,
    "rsi_length": 14,
    "stoch_length": 14, "stoch_rsi_length": 14, "stoch_k": 3, "stoch_d": 3,
}


def cipher_b(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """The Market Cipher B strip, worked out with the open-source VuManChu Cipher B formulas (signal_library has
    the same WaveTrend and money flow the Sets use):

    mc_wt1, mc_wt2   the light-blue and blue waves (WaveTrend WT1 and its signal line WT2)
    mc_vwap          the yellow "VWAP" area: WT1 - WT2
    mc_mf            money flow (the green and red area), and mc_mf_in: True when above zero
    mc_rsi           RSI 14 of the close (the magenta line)
    mc_sk, mc_sd     Stoch RSI %K and %D of the log close (VuManChu's setting); the green / red line is %K, green
                     while %K is at or above %D
    mc_cross         +1 where the light-blue wave crosses above the blue one (small green dot), -1 below (small red)
    mc_buy, mc_sell  a cross up while the blue wave is at or below -53 (big green dot: a strong possible entry), a
                     cross down at or above +53 (big red dot)
    """
    from signal_library.signals_oscillators import money_flow, wavetrend

    c = {**CIPHER, **(cfg or {})}
    wt = wavetrend(df, c["wt_channel"], c["wt_average"], c["wt_signal"])
    w1, w2 = wt["wt1"], wt["wt2"]
    mf = money_flow(df, c["mf_period"], c["mf_multiplier"], c["mf_shift"])
    st = _stoch_of(rsi(np.log(df["close"].where(df["close"] > 0)), c["stoch_rsi_length"]),
                   c["stoch_length"], c["stoch_k"], c["stoch_d"])
    up = (w1 > w2) & (w1.shift(1) <= w2.shift(1))
    down = (w1 < w2) & (w1.shift(1) >= w2.shift(1))
    cross = pd.Series(0, index=df.index).mask(up, 1).mask(down, -1)
    return pd.DataFrame({
        "mc_wt1": w1, "mc_wt2": w2, "mc_vwap": w1 - w2, "mc_mf": mf, "mc_mf_in": mf > 0,
        "mc_rsi": rsi(df["close"], c["rsi_length"]), "mc_sk": st["k"], "mc_sd": st["d"],
        "mc_cross": cross, "mc_buy": up & (w2 <= c["os1"]), "mc_sell": down & (w2 >= c["ob1"]),
    }, index=df.index)


def add_chart_only(df: pd.DataFrame) -> pd.DataFrame:
    """The chart frame with the chart-only columns added (Stoch RSI, Market Cipher B). Quiet on failure."""
    extra = {}
    try:
        sr = stoch_rsi(df)
        extra.update(stochrsi_k=sr["k"], stochrsi_d=sr["d"])
    except Exception:
        pass
    try:
        mc = cipher_b(df)
        extra.update({name: mc[name] for name in mc.columns})
    except Exception:
        pass
    return df.assign(**extra) if extra else df
