"""
Enhanced scoring logic for the Signals Dashboard.
Supports dynamic indicator weighting for custom balance.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add a richer set of technical indicators."""
    if df.empty or len(df) < 30:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df.get("volume", pd.Series(0, index=df.index))

    # Momentum
    df["rsi"] = ta.rsi(close, length=14)
    df["stoch_k"] = ta.stoch(high, low, close, k=14, d=3)["STOCHk_14_3_3"]
    df["stoch_d"] = ta.stoch(high, low, close, k=14, d=3)["STOCHd_14_3_3"]

    # Trend
    df["sma_20"] = ta.sma(close, length=20)
    df["sma_50"] = ta.sma(close, length=50)
    df["sma_200"] = ta.sma(close, length=200)
    df["ema_12"] = ta.ema(close, length=12)
    df["ema_26"] = ta.ema(close, length=26)

    # Trend strength — try pandas_ta first, fall back to a simple version
    try:
        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None and not adx_df.empty:
            df = pd.concat([df, adx_df], axis=1)
    except Exception:
        pass

    # Simple fallback ADX-like strength (average true range relative to price)
    if "atr" in df.columns:
        df["adx_fallback"] = (df["atr"] / close * 100).rolling(14).mean()

    # MACD
    macd = ta.macd(close)
    if macd is not None:
        df = pd.concat([df, macd], axis=1)

    # Volatility
    df["atr"] = ta.atr(high, low, close, length=14)
    bb = ta.bbands(close, length=20, std=2)
    if bb is not None:
        df = pd.concat([df, bb], axis=1)

    # Volume
    df["vol_sma_20"] = ta.sma(volume, length=20)
    df["volume_ratio"] = volume / df["vol_sma_20"].replace(0, np.nan)

    # Recent performance
    df["change_7d"] = close.pct_change(7) * 100
    df["change_30d"] = close.pct_change(30) * 100

    return df


def compute_score(df: pd.DataFrame, weights: dict = None) -> dict:
    """
    Multi-factor 0-100 score with customizable indicator weights.
    Higher = more bullish.
    """
    if weights is None:
        weights = {
            "rsi": 1.0,
            "stochastic": 1.0,
            "sma": 1.0,
            "adx": 1.0,
            "macd": 1.0,
            "bb": 1.0,
            "volume": 1.0,
            "performance": 1.0,
        }

    if df.empty or len(df) < 30:
        return {
            "score": 50,
            "label": "Insufficient data",
            "reasons": ["Not enough history"],
            "confluence": 0,
            "latest_price": None,
            "rsi": None,
            "change_7d": None,
            "change_30d": None,
            "atr_pct": None,
            "volume_ratio": None,
            "bb_position": None,
            "adx": None,
        }

    latest = df.iloc[-1]
    score = 50.0
    reasons = []
    w_rsi = weights.get("rsi", 1.0)
    w_stoch = weights.get("stochastic", 1.0)
    w_sma = weights.get("sma", 1.0)
    w_adx = weights.get("adx", 1.0)
    w_macd = weights.get("macd", 1.0)
    w_bb = weights.get("bb", 1.0)
    w_vol = weights.get("volume", 1.0)
    w_perf = weights.get("performance", 1.0)

    close = latest["close"]

    # --- RSI ---
    rsi = latest.get("rsi")
    if pd.notna(rsi):
        if rsi < 30:
            score += 12 * w_rsi
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi < 40:
            score += 5 * w_rsi
            reasons.append(f"RSI approaching oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 12 * w_rsi
            reasons.append(f"RSI overbought ({rsi:.1f})")
        elif rsi > 60:
            score -= 5 * w_rsi
            reasons.append(f"RSI elevated ({rsi:.1f})")
        else:
            reasons.append(f"RSI neutral ({rsi:.1f})")

    # --- Stochastic ---
    stoch_k = latest.get("stoch_k")
    if pd.notna(stoch_k):
        if stoch_k < 20:
            score += 6 * w_stoch
            reasons.append(f"Stochastic oversold ({stoch_k:.1f})")
        elif stoch_k > 80:
            score -= 6 * w_stoch
            reasons.append(f"Stochastic overbought ({stoch_k:.1f})")

    # --- Price vs Moving Averages ---
    sma20 = latest.get("sma_20")
    sma50 = latest.get("sma_50")
    sma200 = latest.get("sma_200")
    if pd.notna(sma20):
        if close > sma20:
            score += 8 * w_sma
            reasons.append("Price above SMA 20")
        else:
            score -= 8 * w_sma
            reasons.append("Price below SMA 20")
    if pd.notna(sma50):
        if close > sma50:
            score += 7 * w_sma
            reasons.append("Price above SMA 50")
        else:
            score -= 7 * w_sma
            reasons.append("Price below SMA 50")
    if pd.notna(sma200):
        if close > sma200:
            score += 6 * w_sma
            reasons.append("Price above SMA 200 (long-term uptrend)")
        else:
            score -= 6 * w_sma
            reasons.append("Price below SMA 200 (long-term downtrend)")

    # --- ADX trend strength ---
    adx_val = latest.get("ADX_14")
    if not pd.notna(adx_val):
        adx_val = latest.get("adx_fallback")
    if pd.notna(adx_val):
        if adx_val > 25:
            reasons.append(f"Strong trend (ADX {adx_val:.1f})")
            if score > 55:
                score += 4 * w_adx
            elif score < 45:
                score -= 4 * w_adx
        elif adx_val < 20:
            reasons.append(f"Weak/ranging trend (ADX {adx_val:.1f})")
    else:
        adx_val = None

    # --- MACD ---
    if "MACD_12_26_9" in df.columns and pd.notna(latest.get("MACD_12_26_9")):
        macd_line = latest["MACD_12_26_9"]
        signal = latest.get("MACDs_12_26_9")
        hist = latest.get("MACDh_12_26_9")
        if pd.notna(signal) and macd_line > signal:
            score += 6 * w_macd
            reasons.append("MACD above signal")
        elif pd.notna(signal):
            score -= 6 * w_macd
            reasons.append("MACD below signal")
        if pd.notna(hist) and hist > 0:
            score += 3 * w_macd
            reasons.append("MACD histogram positive")
        elif pd.notna(hist):
            score -= 3 * w_macd

    # --- Bollinger Bands position ---
    bb_upper = latest.get("BBU_20_2.0")
    bb_lower = latest.get("BBL_20_2.0")
    bb_position = None
    if pd.notna(bb_upper) and pd.notna(bb_lower) and (bb_upper - bb_lower) > 0:
        bb_position = (close - bb_lower) / (bb_upper - bb_lower)
        if bb_position < 0.2:
            score += 7 * w_bb
            reasons.append("Near lower Bollinger Band")
        elif bb_position > 0.8:
            score -= 7 * w_bb
            reasons.append("Near upper Bollinger Band")

    # --- Volume confirmation ---
    vol_ratio = latest.get("volume_ratio")
    if pd.notna(vol_ratio) and vol_ratio > 1.3:
        if score > 55:
            score += 4 * w_vol
            reasons.append(f"Elevated volume ({vol_ratio:.1f}x avg)")
        elif score < 45:
            score -= 4 * w_vol
            reasons.append(f"Elevated volume on weakness ({vol_ratio:.1f}x)")

    # --- Recent performance context ---
    change_7d = latest.get("change_7d")
    change_30d = latest.get("change_30d")
    if pd.notna(change_7d) and change_7d > 8:
        score += 3 * w_perf
        reasons.append(f"Strong 7d move (+{change_7d:.1f}%)")
    elif pd.notna(change_7d) and change_7d < -8:
        score -= 3 * w_perf
        reasons.append(f"Weak 7d move ({change_7d:.1f}%)")

    # Clamp
    score = max(0, min(100, score))

    bullish = sum(1 for r in reasons if any(w in r.lower() for w in ["above", "oversold", "positive", "strong 7d", "elevated volume ("]) and "weakness" not in r.lower())
    bearish = sum(1 for r in reasons if any(w in r.lower() for w in ["below", "overbought", "weak", "elevated volume on weakness"]))
    confluence = int(bullish - bearish)

    if score >= 72:
        label = "Strong Bullish"
    elif score >= 60:
        label = "Bullish"
    elif score >= 52:
        label = "Mildly Bullish"
    elif score >= 48:
        label = "Neutral"
    elif score >= 40:
        label = "Mildly Bearish"
    elif score >= 28:
        label = "Bearish"
    else:
        label = "Strong Bearish"

    atr = latest.get("atr")
    atr_pct = (atr / close * 100) if pd.notna(atr) and close else None

    return {
        "score": round(score, 1),
        "label": label,
        "reasons": reasons,
        "confluence": confluence,
        "latest_price": round(close, 4) if close < 1 else round(close, 2),
        "rsi": round(rsi, 1) if pd.notna(rsi) else None,
        "change_7d": round(change_7d, 1) if pd.notna(change_7d) else None,
        "change_30d": round(change_30d, 1) if pd.notna(change_30d) else None,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
        "volume_ratio": round(vol_ratio, 2) if pd.notna(vol_ratio) else None,
        "bb_position": round(bb_position, 2) if bb_position is not None else None,
        "adx": round(adx_val, 1) if pd.notna(adx_val) else None,
    }