"""
Simple scoring logic for Phase 1 MVP.
Easy to understand and extend.
"""

import pandas as pd
import pandas_ta as ta

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add basic technical indicators to a price DataFrame."""
    if df.empty or len(df) < 20:
        return df
    
    # RSI
    df["rsi"] = ta.rsi(df["close"], length=14)
    
    # Moving averages
    df["sma_20"] = ta.sma(df["close"], length=20)
    df["sma_50"] = ta.sma(df["close"], length=50)
    
    # MACD
    macd = ta.macd(df["close"])
    if macd is not None:
        df = pd.concat([df, macd], axis=1)
    
    return df


def compute_score(df: pd.DataFrame) -> dict:
    """
    Compute a simple 0-100 composite score based on a few rules.
    Higher score = more bullish.
    Returns a dictionary with score and reasons.
    """
    if df.empty or len(df) < 20:
        return {"score": 50, "label": "Insufficient data", "reasons": ["Not enough history"]}
    
    latest = df.iloc[-1]
    score = 50  # neutral starting point
    reasons = []
    
    # RSI contribution
    rsi = latest.get("rsi")
    if pd.notna(rsi):
        if rsi < 30:
            score += 15
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 15
            reasons.append(f"RSI overbought ({rsi:.1f})")
        else:
            reasons.append(f"RSI neutral ({rsi:.1f})")
    
    # Price vs moving averages
    close = latest["close"]
    sma20 = latest.get("sma_20")
    sma50 = latest.get("sma_50")
    
    if pd.notna(sma20) and close > sma20:
        score += 10
        reasons.append("Price above 20-day SMA")
    elif pd.notna(sma20):
        score -= 10
        reasons.append("Price below 20-day SMA")
    
    if pd.notna(sma50) and close > sma50:
        score += 10
        reasons.append("Price above 50-day SMA")
    elif pd.notna(sma50):
        score -= 10
        reasons.append("Price below 50-day SMA")
    
    # MACD (if available)
    if "MACD_12_26_9" in df.columns and pd.notna(latest.get("MACD_12_26_9")):
        macd_line = latest["MACD_12_26_9"]
        signal_line = latest.get("MACDs_12_26_9")
        if pd.notna(signal_line) and macd_line > signal_line:
            score += 8
            reasons.append("MACD bullish crossover")
        elif pd.notna(signal_line):
            score -= 8
            reasons.append("MACD bearish")
    
    # Clamp score between 0 and 100
    score = max(0, min(100, score))
    
    if score >= 70:
        label = "Bullish"
    elif score >= 55:
        label = "Mildly Bullish"
    elif score >= 45:
        label = "Neutral"
    elif score >= 30:
        label = "Mildly Bearish"
    else:
        label = "Bearish"
    
    return {
        "score": round(score, 1),
        "label": label,
        "reasons": reasons,
        "latest_price": close,
        "rsi": rsi
    }
