"""
Multi-factor technical score for the signals dashboard.

The baseline is 50. Each factor adds or subtracts points, then the result
is clamped to 0-100. A weight scales that factor (0 turns it off).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta

from regime import latest_regime, multipliers_for


DEFAULT_WEIGHTS = {
    "rsi": 1.0,
    "stochastic": 1.0,
    "sma": 1.0,
    "adx": 1.0,
    "macd": 1.0,
    "ichimoku": 1.0,
    "bb": 1.0,
    "volume": 1.0,
    "obv": 1.0,
    "performance": 1.0,
}


def find_column(df: pd.DataFrame, prefix: str) -> str | None:
    """First column whose name starts with prefix, or None."""
    for column in df.columns:
        if str(column).startswith(prefix):
            return column
    return None


def _scalar(value):
    if isinstance(value, pd.Series):
        if value.empty:
            return None
        value = value.iloc[-1]
    try:
        if pd.isna(value):
            return None
    except TypeError:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators. One failed indicator does not drop the rest."""
    if df.empty or len(df) < 15:
        return df

    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"] if "volume" in df.columns else pd.Series(0.0, index=df.index)

    def _keep(label, fn):
        try:
            fn()
        except Exception as exc:
            errors = df.attrs.setdefault("indicator_errors", [])
            errors.append(f"{label}: {exc}")

    def rsi():
        values = ta.rsi(close, length=14)
        if values is not None:
            df["rsi"] = values

    def stochastic():
        stoch = ta.stoch(high, low, close, k=14, d=3)
        if stoch is not None and not stoch.empty:
            df["stoch_k"] = stoch.iloc[:, 0]

    def moving_averages():
        for length in (20, 50, 200):
            values = ta.sma(close, length=length)
            if values is not None:
                df[f"sma_{length}"] = values

    def adx():
        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is None or adx_df.empty:
            return
        column = find_column(adx_df, "ADX_")
        if column:
            df["adx"] = adx_df[column]

    def macd():
        macd_df = ta.macd(close)
        if macd_df is None or macd_df.empty:
            return
        for column in macd_df.columns:
            df[column] = macd_df[column]

    def volatility():
        atr = ta.atr(high, low, close, length=14)
        if atr is not None:
            df["atr"] = atr
        bands = ta.bbands(close, length=20, std=2)
        if bands is None or bands.empty:
            return
        for column in bands.columns:
            df[column] = bands[column]

    def volume_and_obv():
        df["vol_sma_20"] = ta.sma(volume, length=20)
        df["volume_ratio"] = volume / df["vol_sma_20"].replace(0, np.nan)
        obv = ta.obv(close, volume)
        if obv is None:
            return
        df["obv"] = obv
        df["obv_sma_20"] = ta.sma(obv, length=20)

    def performance():
        df["change_1d"] = close.pct_change(1) * 100
        df["change_7d"] = close.pct_change(7) * 100
        df["change_30d"] = close.pct_change(30) * 100

    def ichimoku():
        # Span A/B are shifted forward 26 bars so the latest row is today's cloud,
        # not the cloud projected 26 days ahead.
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
        df["ichi_tenkan"] = tenkan
        df["ichi_kijun"] = kijun
        df["ichi_span_a"] = ((tenkan + kijun) / 2).shift(26)
        df["ichi_span_b"] = (
            (high.rolling(52).max() + low.rolling(52).min()) / 2
        ).shift(26)

    for label, fn in (
        ("RSI", rsi),
        ("Stochastic", stochastic),
        ("Moving averages", moving_averages),
        ("ADX", adx),
        ("MACD", macd),
        ("Bollinger", volatility),
        ("Volume", volume_and_obv),
        ("Performance", performance),
        ("Ichimoku", ichimoku),
    ):
        _keep(label, fn)

    return df


def _empty_result(reason: str) -> dict:
    return {
        "score": 50.0,
        "label": "Insufficient data",
        "reasons": [reason],
        "confluence": 0,
        "latest_price": None,
        "rsi": None,
        "change_1d": None,
        "change_7d": None,
        "change_30d": None,
        "atr_pct": None,
        "volume_ratio": None,
        "bb_position": None,
        "adx": None,
        "contributions": {},
        "regime": None,
    }


def _label_for(score: float) -> str:
    if score >= 70:
        return "Strongly positive reading"
    if score >= 60:
        return "Positive reading"
    if score >= 53:
        return "Slightly positive"
    if score >= 47:
        return "Mixed"
    if score >= 40:
        return "Slightly negative"
    if score >= 30:
        return "Negative reading"
    return "Strongly negative reading"


def compute_score(df: pd.DataFrame, weights: dict | None = None, adaptive: bool = False) -> dict:
    """Score the latest bar from 0 to 100. Higher means a more bullish setup.

    adaptive=True also scales each weight by the market regime (trending or ranging).
    The regime is reported either way.
    """
    merged = dict(DEFAULT_WEIGHTS)
    if weights:
        merged.update(weights)

    if df is None or df.empty or len(df) < 15 or "close" not in df.columns:
        return _empty_result("Not enough history")

    latest = df.iloc[-1]
    close = _scalar(latest.get("close"))
    if close is None:
        return _empty_result("Missing close price")

    regime = latest_regime(df)
    if adaptive and regime:
        for name, factor in multipliers_for(regime["state"]).items():
            try:
                merged[name] = float(merged.get(name, 1.0) or 0) * factor
            except (TypeError, ValueError):
                pass

    score = 50.0
    reasons = []
    contributions = {
        "RSI": 0.0,
        "Stochastic": 0.0,
        "Moving Averages": 0.0,
        "ADX Trend": 0.0,
        "MACD & Hist": 0.0,
        "Ichimoku Cloud": 0.0,
        "Bollinger Bands": 0.0,
        "Volume": 0.0,
        "OBV": 0.0,
        "Performance": 0.0,
    }

    def weight(name: str) -> float:
        try:
            return float(merged.get(name, 1.0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def add(factor: str, points: float, reason: str | None):
        nonlocal score
        if points:
            score += points
            contributions[factor] += points
        if reason:
            reasons.append(reason)

    w_rsi = weight("rsi")
    rsi = _scalar(latest.get("rsi"))
    if rsi is not None and w_rsi:
        if rsi < 35:
            points, reason = 8 * w_rsi, f"RSI oversold ({rsi:.1f})"
        elif rsi < 45:
            points, reason = 4 * w_rsi, f"RSI leaning oversold ({rsi:.1f})"
        elif rsi > 65:
            points, reason = -8 * w_rsi, f"RSI overbought ({rsi:.1f})"
        elif rsi > 55:
            points, reason = -4 * w_rsi, f"RSI elevated ({rsi:.1f})"
        else:
            points, reason = 0.0, f"RSI neutral ({rsi:.1f})"
        add("RSI", points, reason)

    w_stoch = weight("stochastic")
    stoch_k = _scalar(latest.get("stoch_k"))
    if stoch_k is not None and w_stoch:
        if stoch_k < 20:
            points, reason = 5 * w_stoch, f"Stochastic oversold ({stoch_k:.1f})"
        elif stoch_k > 80:
            points, reason = -5 * w_stoch, f"Stochastic overbought ({stoch_k:.1f})"
        else:
            points, reason = 0.0, f"Stochastic neutral ({stoch_k:.1f})"
        add("Stochastic", points, reason)

    w_sma = weight("sma")
    sma_points = 0.0
    for length, each in ((20, 4), (50, 4), (200, 4)):
        sma = _scalar(latest.get(f"sma_{length}"))
        if sma is None or not w_sma:
            continue
        if close > sma:
            sma_points += each * w_sma
            reasons.append(f"Price above SMA {length}")
        else:
            sma_points -= each * w_sma
            reasons.append(f"Price below SMA {length}")
    contributions["Moving Averages"] = sma_points
    score += sma_points

    w_adx = weight("adx")
    adx = _scalar(latest.get("adx"))
    sma50 = _scalar(latest.get("sma_50"))
    if adx is not None and w_adx:
        if adx >= 25 and sma50 is not None:
            if close > sma50:
                points, reason = 4 * w_adx, f"Strong uptrend (ADX {adx:.1f})"
            else:
                points, reason = -4 * w_adx, f"Strong downtrend (ADX {adx:.1f})"
        elif adx < 20:
            points, reason = 0.0, f"Weak trend (ADX {adx:.1f})"
        else:
            points, reason = 0.0, f"Developing trend (ADX {adx:.1f})"
        add("ADX Trend", points, reason)

    w_macd = weight("macd")
    macd_line = _scalar(latest.get(find_column(df, "MACD_"))) if find_column(df, "MACD_") else None
    macd_signal = _scalar(latest.get(find_column(df, "MACDs_"))) if find_column(df, "MACDs_") else None
    macd_hist = _scalar(latest.get(find_column(df, "MACDh_"))) if find_column(df, "MACDh_") else None
    if w_macd and macd_line is not None and macd_signal is not None:
        # Ignore gaps that are only floating-point noise on a settled trend.
        tolerance = max(1e-8, abs(close) * 1e-5)
        macd_points = 0.0
        if abs(macd_line) > tolerance:
            if macd_line > 0:
                macd_points += 4 * w_macd
                reasons.append("MACD above zero")
            else:
                macd_points -= 4 * w_macd
                reasons.append("MACD below zero")
        gap = macd_line - macd_signal
        if abs(gap) > tolerance:
            if gap > 0:
                macd_points += 3 * w_macd
                reasons.append("MACD above signal")
            else:
                macd_points -= 3 * w_macd
                reasons.append("MACD below signal")
        if macd_hist is not None and abs(macd_hist) > tolerance:
            if macd_hist > 0:
                macd_points += 2 * w_macd
                reasons.append("MACD histogram positive")
            else:
                macd_points -= 2 * w_macd
                reasons.append("MACD histogram negative")
        contributions["MACD & Hist"] = macd_points
        score += macd_points

    w_ichi = weight("ichimoku")
    span_a = _scalar(latest.get("ichi_span_a"))
    span_b = _scalar(latest.get("ichi_span_b"))
    tenkan = _scalar(latest.get("ichi_tenkan"))
    kijun = _scalar(latest.get("ichi_kijun"))
    if w_ichi and span_a is not None and span_b is not None:
        cloud_top = max(span_a, span_b)
        cloud_bottom = min(span_a, span_b)
        ichi_points = 0.0
        if close > cloud_top:
            ichi_points += 5 * w_ichi
            reasons.append("Price above the Ichimoku cloud")
        elif close < cloud_bottom:
            ichi_points -= 5 * w_ichi
            reasons.append("Price below the Ichimoku cloud")
        else:
            reasons.append("Price inside the Ichimoku cloud")
        if tenkan is not None and kijun is not None and tenkan != kijun:
            if tenkan > kijun:
                ichi_points += 3 * w_ichi
                reasons.append("Tenkan above Kijun")
            else:
                ichi_points -= 3 * w_ichi
                reasons.append("Tenkan below Kijun")
        contributions["Ichimoku Cloud"] = ichi_points
        score += ichi_points

    bb_position = None
    w_bb = weight("bb")
    upper_name = find_column(df, "BBU_")
    lower_name = find_column(df, "BBL_")
    upper = _scalar(latest.get(upper_name)) if upper_name else None
    lower = _scalar(latest.get(lower_name)) if lower_name else None
    if w_bb and upper is not None and lower is not None and (upper - lower) > 0:
        bb_position = (close - lower) / (upper - lower)
        if bb_position < 0.2:
            points, reason = 4 * w_bb, "Near lower Bollinger Band"
        elif bb_position > 0.8:
            points, reason = -4 * w_bb, "Near upper Bollinger Band"
        else:
            points, reason = 0.0, "Inside Bollinger Bands"
        add("Bollinger Bands", points, reason)

    w_vol = weight("volume")
    volume_ratio = _scalar(latest.get("volume_ratio"))
    open_price = _scalar(latest.get("open"))
    if w_vol and volume_ratio is not None and open_price is not None and volume_ratio >= 1.3:
        if close > open_price:
            points, reason = 3 * w_vol, f"High volume on an up bar ({volume_ratio:.1f}x)"
        elif close < open_price:
            points, reason = -3 * w_vol, f"High volume on a down bar ({volume_ratio:.1f}x)"
        else:
            points, reason = 0.0, None
        add("Volume", points, reason)

    w_obv = weight("obv")
    obv = _scalar(latest.get("obv"))
    obv_sma = _scalar(latest.get("obv_sma_20"))
    if w_obv and obv is not None and obv_sma is not None and obv != obv_sma:
        if obv > obv_sma:
            points, reason = 3 * w_obv, "OBV above its average"
        else:
            points, reason = -3 * w_obv, "OBV below its average"
        add("OBV", points, reason)

    w_perf = weight("performance")
    change_1d = _scalar(latest.get("change_1d"))
    change_7d = _scalar(latest.get("change_7d"))
    change_30d = _scalar(latest.get("change_30d"))
    if w_perf and change_7d is not None and change_7d != 0:
        capped = max(-4.0, min(4.0, change_7d * 0.4))
        direction = "Positive" if change_7d > 0 else "Negative"
        sign = "+" if change_7d > 0 else ""
        add("Performance", capped * w_perf, f"{direction} 7-day move ({sign}{change_7d:.1f}%)")

    score = max(0.0, min(100.0, score))
    bullish = sum(1 for points in contributions.values() if points > 0)
    bearish = sum(1 for points in contributions.values() if points < 0)

    atr = _scalar(latest.get("atr"))
    atr_pct = (atr / close * 100) if atr and close else None

    contributions = {name: round(points, 1) for name, points in contributions.items()}

    return {
        "score": round(score, 1),
        "label": _label_for(score),
        "reasons": reasons,
        "confluence": int(bullish - bearish),
        "latest_price": round(close, 4) if close < 1 else round(close, 2),
        "rsi": round(rsi, 1) if rsi is not None else None,
        "change_1d": round(change_1d, 1) if change_1d is not None else None,
        "change_7d": round(change_7d, 1) if change_7d is not None else None,
        "change_30d": round(change_30d, 1) if change_30d is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "bb_position": round(bb_position, 2) if bb_position is not None else None,
        "adx": round(adx, 1) if adx is not None else None,
        "contributions": contributions,
        "regime": regime,
    }
