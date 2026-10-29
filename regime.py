"""Market regime: is this asset trending or ranging, and which way?

Plain rules on numbers the score already calculates (ADX, the 50 and 200 day
averages), so it needs no extra data and works on any bar size.

- ADX of 25 or more: trending. Below 20: ranging. In between: transitional.
- Direction: up when price is above a rising stack (price > SMA 50 > SMA 200),
  down for the mirror image, otherwise mixed. With no SMA 200 yet, price against
  the SMA 50 decides.

A new regime is only accepted after it has shown up on CONFIRM bars in a row,
so an asset hovering near ADX 25 does not flip back and forth every day.

The score can scale each indicator's weight by regime (see REGIME_MULTIPLIERS).
That is optional and off unless asked for.
"""

from __future__ import annotations

import pandas as pd

TREND_ADX = 25.0
RANGE_ADX = 20.0
CONFIRM = 3
LOOKBACK = 30  # bars looked at when only the latest regime is wanted

TRENDING = "trending"
RANGING = "ranging"
TRANSITIONAL = "transitional"

# Multipliers on the score weights, keyed by the weight names used in scoring.py.
# Trends favour trend followers; ranges favour mean reversion. Anything not listed is 1.
REGIME_MULTIPLIERS = {
    TRENDING: {
        "sma": 1.5, "macd": 1.5, "ichimoku": 1.5, "adx": 1.5, "obv": 1.25,
        "rsi": 0.5, "stochastic": 0.5, "bb": 0.5,
    },
    RANGING: {
        "rsi": 1.5, "stochastic": 1.5, "bb": 1.5,
        "sma": 0.5, "macd": 0.5, "ichimoku": 0.5, "adx": 0.5,
    },
    TRANSITIONAL: {},
}


def _raw_state(adx) -> str | None:
    if adx is None or pd.isna(adx):
        return None
    if adx >= TREND_ADX:
        return TRENDING
    if adx < RANGE_ADX:
        return RANGING
    return TRANSITIONAL


def _direction(close, sma50, sma200) -> str:
    if close is None or pd.isna(close) or sma50 is None or pd.isna(sma50):
        return "mixed"
    if sma200 is None or pd.isna(sma200):
        return "up" if close > sma50 else "down" if close < sma50 else "mixed"
    if close > sma50 > sma200:
        return "up"
    if close < sma50 < sma200:
        return "down"
    return "mixed"


def regime_series(df: pd.DataFrame, confirm: int = CONFIRM) -> pd.DataFrame:
    """Per bar: raw and confirmed state, plus direction. Needs adx, sma_50 (sma_200 optional)."""
    if df is None or df.empty or "adx" not in df.columns:
        return pd.DataFrame(columns=["raw", "state", "direction"])
    close = df["close"] if "close" in df.columns else pd.Series(float("nan"), index=df.index)
    sma50 = df["sma_50"] if "sma_50" in df.columns else pd.Series(float("nan"), index=df.index)
    sma200 = df["sma_200"] if "sma_200" in df.columns else pd.Series(float("nan"), index=df.index)

    raws, states, directions = [], [], []
    confirmed, candidate, streak = None, None, 0
    for adx, c, s50, s200 in zip(df["adx"], close, sma50, sma200):
        raw = _raw_state(adx)
        raws.append(raw)
        directions.append(_direction(c, s50, s200))
        if raw is None:
            states.append(confirmed)
            continue
        if confirmed is None:
            confirmed, candidate, streak = raw, raw, confirm
        elif raw == confirmed:
            candidate, streak = raw, confirm
        else:
            streak = streak + 1 if raw == candidate else 1
            candidate = raw
            if streak >= confirm:
                confirmed = raw
        states.append(confirmed)
    return pd.DataFrame({"raw": raws, "state": states, "direction": directions}, index=df.index)


def latest_regime(df: pd.DataFrame, confirm: int = CONFIRM, lookback: int = LOOKBACK) -> dict | None:
    """The confirmed regime on the last bar, or None when ADX is not available yet."""
    if df is None or df.empty or "adx" not in df.columns:
        return None
    table = regime_series(df.iloc[-max(lookback, confirm + 1):], confirm)
    if table.empty or table["state"].iloc[-1] is None:
        return None
    state = table["state"].iloc[-1]
    direction = table["direction"].iloc[-1]
    label = state if state != TRENDING else f"{TRENDING}_{direction}"
    return {"state": state, "direction": direction, "label": label}


def multipliers_for(state: str | None) -> dict:
    return dict(REGIME_MULTIPLIERS.get(state, {}))
