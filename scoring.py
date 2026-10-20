"""
Clean and functional scoring logic for the Signals Dashboard.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators safely."""
    if df.empty or len(df) < 15:
        return df

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df.get("volume", pd.Series(0, index=df.index))

    try:
        df["rsi"] = ta.rsi(close, length=14)
    except Exception:
        pass

    try:
        stoch = ta.stoch(high, low, close, k=14, d=3)
        if stoch is not None and not stoch.empty:
            df["stoch_k"] = stoch.iloc[:, 0]
    except Exception:
        pass

    try:
        df["sma_20"] = ta.sma(close, length=20)
        df["sma_50"] = ta.sma(close, length=50)
        df["sma_200"] = ta.sma(close, length=200)
    except Exception:
        pass

    try:
        adx_df = ta.adx(high, low, close, length=14)
        if adx_df is not None and not adx_df.empty:
            df = pd.concat([df, adx_df], axis=1)
    except Exception:
        pass

    try:
        macd = ta.macd(close)
        if macd is not None and not macd.empty:
            df = pd.concat([df, macd], axis=1)
    except Exception:
        pass

    try:
        df["atr"] = ta.atr(high, low, close, length=14)
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None and not bb.empty:
            df = pd.concat([df, bb], axis=1)
    except Exception:
        pass

    try:
        df["vol_sma_20"] = ta.sma(volume, length=20)
        df["volume_ratio"] = volume / df["vol_sma_20"].replace(0, np.nan)
        obv = ta.obv(close, volume)
        if obv is not None:
            df["obv"] = obv
            df["obv_sma_20"] = ta.sma(obv, length=20)
    except Exception:
        pass

    try:
        df["change_7d"] = close.pct_change(7) * 100
        df["change_30d"] = close.pct_change(30) * 100
    except Exception:
        pass

    return df


def compute_score(df: pd.DataFrame, weights: dict = None) -> dict:
    """Multi-factor 0-100 score."""
    if weights is None:
        weights = {
            "rsi": 1.0, "stochastic": 1.0, "sma": 1.0, "adx": 1.0,
            "macd": 1.0, "ichimoku": 1.0, "bb": 1.0, "volume": 1.0,
            "obv": 1.0, "performance": 1.0,
        }

    if df.empty or len(df) < 15:
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
            "contributions": {},
        }

    latest = df.iloc[-1]
    score = 50.0
    reasons = []
    
    contributions = {
        "RSI": 0.0, "Stochastic": 0.0, "Moving Averages": 0.0,
        "ADX Trend": 0.0, "MACD & Hist": 0.0, "Ichimoku Cloud": 0.0,
        "Bollinger Bands": 0.0, "Volume": 0.0, "OBV": 0.0, "Performance": 0.0,
    }

    w_rsi = weights.get("rsi", 1.0)
    w_stoch = weights.get("stochastic", 1.0)
    w_sma = weights.get("sma", 1.0)
    w_adx = weights.get("adx", 1.0)
    w_macd = weights.get("macd", 1.0)
    w_bb = weights.get("bb", 1.0)
    w_vol = weights.get("volume", 1.0)
    w_obv = weights.get("obv", 1.0)
    w_perf = weights.get("performance", 1.0)

    close = float(latest["close"])

    # RSI
    rsi = latest.get("rsi")
    rsi_val = None
    if pd.notna(rsi):
        rsi_val = float(rsi.iloc[-1] if isinstance(rsi, pd.Series) else rsi)
        if rsi_val < 35:
            score += 8 * w_rsi
            reasons.append(f"RSI oversold ({rsi_val:.1f})")
            contributions["RSI"] = 8 * w_rsi
        elif rsi_val > 65:
            score -= 8 * w_rsi
            reasons.append(f"RSI overbought ({rsi_val:.1f})")
            contributions["RSI"] = -8 * w_rsi
        else:
            reasons.append(f"RSI neutral ({rsi_val:.1f})")

    # Moving Averages
    sma20 = latest.get("sma_20")
    sma50 = latest.get("sma_50")
    if pd.notna(sma20):
        s20 = float(sma20.iloc[-1] if isinstance(sma20, pd.Series) else sma20)
        if close > s20:
            score += 6 * w_sma
            reasons.append("Price above SMA 20")
            contributions["Moving Averages"] += 6 * w_sma
        else:
            score -= 6 * w_sma
            reasons.append("Price below SMA 20")
            contributions["Moving Averages"] -= 6 * w_sma

    if pd.notna(sma50):
        s50 = float(sma50.iloc[-1] if isinstance(sma50, pd.Series) else sma50)
        if close > s50:
            score += 6 * w_sma
            reasons.append("Price above SMA 50")
            contributions["Moving Averages"] += 6 * w_sma
        else:
            score -= 6 * w_sma
            reasons.append("Price below SMA 50")
            contributions["Moving Averages"] -= 6 * w_sma

    # MACD
    if "MACD_12_26_9" in df.columns and pd.notna(latest.get("MACD_12_26_9")) and w_macd > 0:
        m_line = latest.get("MACD_12_26_9")
        m_sig = latest.get("MACDs_12_26_9")
        ml = float(m_line.iloc[-1] if isinstance(m_line, pd.Series) else m_line)
        ms = float(m_sig.iloc[-1] if isinstance(m_sig, pd.Series) else m_sig) if pd.notna(m_sig) else 0.0
        if ml > ms:
            score += 6 * w_macd
            reasons.append("MACD above signal")
            contributions["MACD & Hist"] = 6 * w_macd
        else:
            score -= 6 * w_macd
            reasons.append("MACD below signal")
            contributions["MACD & Hist"] = -6 * w_macd

    # Bollinger Bands
    bb_upper = latest.get("BBU_20_2.0")
    bb_lower = latest.get("BBL_20_2.0")
    bb_position = None
    if pd.notna(bb_upper) and pd.notna(bb_lower):
        bbu = float(bb_upper.iloc[-1] if isinstance(bb_upper, pd.Series) else bb_upper)
        bbl = float(bb_lower.iloc[-1] if isinstance(bb_lower, pd.Series) else bb_lower)
        if (bbu - bbl) > 0:
            bb_position = (close - bbl) / (bbu - bbl)
            if bb_position < 0.2:
                score += 5 * w_bb
                reasons.append("Near lower Bollinger Band")
                contributions["Bollinger Bands"] = 5 * w_bb
            elif bb_position > 0.8:
                score -= 5 * w_bb
                reasons.append("Near upper Bollinger Band")
                contributions["Bollinger Bands"] = -5 * w_bb

    # Performance
    change_7d = latest.get("change_7d")
    c7_val = None
    if pd.notna(change_7d) and w_perf > 0:
        c7_val = float(change_7d.iloc[-1] if isinstance(change_7d, pd.Series) else change_7d)
        if c7_val > 3:
            score += 5 * w_perf
            reasons.append(f"Strong 7d move (+{c7_val:.1f}%)")
            contributions["Performance"] = 5 * w_perf
        elif c7_val < -3:
            score -= 5 * w_perf
            reasons.append(f"Weak 7d move ({c7_val:.1f}%)")
            contributions["Performance"] = -5 * w_perf

    score = max(0, min(100, score))

    if score >= 65: label = "Strong Bullish"
    elif score >= 56: label = "Bullish"
    elif score >= 52: label = "Mildly Bullish"
    elif score >= 48: label = "Neutral"
    elif score >= 42: label = "Mildly Bearish"
    elif score >= 32: label = "Bearish"
    else: label = "Strong Bearish"

    atr = latest.get("atr")
    atr_val = float(atr.iloc[-1] if isinstance(atr, pd.Series) else atr) if pd.notna(atr) else None
    atr_pct = (atr_val / close * 100) if atr_val and close else None

    change_30d = latest.get("change_30d")
    c30_val = float(change_30d.iloc[-1] if isinstance(change_30d, pd.Series) else change_30d) if pd.notna(change_30d) else None
    vol_ratio = latest.get("volume_ratio")
    vr_val = float(vol_ratio.iloc[-1] if isinstance(vol_ratio, pd.Series) else vol_ratio) if pd.notna(vol_ratio) else None

    contributions = {k: round(v, 1) for k, v in contributions.items()}

    return {
        "score": round(score, 1),
        "label": label,
        "reasons": reasons,
        "confluence": 0,
        "latest_price": round(close, 4) if close < 1 else round(close, 2),
        "rsi": round(rsi_val, 1) if rsi_val is not None else None,
        "change_7d": round(c7_val, 1) if c7_val is not None else None,
        "change_30d": round(c30_val, 1) if c30_val is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
        "volume_ratio": round(vr_val, 2) if vr_val is not None else None,
        "bb_position": round(bb_position, 2) if bb_position is not None else None,
        "adx": None,
        "contributions": contributions,
    }