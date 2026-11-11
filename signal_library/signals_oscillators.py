"""
Momentum oscillators in the style Drew reads (asked 10 Nov 2026; his charts: docs/research/drew_charts_2026-11-10.md),
with the openly published formulas and default settings of LazyBear's WaveTrend and its open-source "Market Cipher B"
recreation (VuManChu Cipher B). Every setting is a parameter, so his own settings can be matched later without a
rebuild.

* osc.wavetrend       WaveTrend: the wave (WT1) and its signal line (WT2), overbought/oversold bands, a cross, and a
                      turn from an extreme (his yellow arrows: WT1 crossing WT2 while oversold or overbought);
* flow.money          money flow, the RSI/MFI-style area: the candle's close-minus-open over its range, averaged
                      (green above zero = money flowing in, red below = flowing out);
* osc.stoch_ohlc4     the Stochastic computed on OHLC4 ((open + high + low + close) / 4), as he uses it;
* divergence.mtf      regular and hidden divergence between price swings and WaveTrend (or RSI) swings, counted
                      across several timeframes ("bullish divergence on 3 of 4").

Closed candles only. Descriptive readings, not forecasts; nothing is tuned on outcomes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import swings as sw
from .core import (CONFIRMED, INSUFFICIENT, OBSERVATION, OK, SCOPE_ASSET, TIMEFRAMES, Param, SignalResult,
                   signal)
from .signals_basic import YAHOO, _num, bar_times, closed_candles


def _ok(ctx, loaded, timeframe, frame, value, evidence, notes=None):
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=value,
                        observed_at=observed, available_at=available, evidence=evidence,
                        provenance=[loaded.get("source") or YAHOO], notes=notes or [])


def _r(x, digits=4):
    x = _num(x)
    return None if x is None else round(x, digits)


def ema(series: pd.Series, length: int) -> pd.Series:
    """TradingView's ta.ema (alpha 2/(n+1), started from the first value)."""
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


# ----------------------------------------------------------------------------------------------- WaveTrend

def wavetrend(frame: pd.DataFrame, channel: int = 9, average: int = 12, signal_len: int = 3) -> pd.DataFrame:
    """WT1 and WT2 as LazyBear's WaveTrend (and VuManChu Cipher B): ap = hlc3; esa = ema(ap, channel);
    d = ema(|ap - esa|, channel); ci = (ap - esa) / (0.015 d); WT1 = ema(ci, average); WT2 = sma(WT1, signal)."""
    ap = (frame["high"] + frame["low"] + frame["close"]) / 3
    esa = ema(ap, channel)
    d = ema((ap - esa).abs(), channel)
    ci = (ap - esa) / (0.015 * d.replace(0, np.nan))
    wt1 = ema(ci, average)
    wt2 = wt1.rolling(signal_len, min_periods=signal_len).mean()
    return pd.DataFrame({"wt1": wt1, "wt2": wt2}, index=frame.index)


WT_PARAMS = {
    "channel": Param(9, "int", 2, 50, doc="channel length (the EMA of price and of its distance)"),
    "average": Param(12, "int", 2, 60, doc="average length (smooths the wave, WT1)"),
    "signal": Param(3, "int", 2, 20, doc="signal line length (WT2 = simple average of WT1)"),
    "overbought": Param(53, "int", 20, 100, doc="overbought line (Market Cipher B: 53; a stronger line at 60)"),
    "oversold": Param(-53, "int", -100, -20, doc="oversold line (Market Cipher B: -53; a stronger line at -60)"),
}


@signal(
    id="osc.wavetrend", version=1, name="WaveTrend momentum (Market Cipher style)", category="momentum",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params=WT_PARAMS,
    calculation=("LazyBear's WaveTrend on the last closed candle: ap = (high + low + close) / 3; esa = EMA(ap, channel); "
                 "d = EMA(|ap - esa|, channel); ci = (ap - esa) / (0.015 x d); WT1 = EMA(ci, average); WT2 = SMA(WT1, "
                 "signal). zone = overbought when WT2 is at or above the overbought line, oversold at or below the "
                 "oversold line, else neutral. cross = up when WT1 moved above WT2 on this candle, down when below. "
                 "turned_up_from_oversold = a cross up while WT2 is at or below the oversold line (Market Cipher's "
                 "green dot); turned_down_from_overbought the mirror (red dot). Defaults are Market Cipher B's."),
    interpretation=("Where the momentum wave is and whether it just turned. A turn up from oversold is what many "
                    "traders mark as a possible bounce point, to be read with the trend and other timeframes. "
                    "Descriptive; not a forecast."),
    limitations=("Oscillators stay overbought or oversold for long stretches in strong trends, and turns repeat. "
                 "Needs about 50 closed candles. Settings change the readings; the defaults follow the published "
                 "Market Cipher B recreation, not any one trader's chart."),
)
def osc_wavetrend(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 4 * (params["channel"] + params["average"]) + 10)
    if failed:
        return failed
    wt = wavetrend(frame, params["channel"], params["average"], params["signal"])
    w1, w2, p1, p2 = (_num(x) for x in (wt["wt1"].iloc[-1], wt["wt2"].iloc[-1], wt["wt1"].iloc[-2],
                                        wt["wt2"].iloc[-2]))
    if None in (w1, w2, p1, p2):
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["WaveTrend is not ready yet."])
    ob, os_ = params["overbought"], params["oversold"]
    cross = "up" if p1 <= p2 and w1 > w2 else "down" if p1 >= p2 and w1 < w2 else "none"
    value = {
        "wt1": _r(w1), "wt2": _r(w2),
        "zone": "overbought" if w2 >= ob else "oversold" if w2 <= os_ else "neutral",
        "cross": cross,
        "turned_up_from_oversold": bool(cross == "up" and w2 <= os_),
        "turned_down_from_overbought": bool(cross == "down" and w2 >= ob),
        "direction": "rising" if w1 > p1 else "falling" if w1 < p1 else "flat",
    }
    return _ok(ctx, loaded, timeframe, frame, value, {**params, "previous_wt1": _r(p1), "previous_wt2": _r(p2)})


# ----------------------------------------------------------------------------------------------- money flow

def money_flow(frame: pd.DataFrame, period: int = 60, multiplier: float = 150.0, shift: float = 2.5) -> pd.Series:
    """VuManChu Cipher B's money flow ("RSI+MFI area"): SMA(((close - open) / (high - low)) x multiplier, period)
    - shift. Positive = closes above opens on balance (money flowing in)."""
    rng = (frame["high"] - frame["low"]).replace(0, np.nan)
    raw = ((frame["close"] - frame["open"]) / rng * multiplier).fillna(0.0)
    return raw.rolling(period, min_periods=period).mean() - shift


@signal(
    id="flow.money", version=1, name="Money flow (Market Cipher style)", category="volume",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"period": Param(60, "int", 5, 200, doc="candles averaged"),
            "multiplier": Param(150, "int", 10, 500, doc="scale (Market Cipher B: 150)")},
    calculation=("On the last closed candle: value = the simple average over `period` candles of ((close - open) / "
                 "(high - low)) x multiplier, less 2.5 (VuManChu Cipher B's money-flow area). direction = in when the "
                 "value is above zero, out when below. rising = higher than one candle before."),
    interpretation=("Whether candles have, on balance, been closing above their opens (money flowing in, green) or "
                    "below (flowing out, red), and whether that is growing. Agreement or disagreement across "
                    "timeframes is how it is usually read. Descriptive."),
    limitations=("Built from candle shapes only; it does not see order flow or exchange volumes. A doji (open = close) "
                 "counts as nothing. Slow by design (60 candles)."),
)
def flow_money(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, params["period"] + 2)
    if failed:
        return failed
    mf = money_flow(frame, params["period"], float(params["multiplier"]))
    v, prev = _num(mf.iloc[-1]), _num(mf.iloc[-2])
    if v is None:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["Money flow is not ready yet."])
    value = {"value": _r(v), "direction": "in" if v > 0 else "out" if v < 0 else "flat",
             "rising": None if prev is None else bool(v > prev)}
    return _ok(ctx, loaded, timeframe, frame, value, {**params, "previous": _r(prev)})


# ----------------------------------------------------------------------------------------------- Stochastic (OHLC4)

def stoch_ohlc4(frame: pd.DataFrame, length: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> pd.DataFrame:
    """%K = SMA(100 x (src - lowest low) / (highest high - lowest low), smooth_k) with src = OHLC4; %D = SMA(%K)."""
    src = (frame["open"] + frame["high"] + frame["low"] + frame["close"]) / 4
    lo = frame["low"].rolling(length, min_periods=length).min()
    hi = frame["high"].rolling(length, min_periods=length).max()
    raw = 100 * (src - lo) / (hi - lo).replace(0, np.nan)
    k = raw.rolling(smooth_k, min_periods=smooth_k).mean()
    return pd.DataFrame({"k": k, "d": k.rolling(smooth_d, min_periods=smooth_d).mean()}, index=frame.index)


@signal(
    id="osc.stoch_ohlc4", version=1, name="Stochastic on OHLC4", category="momentum",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"length": Param(14, "int", 3, 100, doc="candles in the high-low range"),
            "smooth_k": Param(3, "int", 1, 20, doc="smoothing of %K"),
            "smooth_d": Param(3, "int", 1, 20, doc="%D: the average of %K"),
            "overbought": Param(80, "int", 50, 100, doc="overbought line"),
            "oversold": Param(20, "int", 0, 50, doc="oversold line")},
    calculation=("On the last closed candle, with src = (open + high + low + close) / 4: %K = SMA(100 x (src - lowest "
                 "low) / (highest high - lowest low), smooth_k) over `length` candles; %D = SMA(%K, smooth_d). zone = "
                 "overbought at or above the line, oversold at or below; cross = %K crossing %D on this candle; "
                 "turned_up_from_oversold = a cross up with %D at or below the oversold line (mirror for overbought)."),
    interpretation="Where the candle's average price sits in its recent range, smoothed, and whether it just turned. "
                   "Descriptive.",
    limitations="Stays pinned near 0 or 100 in strong trends; turns repeat in sideways markets.",
)
def osc_stoch_ohlc4(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, params["length"] + params["smooth_k"] + params["smooth_d"] + 2)
    if failed:
        return failed
    st = stoch_ohlc4(frame, params["length"], params["smooth_k"], params["smooth_d"])
    k, d, pk, pd_ = (_num(x) for x in (st["k"].iloc[-1], st["d"].iloc[-1], st["k"].iloc[-2], st["d"].iloc[-2]))
    if None in (k, d, pk, pd_):
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["The Stochastic is not ready."])
    cross = "up" if pk <= pd_ and k > d else "down" if pk >= pd_ and k < d else "none"
    ob, os_ = params["overbought"], params["oversold"]
    value = {"k": _r(k, 2), "d": _r(d, 2), "zone": "overbought" if k >= ob else "oversold" if k <= os_ else "neutral",
             "cross": cross, "turned_up_from_oversold": bool(cross == "up" and d <= os_),
             "turned_down_from_overbought": bool(cross == "down" and d >= ob)}
    return _ok(ctx, loaded, timeframe, frame, value, {**params})


# ----------------------------------------------------------------------------------------------- divergence across timeframes

MTF_DIV_SETS = {
    "crypto": ("1D", "12h", "4h", "1h"),
    "equity": ("1W", "1D", "4h", "1h"),
    "intraday": ("4h", "1h", "30m", "15m"),
}


def _wt_series(frame: pd.DataFrame) -> pd.Series:
    return wavetrend(frame)["wt2"]


def _rsi_series(frame: pd.DataFrame, length: int = 14) -> pd.Series:
    delta = frame["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


@signal(
    id="divergence.mtf", version=1, name="Divergence across timeframes", category="momentum",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=("1D",), requires=("candles",),
    params={"set": Param("crypto", "choice", choices=tuple(MTF_DIV_SETS),
                         doc="timeframes: crypto = daily, 12h, 4h, 1h; equity = weekly, daily, 4h, 1h; intraday = "
                             "4h, 1h, 30m, 15m"),
            "oscillator": Param("wavetrend", "choice", choices=("wavetrend", "rsi"),
                                doc="the momentum line compared with price swings"),
            "active_bars": Param(10, "int", 3, 60, doc="candles a confirmed divergence counts as recent")},
    calculation=("On each timeframe of the set, at its last closed candle: confirmed divergences between consecutive "
                 "price swings (5 candles each side) and the oscillator's swings (WaveTrend WT2, or RSI 14), as the "
                 "library's RSI divergence finds them; one counts when it was confirmed within the last `active_bars` "
                 "candles and not invalidated. bullish_count = timeframes with a regular or hidden bullish one; "
                 "bearish_count the same for bearish; regular_bullish_count, hidden_bullish_count, "
                 "regular_bearish_count and hidden_bearish_count split them; timeframes_read = timeframes that could be "
                 "read. A timeframe counts once per kind however many it has."),
    interpretation=("How many timeframes show momentum disagreeing with price at once, the multi-timeframe divergence "
                    "Drew looks for. Regular divergence hints at exhaustion, hidden divergence at continuation. "
                    "Descriptive; not a trade signal by itself."),
    limitations=("Swings are confirmed 5 candles late by design. A timeframe that cannot be read is left out of "
                 "timeframes_read, never counted as no divergence. In strong trends regular divergence can repeat many "
                 "times before any turn."),
)
def divergence_mtf(ctx, timeframe, params):
    series = _wt_series if params["oscillator"] == "wavetrend" else _rsi_series
    counts = {"regular_bullish": 0, "hidden_bullish": 0, "regular_bearish": 0, "hidden_bearish": 0}
    rows, read, latest = [], 0, None
    for tf in MTF_DIV_SETS[params["set"]]:
        frame, loaded, failed = closed_candles(ctx, tf, 80)
        if failed:
            rows.append({"timeframe": tf, "status": failed.status, "kinds": []})
            continue
        osc = series(frame)
        found = sw.divergences(frame["high"], frame["low"], frame["close"], osc, 5, 5, 5, 60,
                               active_bars=params["active_bars"])
        recent = [e for e in found["events"] if e["status"] == "confirmed"]
        kinds = sorted({e["type"] for e in recent})
        for kind in kinds:
            if kind in counts:
                counts[kind] += 1
        read += 1
        _obs, available = bar_times(ctx, loaded, tf, frame.index[-1])
        latest = max(latest or available, available)
        rows.append({"timeframe": tf, "status": OK, "kinds": kinds})
    if read == 0:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, evidence={"timeframes": rows},
                            notes=["No timeframe could be read."])
    bull = sum(1 for r in rows if {"regular_bullish", "hidden_bullish"} & set(r["kinds"]))
    bear = sum(1 for r in rows if {"regular_bearish", "hidden_bearish"} & set(r["kinds"]))
    value = {"bullish_count": bull, "bearish_count": bear, "timeframes_read": read,
             **{f"{k}_count": v for k, v in counts.items()},
             "summary": f"Bullish divergence on {bull} of {read} timeframes, bearish on {bear}"}
    frame, loaded, _ = closed_candles(ctx, timeframe, 2)
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1]) if frame is not None else (None, latest)
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=value,
                        observed_at=observed, available_at=max(filter(None, [available, latest])),
                        evidence={"timeframes": rows, **params}, provenance=[YAHOO],
                        notes=[f"{r['timeframe']}: not readable" for r in rows if r["status"] != OK])
