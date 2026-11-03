"""
Priority 1 (and volume) signals on candles: momentum, multi-timeframe alignment, divergences,
market structure, price zones, regime evidence, CMF and relative volume.

Indicator columns come from scoring.calculate_indicators via the DataContext (the same formulas
as the charts and the v2 readings). New formulas here are only those with no existing version:
swing points and everything built on them, Kaufman's efficiency ratio, Bollinger bandwidth
percentile and Chaikin Money Flow. Each is documented in its definition.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import regime as regime_rules

from . import swings as sw
from .core import (
    CONFIRMED, DIRECTION, EVENTS, INSUFFICIENT, LEVELS, NUMERIC, OBSERVATION, OK,
    REGISTRY, SCOPE_ASSET, TIMEFRAMES, Param, SignalRef, SignalResult, iso, signal,
)
from .signals_basic import YAHOO, _num, bar_times, closed_candles

PIVOT_PARAMS = {
    "left": Param(5, "int", 2, 20, doc="bars before a swing point that must be lower (highs) / higher (lows)"),
    "right": Param(5, "int", 2, 20, doc="bars after it needed to confirm it; this is the confirmation delay"),
}


def _col(frame, prefix):
    return next((c for c in frame.columns if str(c).startswith(prefix)), None)


def _when(ctx, loaded, timeframe, frame, index):
    """(candle start, candle close) of a bar index, ISO UTC."""
    return bar_times(ctx, loaded, timeframe, frame.index[int(index)])


def _ok(ctx, loaded, timeframe, frame, value, evidence, confirmation=CONFIRMED, notes=None):
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=confirmation, value=value,
                        observed_at=observed, available_at=available, evidence=evidence,
                        provenance=[loaded.get("source") or YAHOO], notes=list(notes or []))


# ============================================================================ momentum and MTF

@signal(
    id="momentum.direction", version=1, name="Momentum direction", category="momentum",
    output=DIRECTION, unit="label", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    calculation=("On the last closed candle: up when the MACD(12,26,9) histogram is above 0 and RSI(14) is above 50; "
                 "down when the histogram is below 0 and RSI below 50; otherwise mixed. The histogram's change over "
                 "the last 3 candles is shown as evidence (rising/falling)."),
    interpretation="Which way short-term momentum points on this timeframe, separate from the moving-average trend.",
    limitations="Momentum turns early and often; in ranges it flips back and forth.",
    polarity="up = momentum rising", max_age_bars=3,
)
def momentum_direction(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 40)
    if failed:
        return failed
    hist_col = _col(frame, "MACDh_")
    if not hist_col or "rsi" not in frame.columns:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["MACD or RSI not available."])
    hist, rsi = frame[hist_col], frame["rsi"]
    h, r = _num(hist.iloc[-1]), _num(rsi.iloc[-1])
    if h is None or r is None:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["MACD or RSI not settled yet."])
    value = "up" if h > 0 and r > 50 else "down" if h < 0 and r < 50 else "mixed"
    slope = _num(hist.iloc[-1] - hist.iloc[-4]) if len(hist) >= 4 else None
    return _ok(ctx, loaded, timeframe, frame, value, {
        "macd_histogram": h, "rsi": r, "histogram_change_3": slope,
        "histogram_trend": None if slope is None else ("rising" if slope > 0 else "falling" if slope < 0 else "flat"),
    })


MTF_SETS = {
    "all": ("15m", "1h", "4h", "1D", "1W"),
    "intraday": ("15m", "1h", "4h"),
    "swing": ("1h", "4h", "1D"),
    "position": ("4h", "1D", "1W"),
}


@signal(
    id="mtf.alignment", version=1, name="Multi-timeframe alignment", category="trend",
    output=OBSERVATION, unit="per-timeframe labels", scope=SCOPE_ASSET, timeframes=("1D",),
    requires=("candles", "signals"),
    calculation=("Evaluates trend.direction@1 and momentum.direction@1 on each timeframe of the chosen set and lists "
                 "them side by side, with counts of up/down/mixed, the timeframes whose trend disagrees with the "
                 "next larger one, and the timeframes where momentum opposes trend (possible transition)."),
    interpretation=("Shows where timeframes agree and where they conflict. There is deliberately no single alignment "
                    "score: agreement is descriptive, not evidence of a future move."),
    limitations=("Intraday candles come from Yahoo (15m: about 60 days, 1h/4h: about 2 years). A timeframe that cannot "
                 "be loaded is listed as missing, not dropped silently. Trend and momentum share price inputs, so they "
                 "are not independent confirmations."),
    params={"set": Param("all", "choice", choices=tuple(MTF_SETS), doc="which timeframes to compare")},
)
def mtf_alignment(ctx, timeframe, params):
    from .engine import evaluate

    rows, latest_close = [], None
    for tf in MTF_SETS[params["set"]]:
        t_ref = SignalRef.make(REGISTRY.get("trend.direction", 1), tf)
        m_ref = SignalRef.make(REGISTRY.get("momentum.direction", 1), tf)
        got = evaluate([t_ref, m_ref], ctx)
        t, m = got[t_ref.instance_key], got[m_ref.instance_key]
        rows.append({"timeframe": tf, "trend": t.value if t.status == OK else None,
                     "momentum": m.value if m.status == OK else None,
                     "status": t.status if t.status != OK else m.status,
                     "observed_at": t.observed_at, "trend_evidence": t.evidence, "momentum_evidence": m.evidence,
                     "notes": t.notes + m.notes})
        if t.available_at and (latest_close is None or t.available_at > latest_close):
            latest_close = t.available_at
    usable = [r for r in rows if r["trend"]]
    if len(usable) < 2:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, evidence={"timeframes": rows},
                            notes=["Fewer than two timeframes could be read."])
    counts = {k: sum(r["trend"] == k for r in usable) for k in ("up", "down", "mixed")}
    conflicts = []
    for small, big in zip(usable, usable[1:]):
        if {small["trend"], big["trend"]} == {"up", "down"}:
            conflicts.append(f"{small['timeframe']} trend {small['trend']} vs {big['timeframe']} {big['trend']}")
    transitions = [r["timeframe"] for r in usable
                   if {r["trend"], r["momentum"]} == {"up", "down"}]
    summary = f"Trend up on {counts['up']} of {len(usable)}, down on {counts['down']}, mixed on {counts['mixed']}"
    return SignalResult(
        ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED,
        value={"timeframes": [{k: r[k] for k in ("timeframe", "trend", "momentum", "status")} for r in rows],
               "trend_counts": counts, "conflicts": conflicts, "momentum_against_trend": transitions,
               "summary": summary},
        observed_at=max((r["observed_at"] for r in usable if r["observed_at"]), default=None),
        available_at=latest_close, evidence={"timeframes": rows},
        provenance=[YAHOO], notes=[r["timeframe"] + ": " + "; ".join(r["notes"]) for r in rows if r["notes"]],
    )


# ============================================================================ divergences

def _divergence(ctx, timeframe, params, osc_name, osc_series_fn):
    frame, loaded, failed = closed_candles(ctx, timeframe, 60)
    if failed:
        return failed
    osc = osc_series_fn(frame)
    if osc is None or osc.dropna().empty:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=[f"{osc_name} not available."])
    found = sw.divergences(frame["high"], frame["low"], frame["close"], osc, params["left"], params["right"],
                           params["min_gap"], params["max_gap"], active_bars=params["active_bars"])
    lookback_start = max(0, len(frame) - params["lookback"])

    def stamp(event):
        out = dict(event)
        out["price_pivots"] = [{**p, "time": iso(frame.index[p["index"]])} for p in event["price_pivots"]]
        out["indicator_pivots"] = [{**p, "time": iso(frame.index[p["index"]])} for p in event["indicator_pivots"]]
        if "confirmed_index" in event:
            out["confirmed_at"] = _when(ctx, loaded, timeframe, frame, event["confirmed_index"])[1]
        if event.get("invalidated_index") is not None:
            out["invalidated_at"] = _when(ctx, loaded, timeframe, frame, event["invalidated_index"])[1]
        if "expires_index" in event:
            n = len(frame)
            out["active_window_candles"] = params["active_bars"]
            out["expires_after_candles"] = event["expires_index"] - (n - 1) if event["expires_index"] > n - 1 else 0
            if event["status"] == "expired":
                out["expired_at"] = _when(ctx, loaded, timeframe, frame, event["expires_index"])[1]
        for key in ("confirmed_index", "invalidated_index", "expires_index"):
            out.pop(key, None)
        for p in out["price_pivots"] + out["indicator_pivots"]:
            p.pop("index", None)
        return out

    recent = [stamp(e) for e in found["events"] if e["confirmed_index"] >= lookback_start]
    developing = [stamp(e) for e in found["developing"]]
    active = [e for e in recent if e["status"] == "confirmed"]
    value = {"events": recent, "active": active[-4:], "developing": developing}
    return _ok(ctx, loaded, timeframe, frame, value,
               {"oscillator": osc_name, "candles_scanned": len(frame) - lookback_start, "swing_rule": params},
               notes=["Developing divergences can still disappear; they are listed separately."] if developing else [])


DIV_PARAMS = {
    **PIVOT_PARAMS,
    "min_gap": Param(5, "int", 2, 50, doc="fewest bars between the two swings"),
    "max_gap": Param(60, "int", 10, 200, doc="most bars between the two swings"),
    "lookback": Param(150, "int", 20, 1000, doc="candles back to report confirmed divergences"),
    "active_bars": Param(30, "int", 5, 200, doc="candles a confirmed divergence stays active before it expires"),
}
DIV_TEXT = dict(
    output=EVENTS, unit="events", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",), category="momentum",
    interpretation=("Regular divergence: price makes a new extreme the indicator does not confirm (possible exhaustion). "
                    "Hidden divergence: price holds a higher low / lower high while the indicator overshoots (possible "
                    "continuation). Each event lists the price and indicator swing points, when it was confirmed, the "
                    "confirmation delay and the price that invalidates it. Not a trade signal by itself."),
    limitations=("Confirmation needs `right` closed candles after the swing, so events arrive late by design. In strong "
                 "trends regular divergences can repeat many times before any turn. Swing settings change what counts."),
    polarity="bullish types point up, bearish types point down (descriptive)",
)


@signal(id="ta.divergence.rsi", version=1, name="RSI divergence", params=DIV_PARAMS, **DIV_TEXT, calculation=(
    "Confirmed swing lows/highs (pivot rule, left/right bars). For consecutive swings of the same kind, min_gap..max_gap "
    "bars apart, take RSI(14)'s lowest/highest value within 2 bars of each swing (never past the confirmation bar). "
    "Regular bullish: lower price low, higher RSI low. Hidden bullish: higher price low, lower RSI low. Regular bearish: "
    "higher price high, lower RSI high. Hidden bearish: lower price high, higher RSI high. Confirmed when the second "
    "swing is confirmed; invalidated by a close beyond the second swing's price within the next active_bars "
    "candles, otherwise expired after active_bars candles (active until then)."))
def divergence_rsi(ctx, timeframe, params):
    return _divergence(ctx, timeframe, params, "RSI(14)", lambda f: f["rsi"] if "rsi" in f.columns else None)


@signal(id="ta.divergence.macd", version=1, name="MACD divergence", params={
    **DIV_PARAMS, "line": Param("histogram", "choice", choices=("histogram", "macd"),
                                 doc="compare price with the MACD histogram or the MACD line")},
    **DIV_TEXT, calculation=(
    "As RSI divergence, with the MACD(12,26,9) histogram (default) or MACD line in place of RSI."))
def divergence_macd(ctx, timeframe, params):
    prefix = "MACDh_" if params["line"] == "histogram" else "MACD_"
    name = "MACD histogram" if params["line"] == "histogram" else "MACD line"
    return _divergence(ctx, timeframe, params, name, lambda f: f[_col(f, prefix)] if _col(f, prefix) else None)


# ============================================================================ structure and zones

@signal(
    id="structure.swings", version=1, name="Market structure", category="structure",
    output=OBSERVATION, unit="price", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={**PIVOT_PARAMS, "count": Param(6, "int", 2, 30, doc="recent confirmed swings to list")},
    calculation=("Confirmed swing highs and lows (pivot rule). Each is labelled against the previous swing of the same "
                 "kind: HH/LH for highs, HL/LL for lows (EH/EL when equal). Structure is up when the latest high is HH "
                 "and the latest low HL, down for LH and LL, otherwise mixed. The current unconfirmed extremes are "
                 "listed separately as tentative swings."),
    interpretation="The sequence of confirmed swing points and what they say about structure on this timeframe.",
    limitations="Swings are confirmed `right` candles late. Small swing settings give noisy structure on low timeframes.",
)
def structure_swings(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 30)
    if failed:
        return failed
    labelled = sw.label_swings(sw.pivots(frame["high"], frame["low"], params["left"], params["right"]))
    if len([p for p in labelled if p["label"]]) < 2:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["Too few confirmed swings."])
    state = sw.structure_state(labelled)
    recent = [{"kind": p["kind"], "label": p["label"], "price": p["price"], "time": iso(frame.index[p["index"]]),
               "confirmed_at": _when(ctx, loaded, timeframe, frame, p["confirmed_index"])[1]}
              for p in labelled[-params["count"]:]]
    tentative = []
    for kind in ("high", "low"):
        cand = sw.candidate(frame["high"], frame["low"], kind, params["left"], params["right"])
        if cand:
            tentative.append({"kind": kind, "price": cand["price"], "time": iso(frame.index[cand["index"]]),
                              "bars_to_confirm": cand["bars_to_confirm"]})
    last_high = next((p for p in reversed(labelled) if p["kind"] == "high"), None)
    last_low = next((p for p in reversed(labelled) if p["kind"] == "low"), None)
    close = float(frame["close"].iloc[-1])
    value = {"structure": state, "swings": recent, "tentative": tentative,
             "last_swing_high": last_high and last_high["price"], "last_swing_low": last_low and last_low["price"],
             "close": close}
    return _ok(ctx, loaded, timeframe, frame, value, {"swing_rule": {"left": params["left"], "right": params["right"]},
                                                      "swings_found": len(labelled)})


@signal(
    id="structure.breaks", version=1, name="Structure breaks (BOS / CHoCH)", category="structure",
    output=EVENTS, unit="events", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={**PIVOT_PARAMS, "lookback": Param(150, "int", 20, 1000, doc="candles back to report breaks")},
    calculation=("Walking forward candle by candle with only the swings confirmed before that candle: a close above the "
                 "latest swing high is a bullish break, a close below the latest swing low a bearish break. It is a "
                 "break of structure (BOS) when it continues the existing structure, and a potential change of "
                 "character (CHoCH) when it goes against it. Each swing level counts once."),
    interpretation="Where price closed through recent structure, and whether that continued or challenged it.",
    limitations="A CHoCH is only a potential change; many fail. Wicks through a level without a close do not count.",
    polarity="bullish breaks point up",
)
def structure_breaks(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 30)
    if failed:
        return failed
    events = sw.structure_breaks(frame["high"], frame["low"], frame["close"], params["left"], params["right"])
    start = max(0, len(frame) - params["lookback"])
    out = [{"kind": e["kind"], "direction": e["direction"], "level": e["level"], "structure_before": e["structure_before"],
            "time": iso(frame.index[e["index"]]), "confirmed_at": _when(ctx, loaded, timeframe, frame, e["index"])[1],
            "swing_time": iso(frame.index[e["swing_index"]])}
           for e in events if e["index"] >= start]
    return _ok(ctx, loaded, timeframe, frame, {"events": out, "latest": out[-1] if out else None},
               {"swing_rule": {"left": params["left"], "right": params["right"]}})


@signal(
    id="levels.zones", version=1, name="Support and resistance zones", category="structure",
    output=LEVELS, unit="price", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={**PIVOT_PARAMS,
            "lookback": Param(300, "int", 50, 2000, doc="candles back to collect swing points"),
            "width_atr": Param(0.5, "float", 0.1, 3.0, doc="swings within this many ATRs of each other form one zone"),
            "min_touches": Param(2, "int", 1, 10, doc="fewest swing points for a zone"),
            "per_side": Param(3, "int", 1, 10, doc="most zones kept above and below price"),
            "max_width_mult": Param(2.0, "float", 1.0, 10.0,
                                    doc="a zone spans at most this many grouping widths (convention, not tuned)")},
    calculation=("Confirmed swing points from the lookback are sorted by price and grouped while neighbours are within "
                 "width_atr x ATR(14), and no group grows wider than max_width_mult times that (default 2, a convention). Each group with at least min_touches swings is a zone spanning their prices. The "
                 "strongest per_side zones above (resistance) and below (support) the last close are kept: most "
                 "touches first, then most recent. Each zone gives its distance from price in price, % and ATRs, "
                 "the latest close through it and any retest after that. Swings in groups below min_touches and zones beyond "
                 "per_side are kept in the evidence (ungrouped_swings, other_zones), not discarded."),
    interpretation="Price areas where swings have repeatedly turned. Values are real prices, not scores.",
    limitations=("Zones from few touches are weak; they are dropped below min_touches. No volume information "
                 "(volume profile is on the roadmap). A zone far from price may be irrelevant for the current trade."),
)
def level_zones(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 60)
    if failed:
        return failed
    atr = _num(frame["atr"].iloc[-1]) if "atr" in frame.columns else None
    if not atr:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["ATR not available."])
    found = sw.zones(frame["high"], frame["low"], frame["close"], atr, params["left"], params["right"],
                     params["lookback"], params["width_atr"], params["min_touches"], params["per_side"],
                     params["max_width_mult"])

    def stamp(z):
        z = dict(z)
        z["last_touch"] = iso(frame.index[z.pop("last_touch_index")])
        z["swing_times"] = [iso(frame.index[i]) for i in z.pop("swing_indexes", [])]
        for key in ("broken_index", "retest_index"):
            idx = z.pop(key)
            z[key.replace("_index", "_at")] = None if idx is None else _when(ctx, loaded, timeframe, frame, idx)[1]
        return z

    value = {side: [stamp(z) for z in found[side]] for side in ("support", "resistance", "at_price")}
    value["close"] = float(frame["close"].iloc[-1])
    value["atr"] = atr
    evidence = {
        "tolerance": found["tolerance"], "max_width": found["max_width"],
        "swings_considered": found["swings_considered"],
        "ungrouped_swings": [{"kind": p["kind"], "price": p["price"], "time": iso(frame.index[p["index"]])}
                             for p in found["ungrouped_swings"]],
        "other_zones": [stamp(z) for z in found["other_zones"]],
    }
    return _ok(ctx, loaded, timeframe, frame, value, evidence)


# ============================================================================ regime evidence

def efficiency_ratio(close: pd.Series, n: int) -> float | None:
    """Kaufman efficiency ratio: net move over n candles divided by the sum of every candle's move (0..1)."""
    if len(close) <= n:
        return None
    window = close.iloc[-(n + 1):]
    path = window.diff().abs().sum()
    if not path:
        return None
    return float(abs(window.iloc[-1] - window.iloc[0]) / path)


def percentile_rank(series: pd.Series, window: int) -> float | None:
    """Where the latest value sits among the last `window` values, 0..100."""
    values = series.dropna().iloc[-window:]
    if len(values) < 20:
        return None
    return float((values < values.iloc[-1]).mean() * 100)


@signal(
    id="regime.observation", version=1, name="Regime evidence", category="regime",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"confirm": Param(3, "int", 1, 10, doc="candles a new regime must hold (existing regime rule)"),
            "window": Param(250, "int", 50, 1000, doc="candles used to rank volatility and band width")},
    calculation=("Builds on the existing regime rules without changing them: confirmed state and direction from "
                 "regime.regime_series. Adds: ADX(14) value and its 5-candle change; Kaufman efficiency ratio over 20 "
                 "candles (0 = choppy, 1 = straight line); ATR(14) as % of price and its percentile over `window` "
                 "candles; Bollinger band width (upper-lower over middle) and its percentile (low = compressed, "
                 "high = expanded); and whether the raw state already differs from the confirmed state (in transition)."),
    interpretation=("Why the regime is what it is, and whether volatility is compressed or expanding. Percentiles are "
                    "reported as numbers; the words (compressed below the 20th, expanded above the 80th) are guides."),
    limitations="All inputs come from price; volatility percentiles depend on the window and on how much history loaded.",
)
def regime_observation(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 60)
    if failed:
        return failed
    table = regime_rules.regime_series(frame.iloc[-max(120, params["confirm"] + 1):], confirm=params["confirm"])
    if table.empty or table["state"].iloc[-1] is None:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["ADX not available yet."])
    close = frame["close"]
    adx = frame["adx"]
    atr_pct = frame["atr"] / close * 100 if "atr" in frame.columns else None
    upper, lower, middle = _col(frame, "BBU_"), _col(frame, "BBL_"), _col(frame, "BBM_")
    width = None
    if upper and lower:
        mid = frame[middle] if middle else close.rolling(20).mean()
        width = (frame[upper] - frame[lower]) / mid
    width_pct = percentile_rank(width, params["window"]) if width is not None else None
    vol_pct = percentile_rank(atr_pct, params["window"]) if atr_pct is not None else None
    adx_change = _num(adx.iloc[-1] - adx.iloc[-6]) if len(adx) > 6 else None
    value = {
        "state": table["state"].iloc[-1], "direction": table["direction"].iloc[-1],
        "in_transition": table["raw"].iloc[-1] not in (None, table["state"].iloc[-1]),
        "adx": _num(adx.iloc[-1]), "adx_change_5": adx_change,
        "efficiency_ratio_20": None if efficiency_ratio(close, 20) is None else round(efficiency_ratio(close, 20), 3),
        "atr_pct": _num(atr_pct.iloc[-1]) if atr_pct is not None else None,
        "atr_pct_percentile": None if vol_pct is None else round(vol_pct, 1),
        "band_width": _num(width.iloc[-1]) if width is not None else None,
        "band_width_percentile": None if width_pct is None else round(width_pct, 1),
        "volatility": None if width_pct is None else
        ("compressed" if width_pct < 20 else "expanded" if width_pct > 80 else "normal"),
    }
    return _ok(ctx, loaded, timeframe, frame, value, {"raw_state_now": table["raw"].iloc[-1],
                                                      "thresholds": {"trend_adx": regime_rules.TREND_ADX,
                                                                     "range_adx": regime_rules.RANGE_ADX}})


# ============================================================================ volume

def chaikin_money_flow(frame: pd.DataFrame, length: int = 20) -> pd.Series:
    """CMF: sum over `length` candles of money-flow volume divided by the sum of volume.
    Money-flow multiplier = ((close - low) - (high - close)) / (high - low); 0 when high == low."""
    span = (frame["high"] - frame["low"]).replace(0, np.nan)
    multiplier = (((frame["close"] - frame["low"]) - (frame["high"] - frame["close"])) / span).fillna(0.0)
    volume = frame["volume"].astype(float)
    return (multiplier * volume).rolling(length).sum() / volume.rolling(length).sum().replace(0, np.nan)


@signal(
    id="volume.cmf", version=1, name="Chaikin Money Flow", category="volume",
    output=NUMERIC, unit="ratio (-1..+1)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"length": Param(20, "int", 5, 100, doc="candles summed")},
    calculation=("CMF(length) = sum of ((close-low)-(high-close))/(high-low) x volume over `length` closed candles, "
                 "divided by the sum of volume. Above 0: closes tend to sit near the highs on volume."),
    interpretation=("Where candles close within their range, weighted by volume. Unlike OBV (whole-candle direction) it "
                    "uses the close's position in the range, so it can differ from price direction. The coverage audit "
                    "found it more distinct from the existing readings than OBV; predictive value is unproven."),
    limitations="Gaps between candles are ignored. Crypto volume differs by venue; zero-volume candles are skipped.",
)
def volume_cmf(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, params["length"] + 5)
    if failed:
        return failed
    if float(frame["volume"].iloc[-params["length"]:].sum()) <= 0:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["No volume in these candles."])
    cmf = chaikin_money_flow(frame, params["length"])
    value = _num(cmf.iloc[-1])
    obv_dir = None
    if "obv" in frame.columns and len(frame) > params["length"]:
        obv_dir = "up" if frame["obv"].iloc[-1] > frame["obv"].iloc[-params["length"]] else "down"
    return _ok(ctx, loaded, timeframe, frame, None if value is None else round(value, 4),
               {"cmf_5_candles_ago": _num(cmf.iloc[-6]) if len(cmf) > 6 else None,
                "obv_direction_same_window": obv_dir})


@signal(
    id="volume.relative", version=1, name="Relative volume", category="volume",
    output=NUMERIC, unit="x average", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    calculation="Volume of the last closed candle divided by the 20-candle average volume (the existing volume_ratio).",
    interpretation="How busy the last candle was compared with usual. 2.0 = twice the normal volume.",
    limitations=("Intraday share volume has a daily rhythm (busy open and close), so 15m/1h values are high at the open "
                 "on most days. Crypto volume varies by data venue."),
)
def volume_relative(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 25)
    if failed:
        return failed
    ratio = _num(frame["volume_ratio"].iloc[-1]) if "volume_ratio" in frame.columns else None
    if ratio is None:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["No volume average yet."])
    return _ok(ctx, loaded, timeframe, frame, round(ratio, 3),
               {"volume": _num(frame["volume"].iloc[-1]), "average_20": _num(frame.get("vol_sma_20", pd.Series([None])).iloc[-1])})
