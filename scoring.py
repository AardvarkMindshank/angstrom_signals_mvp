"""
Enhanced scoring logic for the Signals Dashboard.
Supports dynamic indicator weighting for custom balance.
"""

import pandas as pd
import pandas_ta as ta
import numpy as np


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add a richer set of technical indicators with robust error guarding."""
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
        ichimoku = ta.ichimoku(high, low, close)
        if ichimoku is not None and len(ichimoku) >= 2:
            df = pd.concat([df, ichimoku[0], ichimoku[1]], axis=1)
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
    """Multi-factor 0-100 score with safe scalar extraction."""
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
    w_ichi = weights.get("ichimoku", 1.0)
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
        pts = 0.0
        if rsi_val < 30:
            pts = 12 * w_rsi
            reasons.append(f"RSI oversold ({rsi_val:.1f})")
        elif rsi_val < 40:
            pts = 5 * w_rsi
            reasons.append(f"RSI approaching oversold ({rsi_val:.1f})")
        elif rsi_val > 70:
            pts = -12 * w_rsi
            reasons.append(f"RSI overbought ({rsi_val:.1f})")
        elif rsi_val > 60:
            pts = -5 * w_rsi
            reasons.append(f"RSI elevated ({rsi_val:.1f})")
        else:
            reasons.append(f"RSI neutral ({rsi_val:.1f})")
        score += pts
        contributions["RSI"] = pts

    # Stochastic
    stoch_k = latest.get("stoch_k")
    if pd.notna(stoch_k):
        sk_val = float(stoch_k.iloc[-1] if isinstance(stoch_k, pd.Series) else stoch_k)
        pts = 0.0
        if sk_val < 20:
            pts = 6 * w_stoch
            reasons.append(f"Stochastic oversold ({sk_val:.1f})")
        elif sk_val > 80:
            pts = -6 * w_stoch
            reasons.append(f"Stochastic overbought ({sk_val:.1f})")
        score += pts
        contributions["Stochastic"] = pts

    # Moving Averages
    sma20 = latest.get("sma_20")
    sma50 = latest.get("sma_50")
    sma200 = latest.get("sma_200")
    sma_pts = 0.0
    if pd.notna(sma20):
        s20 = float(sma20.iloc[-1] if isinstance(sma20, pd.Series) else sma20)
        if close > s20:
            sma_pts += 8 * w_sma
            reasons.append("Price above SMA 20")
        else:
            sma_pts -= 8 * w_sma
            reasons.append("Price below SMA 20")
    if pd.notna(sma50):
        s50 = float(sma50.iloc[-1] if isinstance(sma50, pd.Series) else sma50)
        if close > s50:
            sma_pts += 7 * w_sma
            reasons.append("Price above SMA 50")
        else:
            sma_pts -= 7 * w_sma
            reasons.append("Price below SMA 50")
    if pd.notna(sma200):
        s200 = float(sma200.iloc[-1] if isinstance(sma200, pd.Series) else sma200)
        if close > s200:
            sma_pts += 6 * w_sma
            reasons.append("Price above SMA 200")
        else:
            sma_pts -= 6 * w_sma
            reasons.append("Price below SMA 200")
    score += sma_pts
    contributions["Moving Averages"] = sma_pts

    # ADX
    adx_val = latest.get("ADX_14")
    adx_num = None
    if pd.notna(adx_val):
        adx_num = float(adx_val.iloc[-1] if isinstance(adx_val, pd.Series) else adx_val)
        adx_pts = 0.0
        if adx_num > 25:
            reasons.append(f"Strong trend (ADX {adx_num:.1f})")
            adx_pts = (4 * w_adx) if score > 55 else (-4 * w_adx if score < 45 else 0)
        score += adx_pts
        contributions["ADX Trend"] = adx_pts

    # MACD
    macd_cols = [c for c in df.columns if c.startswith("MACD_")]
    if macd_cols:
        try:
            m_line = latest.get("MACD_12_26_9")
            m_sig = latest.get("MACDs_12_26_9")
            m_hist = latest.get("MACDh_12_26_9")
            ml = float(m_line.iloc[-1] if isinstance(m_line, pd.Series) else m_line) if pd.notna(m_line) else 0.0
            ms = float(m_sig.iloc[-1] if isinstance(m_sig, pd.Series) else m_sig) if pd.notna(m_sig) else 0.0
            mh = float(m_hist.iloc[-1] if isinstance(m_hist, pd.Series) else m_hist) if pd.notna(m_hist) else 0.0
            
            prev = df.iloc[-2] if len(df) > 1 else latest
            prev_h = prev.get("MACDh_12_26_9", mh)
            ph = float(prev_h.iloc[-1] if isinstance(prev_h, pd.Series) else prev_h) if pd.notna(prev_h) else mh

            macd_pts = 0.0
            if ml > ms:
                macd_pts += 5 * w_macd
                reasons.append("MACD above signal")
            else:
                macd_pts -= 5 * w_macd
                reasons.append("MACD below signal")
            if mh > 0:
                macd_pts += 3 * w_macd
                if mh > ph:
                    macd_pts += 2 * w_macd
                    reasons.append("MACD histogram expanding (bullish)")
            else:
                macd_pts -= 3 * w_macd
                if mh < ph:
                    macd_pts -= 2 * w_macd
                    reasons.append("MACD histogram expanding (bearish)")
            score += macd_pts
            contributions["MACD & Hist"] = macd_pts
        except Exception:
            pass

    # Ichimoku
    isa_cols = [c for c in df.columns if c.startswith("ISA_")]
    isb_cols = [c for c in df.columns if c.startswith("ISB_")]
    if isa_cols and isb_cols:
        try:
            sa_raw = latest.get(isa_cols[0])
            sb_raw = latest.get(isb_cols[0])
            if sa_raw is not None and sb_raw is not None:
                sa = float(sa_raw.iloc[-1] if isinstance(sa_raw, pd.Series) else sa_raw)
                sb = float(sb_raw.iloc[-1] if isinstance(sb_raw, pd.Series) else sb_raw)
                if pd.notna(sa) and pd.notna(sb):
                    cloud_top = max(sa, sb)
                    cloud_bottom = min(sa, sb)
                    ichi_pts = 0.0
                    if close > cloud_top:
                        ichi_pts = 7 * w_ichi
                        reasons.append("Price above Ichimoku Cloud")
                    elif close < cloud_bottom:
                        ichi_pts = -7 * w_ichi
                        reasons.append("Price below Ichimoku Cloud")
                    score += ichi_pts
                    contributions["Ichimoku Cloud"] = ichi_pts
        except Exception:
            pass

    # Bollinger Bands
    bb_upper = latest.get("BBU_20_2.0")
    bb_lower = latest.get("BBL_20_2.0")
    bb_position = None
    if pd.notna(bb_upper) and pd.notna(bb_lower):
        bbu = float(bb_upper.iloc[-1] if isinstance(bb_upper, pd.Series) else bb_upper)
        bbl = float(bb_lower.iloc[-1] if isinstance(bb_lower, pd.Series) else bb_lower)
        if (bbu - bbl) > 0:
            bb_position = (close - bbl) / (bbu - bbl)
            bb_pts = 0.0
            if bb_position < 0.2:
                bb_pts = 7 * w_bb
                reasons.append("Near lower Bollinger Band")
            elif bb_position > 0.8:
                bb_pts = -7 * w_bb
                reasons.append("Near upper Bollinger Band")
            score += bb_pts
            contributions["Bollinger Bands"] = bb_pts

    # Volume & OBV
    vol_ratio = latest.get("volume_ratio")
    if pd.notna(vol_ratio):
        vr = float(vol_ratio.iloc[-1] if isinstance(vol_ratio, pd.Series) else vol_ratio)
        if vr > 1.3:
            vol_pts = (4 * w_vol) if score > 55 else (-4 * w_vol if score < 45 else 0)
            reasons.append(f"Elevated volume ({vr:.1f}x)")
            score += vol_pts
            contributions["Volume"] = vol_pts

    obv_val = latest.get("obv")
    obv_sma = latest.get("obv_sma_20")
    if pd.notna(obv_val) and pd.notna(obv_sma):
        ov = float(obv_val.iloc[-1] if isinstance(obv_val, pd.Series) else obv_val)
        os_val = float(obv_sma.iloc[-1] if isinstance(obv_sma, pd.Series) else obv_sma)
        obv_pts = (5 * w_obv) if ov > os_val else (-5 * w_obv)
        reasons.append("OBV accumulation" if ov > os_val else "OBV distribution")
        score += obv_pts
        contributions["OBV"] = obv_pts

    # Performance
    change_7d = latest.get("change_7d")
    change_30d = latest.get("change_30d")
    c7_val = None
    if pd.notna(change_7d):
        c7_val = float(change_7d.iloc[-1] if isinstance(change_7d, pd.Series) else change_7d)
        perf_pts = (3 * w_perf) if c7_val > 8 else (-3 * w_perf if c7_val < -8 else 0)
        score += perf_pts
        contributions["Performance"] = perf_pts

    score = max(0, min(100, score))

    bullish = sum(1 for r in reasons if any(w in r.lower() for w in ["above", "oversold", "positive", "accumulation", "expanding", "bullish"]) and "weakness" not in r.lower())
    bearish = sum(1 for r in reasons if any(w in r.lower() for w in ["below", "overbought", "distribution", "bearish"]))
    confluence = int(bullish - bearish)

    if score >= 72: label = "Strong Bullish"
    elif score >= 60: label = "Bullish"
    elif score >= 52: label = "Mildly Bullish"
    elif score >= 48: label = "Neutral"
    elif score >= 40: label = "Mildly Bearish"
    elif score >= 28: label = "Bearish"
    else: label = "Strong Bearish"

    atr = latest.get("atr")
    atr_val = float(atr.iloc[-1] if isinstance(atr, pd.Series) else atr) if pd.notna(atr) else None
    atr_pct = (atr_val / close * 100) if atr_val and close else None

    contributions = {k: round(v, 1) for k, v in contributions.items()}

    c30_val = float(change_30d.iloc[-1] if isinstance(change_30d, pd.Series) else change_30d) if pd.notna(change_30d) else None
    vr_val = float(vol_ratio.iloc[-1] if isinstance(vol_ratio, pd.Series) else vol_ratio) if pd.notna(vol_ratio) else None

    return {
        "score": round(score, 1),
        "label": label,
        "reasons": reasons,
        "confluence": confluence,
        "latest_price": round(close, 4) if close < 1 else round(close, 2),
        "rsi": round(rsi_val, 1) if rsi_val is not None else None,
        "change_7d": round(c7_val, 1) if c7_val is not None else None,
        "change_30d": round(c30_val, 1) if c30_val is not None else None,
        "atr_pct": round(atr_pct, 2) if atr_pct else None,
        "volume_ratio": round(vr_val, 2) if vr_val is not None else None,
        "bb_position": round(bb_position, 2) if bb_position is not None else None,
        "adx": round(adx_num, 1) if adx_num is not None else None,
        "contributions": contributions,
    }