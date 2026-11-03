"""
Swing points, divergences, market structure and price zones: the pure calculations.

Everything here works on plain arrays of closed candles and never looks past the bar it is
deciding about, so a result found at bar t is the same whether or not later bars exist
(tests check this by truncating the data).

Swing (pivot) rule, the same convention as TradingView's ta.pivothigh / ta.pivotlow:
- a swing high at bar i: high[i] is above every high in the `left` bars before it and not below any
  high in the `right` bars after it. Swing lows mirror this.
- it is CONFIRMED when bar i + right has closed. Until then it is only a candidate ("developing").
"""

from __future__ import annotations

import numpy as np


def _arr(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


def pivots(high, low, left: int = 5, right: int = 5, upto: int | None = None) -> list[dict]:
    """Confirmed swing points using bars [0, upto] only (upto defaults to the last bar).
    Each: {"kind": "high"|"low", "index", "price", "confirmed_index"} in time order."""
    high, low = _arr(high), _arr(low)
    last = len(high) - 1 if upto is None else int(upto)
    out = []
    for i in range(left, last - right + 1):
        if np.isnan(high[i]) or np.isnan(low[i]):
            continue
        before_h, after_h = high[i - left:i], high[i + 1:i + right + 1]
        if before_h.size and after_h.size and high[i] > np.nanmax(before_h) and high[i] >= np.nanmax(after_h):
            out.append({"kind": "high", "index": i, "price": float(high[i]), "confirmed_index": i + right})
        before_l, after_l = low[i - left:i], low[i + 1:i + right + 1]
        if before_l.size and after_l.size and low[i] < np.nanmin(before_l) and low[i] <= np.nanmin(after_l):
            out.append({"kind": "low", "index": i, "price": float(low[i]), "confirmed_index": i + right})
    return out


def candidate(high, low, kind: str, left: int = 5, right: int = 5) -> dict | None:
    """The most recent bar that could still become a swing point (not confirmed yet)."""
    high, low = _arr(high), _arr(low)
    n = len(high)
    for i in range(n - 1, max(left - 1, n - right - 1), -1):
        if kind == "low":
            before, after = low[i - left:i], low[i + 1:]
            if before.size and low[i] < np.nanmin(before) and (after.size == 0 or low[i] <= np.nanmin(after)):
                return {"kind": "low", "index": i, "price": float(low[i]), "bars_to_confirm": right - (n - 1 - i)}
        else:
            before, after = high[i - left:i], high[i + 1:]
            if before.size and high[i] > np.nanmax(before) and (after.size == 0 or high[i] >= np.nanmax(after)):
                return {"kind": "high", "index": i, "price": float(high[i]), "bars_to_confirm": right - (n - 1 - i)}
    return None


# ---------------------------------------------------------------------------- divergences

REGULAR_BULL = "regular_bullish"
HIDDEN_BULL = "hidden_bullish"
REGULAR_BEAR = "regular_bearish"
HIDDEN_BEAR = "hidden_bearish"


def _osc_extreme(osc: np.ndarray, index: int, kind: str, near: int, limit: int):
    """Indicator swing value next to a price swing: the lowest (for lows) or highest (for highs)
    indicator reading within `near` bars, never past `limit` (the confirmation bar)."""
    lo, hi = max(0, index - near), min(limit, index + near)
    window = osc[lo:hi + 1]
    if window.size == 0 or np.all(np.isnan(window)):
        return None, None
    j = int(np.nanargmin(window) if kind == "low" else np.nanargmax(window))
    return lo + j, float(window[j])


def _classify(kind: str, p1: float, p2: float, o1: float, o2: float) -> str | None:
    if kind == "low":
        if p2 < p1 and o2 > o1:
            return REGULAR_BULL
        if p2 > p1 and o2 < o1:
            return HIDDEN_BULL
    else:
        if p2 > p1 and o2 < o1:
            return REGULAR_BEAR
        if p2 < p1 and o2 > o1:
            return HIDDEN_BEAR
    return None


def divergences(high, low, close, osc, left=5, right=5, min_gap=5, max_gap=60, near=2) -> dict:
    """Confirmed divergences between consecutive confirmed price swings, plus any developing one.

    A divergence compares two consecutive swing lows (bullish kinds) or highs (bearish kinds) that are
    min_gap..max_gap bars apart, with the indicator's own extreme within `near` bars of each price swing.
    It is confirmed when the second swing is confirmed (right bars later). It is invalidated when, after
    confirmation, a candle closes beyond the second swing's price (below it for bullish, above for bearish).
    """
    high, low, close, osc = _arr(high), _arr(low), _arr(close), _arr(osc)
    n = len(close)
    swings = pivots(high, low, left, right)
    events = []
    for kind in ("low", "high"):
        same = [p for p in swings if p["kind"] == kind]
        for a, b in zip(same, same[1:]):
            gap = b["index"] - a["index"]
            if gap < min_gap or gap > max_gap:
                continue
            ia, oa = _osc_extreme(osc, a["index"], kind, near, a["confirmed_index"])
            ib, ob = _osc_extreme(osc, b["index"], kind, near, b["confirmed_index"])
            if oa is None or ob is None:
                continue
            label = _classify(kind, a["price"], b["price"], oa, ob)
            if not label:
                continue
            invalid_at = None
            for k in range(b["confirmed_index"] + 1, n):
                if (kind == "low" and close[k] < b["price"]) or (kind == "high" and close[k] > b["price"]):
                    invalid_at = k
                    break
            events.append({
                "type": label, "status": "invalidated" if invalid_at is not None else "confirmed",
                "price_pivots": [{"index": a["index"], "price": a["price"]}, {"index": b["index"], "price": b["price"]}],
                "indicator_pivots": [{"index": ia, "value": round(oa, 6)}, {"index": ib, "value": round(ob, 6)}],
                "confirmed_index": b["confirmed_index"], "delay_bars": right,
                "invalidation_price": b["price"], "invalidation_rule": "close below" if kind == "low" else "close above",
                "invalidated_index": invalid_at,
            })
    events.sort(key=lambda e: e["confirmed_index"])

    developing = []
    for kind in ("low", "high"):
        cand = candidate(high, low, kind, left, right)
        prior = [p for p in swings if p["kind"] == kind]
        if not cand or not prior:
            continue
        a = prior[-1]
        gap = cand["index"] - a["index"]
        if gap < min_gap or gap > max_gap:
            continue
        ia, oa = _osc_extreme(osc, a["index"], kind, near, a["confirmed_index"])
        ib, ob = _osc_extreme(osc, cand["index"], kind, near, n - 1)
        if oa is None or ob is None:
            continue
        label = _classify(kind, a["price"], cand["price"], oa, ob)
        if label:
            developing.append({
                "type": label, "status": "developing",
                "price_pivots": [{"index": a["index"], "price": a["price"]}, {"index": cand["index"], "price": cand["price"]}],
                "indicator_pivots": [{"index": ia, "value": round(oa, 6)}, {"index": ib, "value": round(ob, 6)}],
                "bars_to_confirm": cand["bars_to_confirm"],
            })
    return {"events": events, "developing": developing}


# ---------------------------------------------------------------------------- market structure

def label_swings(swings: list[dict]) -> list[dict]:
    """HH/LH for highs and HL/LL for lows against the previous swing of the same kind (EH/EL when equal)."""
    last = {"high": None, "low": None}
    out = []
    for p in swings:
        prev = last[p["kind"]]
        if prev is None:
            tag = None
        elif p["kind"] == "high":
            tag = "HH" if p["price"] > prev else "LH" if p["price"] < prev else "EH"
        else:
            tag = "HL" if p["price"] > prev else "LL" if p["price"] < prev else "EL"
        out.append({**p, "label": tag})
        last[p["kind"]] = p["price"]
    return out


def structure_state(labelled: list[dict]) -> str:
    """up: latest high HH and latest low HL. down: LH and LL. Otherwise mixed (or unknown)."""
    highs = [p for p in labelled if p["kind"] == "high" and p["label"]]
    lows = [p for p in labelled if p["kind"] == "low" and p["label"]]
    if not highs or not lows:
        return "unknown"
    h, l = highs[-1]["label"], lows[-1]["label"]
    if h == "HH" and l == "HL":
        return "up"
    if h == "LH" and l == "LL":
        return "down"
    return "mixed"


def structure_breaks(high, low, close, left=5, right=5) -> list[dict]:
    """Closes beyond the latest confirmed swing, judged with only the swings confirmed at that bar.

    - bullish break: a close above the latest confirmed swing high. It is a break of structure (BOS,
      continuation) when the structure was already up, and a potential change of character (CHoCH)
      when it was down. Bearish breaks mirror this. Each swing level can be broken once.
    """
    high, low, close = _arr(high), _arr(low), _arr(close)
    swings = sorted(pivots(high, low, left, right), key=lambda p: p["confirmed_index"])
    events = []
    broken = set()
    known, labelled_tail = [], {"high": None, "low": None}   # newest labelled swing of each kind
    last_price = {"high": None, "low": None}
    pointer = 0
    for t in range(len(close)):
        while pointer < len(swings) and swings[pointer]["confirmed_index"] <= t - 1:  # confirmed before this bar
            p = swings[pointer]
            prev = last_price[p["kind"]]
            if prev is None:
                tag = None
            elif p["kind"] == "high":
                tag = "HH" if p["price"] > prev else "LH" if p["price"] < prev else "EH"
            else:
                tag = "HL" if p["price"] > prev else "LL" if p["price"] < prev else "EL"
            last_price[p["kind"]] = p["price"]
            labelled_tail[p["kind"]] = {**p, "label": tag}
            known.append(p)
            pointer += 1
        if not known:
            continue
        state = structure_state([x for x in labelled_tail.values() if x])
        last_high = labelled_tail["high"]
        last_low = labelled_tail["low"]
        if last_high and ("high", last_high["index"]) not in broken and close[t] > last_high["price"]:
            broken.add(("high", last_high["index"]))
            events.append({"index": t, "direction": "bullish", "level": last_high["price"],
                           "swing_index": last_high["index"], "structure_before": state,
                           "kind": "BOS" if state == "up" else "CHoCH" if state == "down" else "break"})
        if last_low and ("low", last_low["index"]) not in broken and close[t] < last_low["price"]:
            broken.add(("low", last_low["index"]))
            events.append({"index": t, "direction": "bearish", "level": last_low["price"],
                           "swing_index": last_low["index"], "structure_before": state,
                           "kind": "BOS" if state == "down" else "CHoCH" if state == "up" else "break"})
    return events


# ---------------------------------------------------------------------------- price zones

def zones(high, low, close, atr: float, left=5, right=5, lookback=300, width_atr=0.5,
          min_touches=2, per_side=3) -> dict:
    """Support and resistance zones from clusters of confirmed swing points.

    Swing prices within the lookback are sorted and grouped while neighbours are within
    width_atr x ATR of each other. A zone spans its swings' prices (at least a quarter of that width).
    Zones with fewer than min_touches swings are dropped; the strongest per_side zones on each side of
    the last close are kept (more touches first, then the most recent touch).
    A retest is recorded when a candle closed through the zone and a later candle came back into it
    and closed on the new side again.
    """
    high, low, close = _arr(high), _arr(low), _arr(close)
    n = len(close)
    if n == 0 or not atr or atr != atr or atr <= 0:
        return {"support": [], "resistance": [], "at_price": [], "tolerance": None}
    tol = width_atr * atr
    start = max(0, n - lookback)
    swings = [p for p in pivots(high, low, left, right) if p["index"] >= start]
    swings.sort(key=lambda p: p["price"])
    clusters, current = [], []
    for p in swings:
        if current and p["price"] - current[-1]["price"] > tol:
            clusters.append(current)
            current = []
        current.append(p)
    if current:
        clusters.append(current)

    price = close[-1]
    out = {"support": [], "resistance": [], "at_price": [], "tolerance": round(tol, 8)}
    for group in clusters:
        if len(group) < min_touches:
            continue
        lo_p, hi_p = min(p["price"] for p in group), max(p["price"] for p in group)
        pad = max(0.0, (tol / 4 - (hi_p - lo_p)) / 2)
        z_lo, z_hi = lo_p - pad, hi_p + pad
        last_touch = max(p["index"] for p in group)
        side = "support" if z_hi < price else "resistance" if z_lo > price else "at_price"
        distance = 0.0 if side == "at_price" else (price - z_hi if side == "support" else z_lo - price)
        zone = {
            "low": round(z_lo, 8), "high": round(z_hi, 8), "mid": round((z_lo + z_hi) / 2, 8),
            "touches": len(group), "highs": sum(p["kind"] == "high" for p in group),
            "lows": sum(p["kind"] == "low" for p in group), "last_touch_index": last_touch,
            "distance": round(distance, 8), "distance_pct": round(distance / price * 100, 4) if price else None,
            "distance_atr": round(distance / atr, 3),
        }
        zone.update(_retest(high, low, close, z_lo, z_hi))
        out[side].append(zone)
    for side in ("support", "resistance", "at_price"):
        out[side].sort(key=lambda z: (-z["touches"], -z["last_touch_index"]))
        out[side] = out[side][:per_side]
        out[side].sort(key=lambda z: z["distance"])
    return out


def _retest(high, low, close, z_lo, z_hi) -> dict:
    """Latest close through the zone, and whether price came back to it and held the new side."""
    n = len(close)
    side = np.where(close > z_hi, 1, np.where(close < z_lo, -1, 0))
    flip_index, flip_dir = None, None
    last_side = 0
    for i in range(n):
        if side[i] != 0:
            if last_side != 0 and side[i] != last_side:
                flip_index, flip_dir = i, "up" if side[i] > 0 else "down"
            last_side = side[i]
    if flip_index is None:
        return {"broken_index": None, "broken_direction": None, "retest_index": None}
    retest = None
    for k in range(flip_index + 1, n):
        touched = low[k] <= z_hi if flip_dir == "up" else high[k] >= z_lo
        held = close[k] > z_hi if flip_dir == "up" else close[k] < z_lo
        if touched and held:
            retest = k
            break
    return {"broken_index": flip_index, "broken_direction": flip_dir, "retest_index": retest}
