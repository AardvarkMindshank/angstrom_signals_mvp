"""
📍 Single prints (20 Nov 2026), from market profile: within one day, a price that only one 30-minute candle traded
through, because price moved through it too fast for trading to build up. Traders treat these thin areas like fair
value gaps: price often comes back to fill them.

Worked out from the chart's own 30-minute candles (Binance for crypto, Yahoo for equities), so no new data source:
* each day (UTC for crypto, the exchange's day for shares) is cut into ROWS price rows between its low and high;
* a row touched by exactly one of the day's 30-minute candles is a single print; neighbouring ones join into a zone;
* zones that reach the day's high or low are left out (those are the day's tails, not gaps inside it);
* a zone stays on the chart until later candles trade back through it (a part traded shrinks it).

Chart only: nothing here is scored or stored.
"""

from __future__ import annotations

import pandas as pd

ROWS = 40              # price rows per day
MIN_CANDLES = 8        # a day needs at least 4 hours of candles to have a profile
MIN_SIZE = 0.0015      # a zone at least 0.15% of the price
MAX_ZONES = 30         # the newest ones


def _days(candles: pd.DataFrame, session=None):
    index = candles.index
    if index.tz is None:
        index = index.tz_localize("UTC")
    local = index.tz_convert(session[0]) if session else index.tz_convert("UTC")
    return candles.groupby(local.date, sort=True)


def day_zones(day: pd.DataFrame) -> list[dict]:
    """Single-print zones inside one day's 30-minute candles: [{start, top, bottom, up}]."""
    if len(day) < MIN_CANDLES:
        return []
    high, low = float(day["high"].max()), float(day["low"].min())
    if not high > low:
        return []
    step = (high - low) / ROWS
    centres = [low + step * (r + 0.5) for r in range(ROWS)]
    touched = [[i for i, (h, lo) in enumerate(zip(day["high"], day["low"])) if lo <= c <= h] for c in centres]
    zones, run = [], []
    for r in range(ROWS + 1):
        single = r < ROWS and len(touched[r]) == 1
        if single and run and touched[r] != touched[run[-1]]:      # a different candle: a new zone
            zones.append(run)
            run = []
        if single:
            run.append(r)
        elif run:
            zones.append(run)
            run = []
    out = []
    for run in zones:
        if run[0] == 0 or run[-1] == ROWS - 1:                     # a tail at the day's low or high
            continue
        bottom, top = low + step * run[0], low + step * (run[-1] + 1)
        if (top - bottom) / top < MIN_SIZE:
            continue
        i = touched[run[0]][0]
        row = day.iloc[i]
        out.append({"start": day.index[i], "top": top, "bottom": bottom, "up": float(row["close"]) >= float(row["open"])})
    return out


def _fill(zone: dict, later: pd.DataFrame) -> dict | None:
    """The part of the zone later candles have not traded through, or None once it is filled."""
    top, bottom = zone["top"], zone["bottom"]
    for h, lo in zip(later["high"], later["low"]):
        if lo <= bottom and h >= top:
            return None
        if bottom < lo < top <= h:              # traded down into it from above
            top = lo
        elif lo <= bottom < h < top:            # traded up into it from below
            bottom = h
        elif bottom < lo and h < top:           # inside it: keep the larger part left untouched
            if top - h >= lo - bottom:
                bottom = h
            else:
                top = lo
        if top <= bottom:
            return None
    return {**zone, "top": top, "bottom": bottom}


def zones(candles: pd.DataFrame, session=None) -> list[dict]:
    """The single-print zones still open, oldest first (at most MAX_ZONES)."""
    if candles is None or candles.empty:
        return []
    candles = candles[["open", "high", "low", "close"]].astype(float)
    out = []
    for _date, day in _days(candles, session):
        for zone in day_zones(day):
            later = candles[candles.index > day.index[-1]]
            left = _fill(zone, later)
            if left is not None:
                out.append(left)
    return out[-MAX_ZONES:]


def payload(zones_found: list[dict], frame_index: pd.DatetimeIndex) -> list[dict]:
    """For the chart: each zone from the chart candle that holds its start (a logical index), top, bottom, up."""
    if not zones_found or frame_index is None or len(frame_index) == 0:
        return []
    index = frame_index if frame_index.tz is not None else frame_index.tz_localize("UTC")
    out = []
    for z in zones_found:
        start = pd.Timestamp(z["start"])
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert(index.tz)
        i = int(index.searchsorted(start, side="right")) - 1
        if i < 0:
            continue
        out.append({"from": i, "top": round(z["top"], 10), "bottom": round(z["bottom"], 10), "up": bool(z["up"])})
    return out
