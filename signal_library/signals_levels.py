"""
Price levels made by trading (asked 20 Nov 2026, after the chart tools of 19-20 Nov), one signal each with settings:

* level.fvg            fair value gaps: three-candle gaps a fast move leaves, still open below or above the price,
                       and when one last formed, was tested or was filled;
* level.avwap          anchored VWAP: the volume-weighted average price from a chosen start (the last swing low or
                       high, or the start of the week, month or year), and where the close sits against it;
* level.volume_profile volume profile: over the last N candles, the busiest price (point of control) and the band
                       holding most of the volume (value area), and where the close sits against them.

The same rules as the chart (lw_chart.js, lw_draw.js), so a reading matches what the chart shows on that timeframe.
Each reads closed candles only. Descriptive readings, not forecasts; nothing is tuned on outcomes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import INSUFFICIENT, OBSERVATION, SCOPE_ASSET, TIMEFRAMES, Param, SignalResult, signal
from .signals_basic import _num
from .signals_candles import _ok, _r, wilder_atr
from .signals_basic import closed_candles
from .swings import pivots

ANCHORS = ("swing_low", "swing_high", "week", "month", "year")


def _insufficient(ctx, note: str) -> SignalResult:
    return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=[note])


def _dist(close: float, level: float | None, atr: float | None):
    if level is None or not close:
        return None, None
    return _r((level - close) / close * 100), (_r((level - close) / atr) if atr else None)


# ----------------------------------------------------------------------------------------------- fair value gaps

def gap_history(high, low, close, min_size_pct: float, start: int = 2) -> dict:
    """Walk the candles once. A gap forms on candle i (the third candle) when low[i] > high[i-2] (up gap) or
    high[i] < low[i-2] (down gap), at least min_size_pct of the price. Later candles trading into it shrink it; one
    trading through it fills it. A test = a candle entering an open gap and closing back on its near side (up gap:
    the close stays above the gap's bottom). Returns the open gaps after the last candle and, for each kind, the last
    candle index of: a new gap, a test, a fill."""
    n = len(high)
    open_gaps: list[dict] = []
    last = {f"{what}_{kind}": None for what in ("new", "test", "filled") for kind in ("up", "down")}
    for i in range(max(2, start), n):
        h, lo, c = high[i], low[i], close[i]
        keep = []
        for g in open_gaps:
            if g["up"]:
                if lo <= g["bottom"]:
                    last["filled_up"] = i
                    continue
                if lo < g["top"]:
                    if c > g["bottom"]:
                        last["test_up"] = i
                    g["top"] = lo
            else:
                if h >= g["top"]:
                    last["filled_down"] = i
                    continue
                if h > g["bottom"]:
                    if c < g["top"]:
                        last["test_down"] = i
                    g["bottom"] = h
            keep.append(g)
        open_gaps = keep
        if lo > high[i - 2] and (lo - high[i - 2]) / high[i - 2] * 100 >= min_size_pct:
            open_gaps.append({"up": True, "top": float(lo), "bottom": float(high[i - 2]), "formed": i})
            last["new_up"] = i
        elif h < low[i - 2] and (low[i - 2] - h) / low[i - 2] * 100 >= min_size_pct:
            open_gaps.append({"up": False, "top": float(low[i - 2]), "bottom": float(h), "formed": i})
            last["new_down"] = i
    return {"open": open_gaps, "last": last}


@signal(
    id="level.fvg", version=1, name="Fair value gaps", category="structure",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"min_size_pct": Param(0.15, "float", 0.0, 5.0, doc="smallest gap counted, as % of the price"),
            "lookback": Param(100, "int", 20, 500, doc="candles searched for gaps")},
    calculation=("Over the last `lookback` closed candles: an up gap forms when a candle's low is above the high of the "
                 "candle two before it, a down gap when its high is below that candle's low, each at least "
                 "`min_size_pct` % of the price. A later candle trading into a gap shrinks it to the part not yet "
                 "traded; one trading right through fills it. A test = a candle entering an open gap and closing back "
                 "on its near side (an up gap: the close stays above the gap's bottom). On the last closed candle: "
                 "below_count / above_count = open gaps under / over the close; nearest_below_* and nearest_above_* = "
                 "the closest one's edges and its distance from the close (to its near edge) in % and in ATR(14); "
                 "new_up_ago, test_up_ago, filled_up_ago (and _down_) = candles since a gap of that kind formed, was "
                 "tested or was filled (0 = the last closed candle, `lookback` = not in the window). The same rule as "
                 "the chart's fair value gaps."),
    interpretation=("Gaps left by fast moves that price has not gone back to. Traders watch an open gap under the price "
                    "as a place price may come back to and find buyers, and one over it as a place sellers may wait. "
                    "Descriptive; not a forecast."),
    limitations=("Many small gaps form in fast markets; min_size_pct keeps the noise down. Gaps between sessions in "
                 "shares count too. A gap is a price area, not a promise that price returns to it."),
)
def fair_value_gaps(ctx, timeframe, params):
    lookback, min_pct = params["lookback"], params["min_size_pct"]
    frame, loaded, failed = closed_candles(ctx, timeframe, max(lookback, 20) + 3)
    if failed:
        return failed
    window = frame.iloc[-(lookback + 2):]
    high, low, close = (window[k].astype(float).to_numpy() for k in ("high", "low", "close"))
    found = gap_history(high, low, close, min_pct)
    c = float(close[-1])
    atr = _num(wilder_atr(frame, 14).iloc[-1])
    below = [g for g in found["open"] if g["top"] <= c]
    above = [g for g in found["open"] if g["bottom"] >= c]
    near_below = max(below, key=lambda g: g["top"]) if below else None
    near_above = min(above, key=lambda g: g["bottom"]) if above else None
    end = len(high) - 1

    def ago(i):
        return lookback if i is None else min(lookback, end - i)

    nb_pct, nb_atr = _dist(c, near_below["top"] if near_below else None, atr)
    na_pct, na_atr = _dist(c, near_above["bottom"] if near_above else None, atr)
    value = {
        "close": c, "below_count": len(below), "above_count": len(above),
        "nearest_below_top": _r(near_below["top"]) if near_below else None,
        "nearest_below_bottom": _r(near_below["bottom"]) if near_below else None,
        "nearest_below_distance_pct": None if nb_pct is None else -nb_pct,
        "nearest_below_distance_atr": None if nb_atr is None else -nb_atr,
        "nearest_above_bottom": _r(near_above["bottom"]) if near_above else None,
        "nearest_above_top": _r(near_above["top"]) if near_above else None,
        "nearest_above_distance_pct": na_pct, "nearest_above_distance_atr": na_atr,
        **{f"{what}_{kind}_ago": ago(found["last"][f"{what}_{kind}"])
           for what in ("new", "test", "filled") for kind in ("up", "down")},
    }
    return _ok(ctx, loaded, timeframe, frame, value, {"lookback": lookback, "min_size_pct": min_pct,
                                                       "atr_14": _r(atr), "open_gaps": len(found["open"])})


# ----------------------------------------------------------------------------------------------- anchored VWAP

def anchor_index(frame: pd.DataFrame, anchor: str, swing: int) -> int | None:
    """The candle the VWAP starts from: the last confirmed swing low / high (swing candles each side), or the first
    candle of the current week (Monday), month or year (UTC dates of candle starts)."""
    if anchor in ("swing_low", "swing_high"):
        kind = "low" if anchor == "swing_low" else "high"
        found = [p for p in pivots(frame["high"].to_numpy(), frame["low"].to_numpy(), swing, swing) if p["kind"] == kind]
        return found[-1]["index"] if found else None
    index = frame.index if frame.index.tz is not None else frame.index.tz_localize("UTC")
    dates = index.tz_convert("UTC")
    last = dates[-1]
    if anchor == "week":
        start = (last - pd.Timedelta(days=last.weekday())).normalize()
    elif anchor == "month":
        start = last.normalize().replace(day=1)
    else:
        start = last.normalize().replace(month=1, day=1)
    i = int(dates.searchsorted(start))
    return i if i < len(frame) else None


def vwap_from(frame: pd.DataFrame, start: int) -> pd.Series:
    """Running VWAP from candle `start`: sum(typical price x volume) / sum(volume), typical = (high + low + close) / 3."""
    part = frame.iloc[start:]
    typical = (part["high"] + part["low"] + part["close"]) / 3
    volume = part["volume"].astype(float).fillna(0.0)
    vol = volume.cumsum()
    out = (typical * volume).cumsum() / vol.replace(0, np.nan)
    return out.fillna(typical.expanding().mean())


@signal(
    id="level.avwap", version=1, name="Anchored VWAP", category="structure",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"anchor": Param("swing_low", "choice", choices=ANCHORS,
                            doc="where the average starts: the last swing low or high, or the start of the week, month "
                                "or year"),
            "swing": Param(5, "int", 2, 30, doc="candles each side that make a swing low or high")},
    calculation=("From the anchor candle to the last closed candle: VWAP = sum of typical price ((high + low + close) "
                 "/ 3) x volume over the sum of volume. Anchors: swing_low / swing_high = the last swing low / high "
                 "confirmed by `swing` candles each side (as the structure signals); week, month, year = the first "
                 "candle of the current calendar week (Monday), month or year, UTC. On the last closed candle: "
                 "position = the close above or below the VWAP; distance in % and in ATR(14); crossed_up = the "
                 "previous close was below its VWAP and this one is above, crossed_down the reverse; retest_from_above "
                 "= the low reached the VWAP and the close finished above it, retest_from_below the reverse; anchor_ago "
                 "= candles since the anchor; anchor_price = the swing's price (swing anchors) or the anchor candle's "
                 "open. The chart's ⚓ drawing tool uses the same formula from a candle you tap."),
    interpretation=("The average price paid, weighted by volume, by everyone who traded since a moment that mattered. "
                    "Above it, buyers since then are on average in profit; traders watch a pullback that holds the "
                    "VWAP as a sign buyers are defending it. Descriptive; not a forecast."),
    limitations=("Depends on the anchor: a different swing gives a different line. Swing anchors are known `swing` "
                 "candles late. Volume differs between exchanges and data sources; a period with little volume moves "
                 "the line little."),
)
def anchored_vwap(ctx, timeframe, params):
    anchor, swing = params["anchor"], params["swing"]
    frame, loaded, failed = closed_candles(ctx, timeframe, max(30, swing * 4 + 2))
    if failed:
        return failed
    frame = frame.astype({k: float for k in ("open", "high", "low", "close")})
    if "volume" not in frame.columns:
        return _insufficient(ctx, "No volume for this asset.")
    start = anchor_index(frame, anchor, swing)
    if start is None:
        return _insufficient(ctx, f"No {anchor.replace('_', ' ')} to start from.")
    line = vwap_from(frame, start)
    v, close = _num(line.iloc[-1]), float(frame["close"].iloc[-1])
    high, low = float(frame["high"].iloc[-1]), float(frame["low"].iloc[-1])
    if v is None:
        return _insufficient(ctx, "The VWAP is not ready yet.")
    prev = len(line) >= 2
    v_prev, c_prev = (_num(line.iloc[-2]), float(frame["close"].iloc[-2])) if prev else (None, None)
    atr = _num(wilder_atr(frame, 14).iloc[-1])
    if anchor == "swing_low":
        anchor_price = float(frame["low"].iloc[start])
    elif anchor == "swing_high":
        anchor_price = float(frame["high"].iloc[start])
    else:
        anchor_price = float(frame["open"].iloc[start])
    value = {
        "vwap": _r(v), "close": close, "position": "above" if close > v else "below" if close < v else "on",
        "distance_pct": _r((close - v) / v * 100) if v else None,
        "distance_atr": _r((close - v) / atr) if atr else None,
        "crossed_up": bool(v_prev is not None and c_prev < v_prev and close > v),
        "crossed_down": bool(v_prev is not None and c_prev > v_prev and close < v),
        "retest_from_above": bool(low <= v < close), "retest_from_below": bool(high >= v > close),
        "anchor_ago": len(frame) - 1 - start, "anchor_price": _r(anchor_price),
    }
    return _ok(ctx, loaded, timeframe, frame, value, {"anchor": anchor, "swing": swing, "atr_14": _r(atr),
                                                       "anchor_at": str(frame.index[start])})


# ----------------------------------------------------------------------------------------------- volume profile

def profile(high, low, volume, rows: int, value_area: float) -> dict | None:
    """Volume shared out over `rows` price rows between the lowest low and highest high (each candle's volume spread
    evenly over the rows its range covers); the busiest row (point of control) and the rows around it that hold
    `value_area` of the volume, growing towards the busier neighbour first. None without range or volume."""
    top, bottom = float(np.nanmax(high)), float(np.nanmin(low))
    if not top > bottom:
        return None
    step = (top - bottom) / rows
    counts = np.zeros(rows)
    for h, lo, v in zip(high, low, volume):
        if not (v and np.isfinite(v) and np.isfinite(h) and np.isfinite(lo)) or v <= 0:
            continue
        r0 = int(min(rows - 1, max(0, (lo - bottom) // step)))
        r1 = int(min(rows - 1, max(0, (h - bottom) // step)))
        counts[r0:r1 + 1] += v / (r1 - r0 + 1)
    total = counts.sum()
    if not total:
        return None
    poc = int(np.argmax(counts))
    lo_r, hi_r, held = poc, poc, counts[poc]
    while held < total * value_area and (lo_r > 0 or hi_r < rows - 1):
        below = counts[lo_r - 1] if lo_r > 0 else -1
        above = counts[hi_r + 1] if hi_r < rows - 1 else -1
        if above >= below:
            hi_r += 1
            held += above
        else:
            lo_r -= 1
            held += below
    return {"poc": bottom + step * (poc + 0.5), "value_low": bottom + step * lo_r,
            "value_high": bottom + step * (hi_r + 1), "row": step, "low": bottom, "high": top}


@signal(
    id="level.volume_profile", version=1, name="Volume profile", category="structure",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"lookback": Param(30, "int", 10, 500, doc="candles in the profile (the last closed one included)"),
            "rows": Param(24, "int", 10, 100, doc="price rows the range is cut into"),
            "value_area": Param(70, "int", 50, 95, doc="% of the volume the value area holds")},
    calculation=("Over the last `lookback` closed candles, the range from the lowest low to the highest high is cut "
                 "into `rows` price rows; each candle's volume is spread evenly over the rows its high-low covers. "
                 "poc (point of control) = the middle of the busiest row; the value area = the busiest row plus "
                 "neighbouring rows, adding the busier side first, until it holds `value_area` % of the volume; "
                 "value_low / value_high = its edges. On the last close: position = above_value, in_value or "
                 "below_value; poc_side = the close above or below the poc; poc_distance_pct and poc_distance_atr = "
                 "from the poc to the close (ATR 14); at_poc = the close within one row of the poc. The chart's 📊 "
                 "drawing tool uses the same rule over a range you drag."),
    interpretation=("Where most trading happened lately. Traders read the busiest price as fair value that price is "
                    "drawn back to, and a close outside the value area as price leaving that range. Descriptive; "
                    "not a forecast."),
    limitations=("Built from candles, not trades: volume inside a candle is assumed spread evenly across its range, "
                 "so it is an estimate. Daily candles give a rough profile; shorter candles a finer one. Volume "
                 "differs between data sources."),
)
def volume_profile(ctx, timeframe, params):
    lookback, rows, area = params["lookback"], params["rows"], params["value_area"]
    frame, loaded, failed = closed_candles(ctx, timeframe, lookback + 15)
    if failed:
        return failed
    if "volume" not in frame.columns:
        return _insufficient(ctx, "No volume for this asset.")
    window = frame.iloc[-lookback:]
    vp = profile(window["high"].astype(float).to_numpy(), window["low"].astype(float).to_numpy(),
                 window["volume"].astype(float).fillna(0.0).to_numpy(), rows, area / 100)
    if vp is None:
        return _insufficient(ctx, "No price range or volume in the window.")
    close = float(frame["close"].iloc[-1])
    atr = _num(wilder_atr(frame, 14).iloc[-1])
    value = {
        "poc": _r(vp["poc"]), "value_high": _r(vp["value_high"]), "value_low": _r(vp["value_low"]), "close": close,
        "position": "above_value" if close > vp["value_high"] else "below_value" if close < vp["value_low"] else "in_value",
        "poc_side": "above" if close > vp["poc"] else "below" if close < vp["poc"] else "on",
        "poc_distance_pct": _r((close - vp["poc"]) / vp["poc"] * 100) if vp["poc"] else None,
        "poc_distance_atr": _r((close - vp["poc"]) / atr) if atr else None,
        "at_poc": bool(abs(close - vp["poc"]) <= vp["row"]),
    }
    return _ok(ctx, loaded, timeframe, frame, value, {"lookback": lookback, "rows": rows, "value_area": area,
                                                       "range_low": _r(vp["low"]), "range_high": _r(vp["high"]),
                                                       "atr_14": _r(atr)})
