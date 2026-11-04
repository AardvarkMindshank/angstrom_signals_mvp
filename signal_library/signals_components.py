"""
The ten readings behind Trend, Stretch and Flow, as Signal Library signals (docs/design/library_completion.md).

Each signal reports its native measurement (an RSI of 63, a position within the Bollinger bands) and one extra
field, `standard_score`: the same reading on -1..+1 exactly as the dashboard's Trend, Stretch and Flow compute it.
The calculation is not repeated here: it calls the component functions in signals_v2, which stay the single
source of truth. Starter Groups (signal_groups/starters/trend.json, stretch.json, flow.json) average the standard
scores and reproduce the dashboard's readings on the same input data.

On timeframes other than 1D the standard score keeps the daily definitions' scaling; it is labelled as
daily-derived, not calibrated for that timeframe.
"""

from __future__ import annotations

import math

import signals_v2 as v2

from .core import CONFIRMED, INSUFFICIENT, OBSERVATION, OK, SCOPE_ASSET, TIMEFRAMES, SignalDefinition, SignalResult, REGISTRY
from .signals_basic import YAHOO, _num, bar_times, closed_candles

MIN_CANDLES = 15     # signals_v2 needs at least 15 completed bars
DAILY_ONLY_NOTE = ("Standard score uses daily-derived scaling (the dashboard's daily definitions); it is not "
                   "calibrated for this timeframe.")
STANDARD_TEXT = ("standard_score is the dashboard's {name} component for this candle, on -1..+1 (positive = up or "
                 "stretched up), computed by signals_v2.{fn} (definitions fingerprint recorded in the evidence).")


def _r(x, digits=6):
    x = _num(x)
    return None if x is None else round(x, digits)


def _natives_ma(row, frame, readings):
    close, atr = _num(row.get("close")), _num(row.get("atr"))
    out = {"close": close}
    for n in v2.DEFINITIONS["ma_lengths"]:
        sma = _num(row.get(f"sma_{n}"))
        out[f"sma_{n}"] = sma
        out[f"vs_sma_{n}_pct"] = _r(readings.get(f"vs_sma_{n}_pct"))
        out[f"distance_atr_{n}"] = _r((close - sma) / atr) if None not in (close, sma) and atr else None
    return out, out.get("vs_sma_50_pct")


def _natives_ichimoku(row, frame, readings):
    close, atr = _num(row.get("close")), _num(row.get("atr"))
    a, b = _num(row.get("ichi_span_a")), _num(row.get("ichi_span_b"))
    t, k = _num(row.get("ichi_tenkan")), _num(row.get("ichi_kijun"))
    outside = None
    if None not in (a, b, close) and atr:
        top, bottom = max(a, b), min(a, b)
        outside = _r((close - top if close > top else close - bottom if close < bottom else 0.0) / atr)
    out = {"cloud": readings.get("cloud"), "outside_cloud_atr": outside,
           "tenkan_kijun_gap_atr": _r((t - k) / atr) if None not in (t, k) and atr else None,
           "span_a": a, "span_b": b, "tenkan": t, "kijun": k, "close": close}
    return out, out["cloud"]


def _natives_macd(row, frame, readings):
    atr = _num(row.get("atr"))
    line = readings.get("macd")
    out = {"macd_line": _r(line), "macd_line_atr": _r(line / atr) if line is not None and atr else None}
    return out, out["macd_line"]


def _natives_macd_accel(row, frame, readings):
    atr = _num(row.get("atr"))
    hist = readings.get("macd_histogram")
    out = {"histogram": _r(hist), "histogram_quarter_atr": _r(hist / (atr * v2.DEFINITIONS["macd_accel_scale_atr"])) if hist is not None and atr else None}
    return out, out["histogram"]


def _natives_momentum(row, frame, readings):
    change, atr_pct = readings.get("change_7d"), readings.get("atr_pct")
    expected = atr_pct * math.sqrt(v2.DEFINITIONS["momentum_days"]) if atr_pct else None
    out = {"change_7d_pct": _r(change), "atr_pct": _r(atr_pct), "expected_7d_move_pct": _r(expected),
           "move_in_expected_units": _r(change / expected) if change is not None and expected else None}
    return out, out["change_7d_pct"]


def _natives_rsi(row, frame, readings):
    return {"rsi": _r(readings.get("rsi"))}, readings.get("rsi")


def _natives_stoch(row, frame, readings):
    return {"stoch_k": _r(readings.get("stoch_k"))}, readings.get("stoch_k")


def _natives_bollinger(row, frame, readings):
    up, lo = v2._col(frame, "BBU_"), v2._col(frame, "BBL_")
    out = {"position": _r(readings.get("bb_position")), "upper": _num(row.get(up)) if up else None,
           "lower": _num(row.get(lo)) if lo else None, "close": _num(row.get("close"))}
    return out, out["position"]


def _natives_obv(row, frame, readings):
    obv, avg, vol = _num(row.get("obv")), _num(row.get("obv_sma_20")), _num(row.get("vol_sma_20"))
    scale = vol * math.sqrt(v2.DEFINITIONS["obv_scale_sqrt_days"]) if vol else None
    out = {"obv": obv, "obv_average_20": avg, "has_volume": bool(vol and vol > 0),
           "balance_in_scaled_volumes": _r((obv - avg) / scale) if None not in (obv, avg) and scale else None}
    return out, out["balance_in_scaled_volumes"]


def _natives_heavy(row, frame, readings):
    o, h, l, c = (_num(row.get(k)) for k in ("open", "high", "low", "close"))
    ratio = readings.get("volume_ratio")
    span = (h - l) if None not in (h, l) else None
    body = ((c - o) / span if span > 0 else 0.0) if None not in (o, c) and span is not None else None
    heavy = (max(0.0, min(1.0, (ratio - 1.0) / (v2.DEFINITIONS["heavy_volume_full_at"] - 1.0)))
             if ratio is not None else None)
    out = {"volume_ratio": _r(ratio), "body_share_of_range": _r(body), "heaviness": _r(heavy)}
    return out, out["volume_ratio"]


SPECS = (
    # id, component, natives, name, category, unit, calculation, interpretation, limitations
    ("ma.position", "moving_averages", _natives_ma, "Moving averages (50, 200)", "trend", "% and ATRs",
     "Close against the 50- and 200-candle simple moving averages: the gap in % and in ATR(14) units.",
     "How far price sits above or below its longer averages. The standard score (dashboard Trend part) averages "
     "tanh(distance / (ATR x 0.5 x sqrt(length))) over the two averages.",
     "Averages lag. Without 200 candles of history only the 50 is used."),
    ("ichimoku.position", "ichimoku", _natives_ichimoku, "Ichimoku cloud position", "trend", "label and ATRs",
     "Close above, inside or below the Ichimoku cloud; the distance outside it and the Tenkan-Kijun gap, in ATR(14).",
     "Where price sits relative to the cloud. The standard score (dashboard Trend part) is 0 inside the cloud and "
     "grows with distance outside it, averaged with the Tenkan-Kijun gap (both scaled by 3 ATRs).",
     "The cloud is plotted 26 candles ahead from past prices; it needs about 78 candles of history."),
    ("macd.level", "macd", _natives_macd, "MACD line", "trend", "price and ATRs",
     "MACD(12, 26) line: the 12-candle EMA minus the 26-candle EMA, and the same in ATR(14) units.",
     "Whether the shorter average is above the longer one, and by how much. Standard score (dashboard Trend part): "
     "tanh(line / ATR).",
     "EMAs depend slightly on how much history was loaded."),
    ("macd.acceleration", "macd_acceleration", _natives_macd_accel, "MACD histogram", "momentum", "price and ATRs",
     "MACD histogram (line minus its 9-candle signal), and the same in quarter-ATR units.",
     "Whether momentum is speeding up or slowing. Standard score (dashboard Stretch part): tanh(histogram / (ATR/4)).",
     "Turns often in ranges."),
    ("move.seven_day", "momentum", _natives_momentum, "7-candle move", "momentum", "% and expected moves",
     "Close-to-close change over 7 candles, and the same change in units of the expected move (ATR% x sqrt(7)).",
     "How large the recent move is for this asset. Standard score (dashboard Stretch part): tanh(change / expected).",
     "On daily candles this is the 7-day move; on other timeframes it is 7 of those candles."),
    ("rsi.level", "rsi", _natives_rsi, "RSI (14)", "momentum", "0-100",
     "Relative Strength Index over 14 candles.",
     "How strongly recent closes have risen versus fallen. Standard score (dashboard Stretch part): "
     "(RSI - 50) / 30, clipped to -1..+1 (80 = +1, 20 = -1).",
     "Stays stretched for long periods in strong trends."),
    ("stochastic.level", "stochastic", _natives_stoch, "Stochastic %K (14, 3)", "momentum", "0-100",
     "Stochastic %K: where the close sits within the 14-candle high-low range, smoothed.",
     "Near 100: closing near recent highs. Standard score (dashboard Stretch part): (%K - 50) / 50.",
     "Very sensitive in ranges; reaches extremes easily."),
    ("bollinger.position", "bollinger", _natives_bollinger, "Bollinger position (20, 2)", "momentum",
     "0 = lower band, 1 = upper band",
     "Where the close sits between the 20-candle Bollinger bands (2 standard deviations).",
     "Near 1: at the upper band. Standard score (dashboard Stretch part): tanh(2 x (position - 0.5)).",
     "Bands widen in volatile periods, so the same position means a different move."),
    ("obv.balance", "obv", _natives_obv, "On-balance volume balance", "volume", "scaled volumes",
     "On-balance volume minus its 20-candle average, in average-candle volumes x sqrt(20).",
     "Whether volume has recently come on up-candles or down-candles. Standard score (dashboard Flow part): "
     "tanh(balance).",
     "Needs a source with real volume; crypto volume differs by venue."),
    ("volume.heavy_candle", "heavy_volume", _natives_heavy, "Heavy-volume candle", "volume", "ratio and share",
     "The last candle's volume against its 20-candle average, its body as a share of its range, and how heavy it "
     "counts (1x average = 0, 2x or more = 1).",
     "A big candle on big volume. Standard score (dashboard Flow part): heaviness x body share, clipped to -1..+1.",
     "One candle only; needs real volume."),
)


def _make(spec):
    signal_id, component, natives, name, category, unit, calculation, interpretation, limitations = spec
    fn = v2.COMPONENT_FUNCTIONS[component]

    def compute(ctx, timeframe, params):
        frame, loaded, failed = closed_candles(ctx, timeframe, MIN_CANDLES)
        if failed:
            return failed
        row = frame.iloc[-1]
        score, readings = fn(row, frame)
        value, primary = natives(row, frame, readings)
        if score is None and primary is None:
            return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT,
                                notes=[f"{name}: inputs not available on the last closed candle."])
        value = {**value, "standard_score": score}
        observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
        notes = [] if timeframe == "1D" else [DAILY_ONLY_NOTE]
        if score is None:
            notes.append("No standard score: an input it needs (ATR, volume or a band) is missing.")
        return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=value,
                            observed_at=observed, available_at=available,
                            evidence={"component": component, "definitions_fingerprint": v2.FINGERPRINT,
                                      "definitions_version": v2.VERSION},
                            provenance=[loaded.get("source") or YAHOO], notes=notes)

    compute.__name__ = signal_id.replace(".", "_")
    REGISTRY.register(SignalDefinition(
        id=signal_id, version=1, name=name, category=category, output=OBSERVATION, unit=unit, scope=SCOPE_ASSET,
        timeframes=TIMEFRAMES, requires=("candles",), compute=compute,
        calculation=calculation + " " + STANDARD_TEXT.format(name=name, fn=fn.__name__),
        interpretation=interpretation + " Descriptive; not a forecast.",
        limitations=limitations + " On timeframes other than 1D the standard score is daily-derived scaling.",
        polarity="standard_score positive = up / stretched up / volume backing rises",
    ))


for _spec in SPECS:
    _make(_spec)

COMPONENT_SIGNALS = {spec[1]: spec[0] for spec in SPECS}   # v2 component -> signal id
