"""
First signals: thin wrappers over calculations the app already has, to prove the interface.
They add no new formulas: direction uses regime._direction and regime uses regime.regime_series.
"""

from __future__ import annotations

import pandas as pd

import chart_data
import regime as regime_rules

from .context import confirmed_frame
from .core import (
    CATEGORY, CONFIRMED, DIRECTION, INSUFFICIENT, MISSING, OK, SCOPE_ASSET, TIMEFRAMES,
    Param, SignalResult, iso, signal,
)

YAHOO = "Yahoo Finance candles (via chart_data)"


def closed_candles(ctx, timeframe: str, minimum: int):
    """(frame of closed candles, loaded dict, failure result or None)."""
    loaded = ctx.candles(timeframe)
    if loaded.get("error"):
        return None, loaded, SignalResult(ref={}, subject=ctx.subject, status=MISSING, notes=[loaded["error"]])
    frame = confirmed_frame(loaded)
    if frame is None or len(frame) < minimum:
        have = 0 if frame is None else len(frame)
        return None, loaded, SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT,
                                          notes=[f"{have} closed {timeframe} candles; {minimum} needed."])
    return frame, loaded, None


def bar_times(ctx, loaded: dict, timeframe: str, start) -> tuple[str, str]:
    """observed_at = candle start; available_at = when that candle closed."""
    kind = "crypto" if ctx.kind == "crypto" else "equity"
    end = chart_data.candle_end(pd.Timestamp(start), timeframe, kind, loaded.get("session"))
    return iso(start), iso(end)


@signal(
    id="trend.direction", version=1, name="Trend direction", category="trend",
    output=DIRECTION, unit="label", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    calculation=("On the last closed candle: up when close > SMA 50 > SMA 200, down when close < SMA 50 < SMA 200, "
                 "otherwise mixed. Without SMA 200 yet, close against SMA 50 decides. Same rule as the market regime."),
    interpretation="Which way the moving-average stack points on this timeframe. Descriptive.",
    limitations="Moving averages lag; after a sharp reversal this stays on the old direction for a while.",
    polarity="up = price above a rising average stack", max_age_bars=3,
)
def trend_direction(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 50)
    if failed:
        return failed
    last = frame.iloc[-1]
    direction = regime_rules._direction(last.get("close"), last.get("sma_50"), last.get("sma_200"))
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return SignalResult(
        ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=direction,
        observed_at=observed, available_at=available,
        evidence={"close": float(last["close"]), "sma_50": _num(last.get("sma_50")), "sma_200": _num(last.get("sma_200"))},
        provenance=[loaded.get("source") or YAHOO],
    )


@signal(
    id="regime.state", version=1, name="Market regime", category="regime",
    output=CATEGORY, unit="label", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    labels=("trending", "ranging", "transitional"),
    calculation=("ADX(14) >= 25 trending, < 20 ranging, otherwise transitional; a new state is accepted after it "
                 "holds for `confirm` closed candles in a row. Same rules as the existing regime feature."),
    interpretation="Whether the asset is trending or ranging on this timeframe, with the evidence behind it.",
    limitations="ADX thresholds are conventions; ADX says how strong a move is, not which way.",
    params={"confirm": Param(3, "int", 1, 10, doc="closed candles a new state must hold before it is accepted")},
)
def regime_state(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 30)
    if failed:
        return failed
    table = regime_rules.regime_series(frame.iloc[-120:], confirm=params["confirm"])
    if table.empty or table["state"].iloc[-1] is None:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["ADX not available yet."])
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    changes = table["state"].ne(table["state"].shift()).cumsum()
    held = int((changes == changes.iloc[-1]).sum())
    return SignalResult(
        ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=table["state"].iloc[-1],
        observed_at=observed, available_at=available,
        evidence={"adx": _num(frame["adx"].iloc[-1]), "raw_state_now": table["raw"].iloc[-1],
                  "direction": table["direction"].iloc[-1], "candles_in_state": held},
        provenance=[loaded.get("source") or YAHOO],
    )


def _num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if value != value else round(value, 6)
