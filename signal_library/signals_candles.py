"""
Candle-level building blocks with adjustable settings (asked for 10 Nov 2026 to write setups such as Drew's
"BTC Hybrid" entry rules as Sets):

* ma.line      a moving average of any length, EMA or SMA: where the close sits, and whether this candle touched it and
               closed back on one side (a retest) or crossed it;
* ma.pair      two moving averages (for example EMA 20 over EMA 50): their order, the gap and a cross on this candle;
* candle.shape the last closed candle: green or red, a higher or lower close than the candle before, its body against
               the average body of recent candles;
* volatility.atr_trend  ATR against its own average: is volatility expanding?

Each reads closed candles only, on the timeframe asked for. The formulas are the usual chart ones (TradingView's
ta.ema, ta.sma, ta.rma, ta.tr), written out here; nothing is tuned on outcomes. Descriptive readings, not forecasts.
"""

from __future__ import annotations

import pandas as pd

from .core import OBSERVATION, OK, SCOPE_ASSET, TIMEFRAMES, Param, SignalResult, signal, INSUFFICIENT, CONFIRMED
from .signals_basic import YAHOO, _num, bar_times, closed_candles

KINDS = ("EMA", "SMA")


def _ok(ctx, loaded, timeframe, frame, value, evidence):
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=value,
                        observed_at=observed, available_at=available, evidence=evidence,
                        provenance=[loaded.get("source") or YAHOO])


def _r(x, digits=6):
    x = _num(x)
    return None if x is None else round(x, digits)


def average(close: pd.Series, kind: str, length: int) -> pd.Series:
    """EMA as TradingView's ta.ema (alpha 2/(n+1), started from the first close); SMA as ta.sma."""
    if kind == "EMA":
        return close.ewm(span=length, adjust=False, min_periods=length).mean()
    return close.rolling(length, min_periods=length).mean()


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev = frame["close"].shift(1)
    return pd.concat([frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()],
                     axis=1).max(axis=1)


def wilder_atr(frame: pd.DataFrame, length: int) -> pd.Series:
    """ATR as TradingView's ta.atr: Wilder's average (ta.rma) of the true range."""
    return true_range(frame).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def _need(kind: str, length: int) -> int:
    """Closed candles needed: an EMA settles after about three lengths."""
    return length * 3 + 2 if kind == "EMA" else length + 2


# ----------------------------------------------------------------------------------------------- one average

@signal(
    id="ma.line", version=1, name="Moving average (EMA or SMA, any length)", category="trend",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"kind": Param("EMA", "choice", choices=KINDS, doc="exponential (EMA) or simple (SMA) average"),
            "length": Param(20, "int", 2, 400, doc="candles averaged")},
    calculation=("On the last closed candle, with the average of closes over `length` candles (EMA as TradingView's "
                 "ta.ema, SMA as ta.sma): position = above or below the close; distance in % and in ATR(14); "
                 "retest_from_above = the low reached the average and the close finished above it; retest_from_below = "
                 "the high reached it and the close finished below; crossed_up = the previous close was below the "
                 "average and this close is above it; crossed_down the reverse; slope = the average higher or lower "
                 "than one candle before."),
    interpretation=("Where price sits against one moving average, and whether this candle pulled back to it and held "
                    "(a retest) or crossed it. Descriptive; not a forecast."),
    limitations=("Averages lag. A retest on one candle is common in choppy markets; pair it with a trend reading. An EMA "
                 "needs about three lengths of history to settle, so new listings say not enough data."),
)
def ma_line(ctx, timeframe, params):
    kind, length = params["kind"], params["length"]
    frame, loaded, failed = closed_candles(ctx, timeframe, _need(kind, length))
    if failed:
        return failed
    avg = average(frame["close"], kind, length)
    a, a_prev = _num(avg.iloc[-1]), _num(avg.iloc[-2])
    close, prev_close = _num(frame["close"].iloc[-1]), _num(frame["close"].iloc[-2])
    high, low = _num(frame["high"].iloc[-1]), _num(frame["low"].iloc[-1])
    atr = _num(wilder_atr(frame, 14).iloc[-1])
    if None in (a, close, prev_close, high, low):
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["The average is not ready yet."])
    value = {
        "average": _r(a), "close": close,
        "position": "above" if close > a else "below" if close < a else "on",
        "distance_pct": _r((close - a) / a * 100) if a else None,
        "distance_atr": _r((close - a) / atr) if atr else None,
        "retest_from_above": bool(low <= a and close > a),
        "retest_from_below": bool(high >= a and close < a),
        "crossed_up": bool(prev_close < a and close > a),
        "crossed_down": bool(prev_close > a and close < a),
        "slope": None if a_prev is None else "up" if a > a_prev else "down" if a < a_prev else "flat",
    }
    return _ok(ctx, loaded, timeframe, frame, value, {"kind": kind, "length": length, "previous_close": prev_close,
                                                       "high": high, "low": low, "atr_14": _r(atr)})


# ----------------------------------------------------------------------------------------------- two averages

@signal(
    id="ma.pair", version=1, name="Two moving averages (fast vs slow)", category="trend",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"kind": Param("EMA", "choice", choices=KINDS, doc="exponential (EMA) or simple (SMA) averages"),
            "fast": Param(20, "int", 2, 400, doc="candles in the fast average"),
            "slow": Param(50, "int", 3, 400, doc="candles in the slow average")},
    calculation=("On the last closed candle: order = fast_above when the fast average is above the slow one, "
                 "fast_below when under; gap_pct = (fast - slow) / slow x 100; crossed = up when the fast average "
                 "moved above the slow one on this candle, down when it moved below, none otherwise."),
    interpretation="The trend as two averages see it, such as EMA 20 over EMA 50 for an uptrend. Descriptive.",
    limitations="Both averages lag; crosses come late and repeat in sideways markets.",
)
def ma_pair(ctx, timeframe, params):
    kind, fast, slow = params["kind"], params["fast"], params["slow"]
    if fast >= slow:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT,
                            notes=["The fast average must be shorter than the slow one."])
    frame, loaded, failed = closed_candles(ctx, timeframe, _need(kind, slow))
    if failed:
        return failed
    f, s = average(frame["close"], kind, fast), average(frame["close"], kind, slow)
    f1, s1, f0, s0 = (_num(x) for x in (f.iloc[-1], s.iloc[-1], f.iloc[-2], s.iloc[-2]))
    if None in (f1, s1):
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["The averages are not ready yet."])
    crossed = "none"
    if None not in (f0, s0):
        if f0 <= s0 and f1 > s1:
            crossed = "up"
        elif f0 >= s0 and f1 < s1:
            crossed = "down"
    value = {"fast": _r(f1), "slow": _r(s1), "order": "fast_above" if f1 > s1 else "fast_below",
             "gap_pct": _r((f1 - s1) / s1 * 100) if s1 else None, "crossed": crossed}
    return _ok(ctx, loaded, timeframe, frame, value, {"kind": kind, "fast": fast, "slow": slow})


# ----------------------------------------------------------------------------------------------- the candle

@signal(
    id="candle.shape", version=1, name="Candle (colour, close vs previous, body size)", category="momentum",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"average": Param(10, "int", 3, 100, doc="candles in the average body size")},
    calculation=("On the last closed candle: colour = green when close > open, red when close < open; "
                 "close_vs_previous = higher or lower than the previous candle's close; change_pct from the previous "
                 "close; body = |close - open|; body_vs_average = body / the average body of the last `average` "
                 "candles (this one included, as TradingView's ta.sma); body_share_of_range = body / (high - low)."),
    interpretation=("What the last candle did: a strong green candle has body_vs_average above 1 (bigger than usual). "
                    "Descriptive; one candle says little on its own."),
    limitations="One candle is noisy, and gaps between sessions (shares) make the previous close less comparable.",
)
def candle_shape(ctx, timeframe, params):
    n = params["average"]
    frame, loaded, failed = closed_candles(ctx, timeframe, n + 2)
    if failed:
        return failed
    o, c, h, l = (_num(frame[k].iloc[-1]) for k in ("open", "close", "high", "low"))
    prev = _num(frame["close"].iloc[-2])
    if None in (o, c, h, l, prev):
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["The candle is incomplete."])
    bodies = (frame["close"] - frame["open"]).abs()
    avg_body = _num(bodies.rolling(n).mean().iloc[-1])
    body = abs(c - o)
    value = {
        "colour": "green" if c > o else "red" if c < o else "flat",
        "close_vs_previous": "higher" if c > prev else "lower" if c < prev else "same",
        "change_pct": _r((c - prev) / prev * 100) if prev else None,
        "body_vs_average": _r(body / avg_body) if avg_body else None,
        "body_share_of_range": _r(body / (h - l)) if h > l else None,
    }
    return _ok(ctx, loaded, timeframe, frame, value, {"open": o, "close": c, "previous_close": prev,
                                                       "average_body": _r(avg_body), "average_of": n})


# ----------------------------------------------------------------------------------------------- volatility

@signal(
    id="volatility.atr_trend", version=1, name="Volatility vs its average (ATR)", category="regime",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"length": Param(14, "int", 2, 100, doc="candles in the ATR (Wilder's average of the true range)"),
            "average": Param(20, "int", 2, 200, doc="candles in the average ATR it is compared with")},
    calculation=("On the last closed candle: atr = ATR(`length`) as TradingView's ta.atr (Wilder's average of the true "
                 "range); atr_pct = ATR as % of the close; ratio = ATR / its simple average over `average` candles; "
                 "expanding = yes when the ratio is above 1 (ATR above its average)."),
    interpretation="Whether the asset is moving more than it has lately (expanding) or less. Descriptive.",
    limitations="A single large candle lifts ATR for a while; ratios near 1 flip back and forth.",
)
def atr_trend(ctx, timeframe, params):
    length, n = params["length"], params["average"]
    frame, loaded, failed = closed_candles(ctx, timeframe, length * 3 + n)
    if failed:
        return failed
    atr = wilder_atr(frame, length)
    a, mean = _num(atr.iloc[-1]), _num(atr.rolling(n).mean().iloc[-1])
    close = _num(frame["close"].iloc[-1])
    if None in (a, mean, close) or not mean:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["ATR is not ready yet."])
    value = {"atr": _r(a), "atr_pct": _r(a / close * 100) if close else None, "ratio": _r(a / mean),
             "expanding": bool(a > mean)}
    return _ok(ctx, loaded, timeframe, frame, value, {"length": length, "average_of": n, "average_atr": _r(mean)})
