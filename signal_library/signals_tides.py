"""
Tides as Signal Library signals (18 Nov 2026): the macro layer, usable in Groups, Sets and funnels.

    tides.tide      the Tide (coming in, slack, going out), the sea state, and the wind for this asset's market
    tides.current   one of the twelve currents: rising, flat or falling; its level against its own 5 years
    tides.storm     a major scheduled release (Fed decision, CPI, jobs report) coming within N days

Tides are market-wide: every asset of a market reads the same values on a given day. Rows come from the DataContext
("tides": tides_store.py), each with recorded_at (the US close it describes) and first_seen_at.

Which day's row a close reads (no peeking):
- A crypto daily close (midnight UTC) comes after that day's US close: it reads that day's row, once seen.
- An equity daily close IS the US close, when the closing readings (VIX at 16:15 New York, FRED a day later) are not
  all known yet: it reads the row of the business day before.
"""

from __future__ import annotations

import pandas as pd

from .core import (
    CONFIRMED, INSUFFICIENT, MISSING, OBSERVATION, OK, SCOPE_ASSET, STALE, Param, SignalResult, iso, signal,
)

SOURCE = ("Angstrom Tides: public daily market data (Yahoo Finance closes, FRED yields, ALFRED first-release CPI "
          "dates), point in time")
LIMITATIONS = ("Market-wide, not about this asset. Daily: reflects the previous US close. The history to Oct 2024 is "
               "reconstructed from data that is not revised later (closes, yields, unadjusted CPI), each value dated "
               "when it was first known; afterwards each day is recorded as it happens. The Tide's rules are fixed "
               "in advance, not fitted to returns. Few Tide turns per year, so studies of it rest on few spells.")
STALE_DAYS = 5
CURRENTS = ("short_rates", "long_rates", "curve", "dollar", "inflation", "gold", "fear", "copper_gold", "oil",
            "credit", "equity_rotation", "crypto_rotation")
LEVELS = ("very_low", "low", "normal", "high", "very_high")
EVENT_NAMES = {"fomc": "fed", "cpi": "cpi", "jobs": "jobs"}


def target_day(ctx) -> tuple[pd.Timestamp, bool]:
    """(day, inclusive): the last row a close at ctx.now may read is that day's (crypto) or the one before (equity)."""
    now = ctx.now
    if ctx.kind == "equity":
        day = (now - pd.Timedelta(hours=21, minutes=15)).normalize()
        while day.weekday() >= 5:
            day -= pd.Timedelta(days=1)
        return day, False
    return (now - pd.Timedelta(days=1)).normalize(), True


def _utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _row(ctx):
    """(row, day, problem): the newest row this close may read."""
    loaded = ctx.tides()
    if loaded.get("error"):
        return None, None, SignalResult(ref={}, subject=ctx.subject, status=MISSING, notes=[loaded["error"]])
    day, inclusive = target_day(ctx)
    now = ctx.now
    best = None
    for r in loaded.get("rows") or []:
        d = _utc(r["day"])
        if (d > day) or (d == day and not inclusive):
            continue
        if _utc(r["first_seen_at"]) > now or _utc(r["recorded_at"]) > now:
            continue
        if best is None or d > _utc(best["day"]):
            best = r
    if best is None:
        return None, day, SignalResult(ref={}, subject=ctx.subject, status=MISSING,
                                       notes=[f"No Tides reading known by {iso(now)}."])
    return best, day, None


def _result(ctx, row, day, value, required: tuple):
    missing = [k for k in required if row.get(k) is None]
    if missing:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT,
                            notes=[f"Not enough history for this Tides reading on {row['day']}."])
    gap = (day - _utc(row["day"])).days
    stale = gap > STALE_DAYS
    seen, recorded = _utc(row["first_seen_at"]), _utc(row["recorded_at"])
    notes = [f"The newest Tides reading is from {row['day']}, {gap} days before this close."] if stale else []
    return SignalResult(
        ref={}, subject=ctx.subject, status=STALE if stale else OK, confirmation=CONFIRMED, value=value,
        observed_at=iso(recorded), available_at=iso(seen),
        backfilled=(row.get("source") == "daily record" and seen - recorded > pd.Timedelta(days=2)),
        evidence={"row_day": row["day"], "row_source": row.get("source", "")}, provenance=[SOURCE], notes=notes)


def _num(x, scale=1.0, digits=1):
    return None if x is None else round(float(x) * scale, digits)


COMMON = dict(category="regime", output=OBSERVATION, scope=SCOPE_ASSET, timeframes=("1D",), requires=("tides",),
              limitations=LIMITATIONS)


@signal(id="tides.tide", version=1, name="Tides: tide and sea state", unit="label", **COMMON,
        calculation=("The day's Tides record (tides.py rules): the Tide (coming in above +0.20, going out below -0.20, "
                     "else slack; a new label counts after 5 closes), its score on -100..+100, days since it last "
                     "turned, the sea state (calm, moderate, rough, storm: VIX and Bitcoin volatility against their 5 "
                     "years), and the wind for this asset's market (crypto or equity: the average push of the "
                     "currents declared for it; tailwind above +20, headwind below -20)."),
        interpretation="Whether broad conditions support risk-taking, how turbulent they are, and whether they push "
                       "for or against this market. Descriptive; it does not forecast.")
def tides_tide(ctx, timeframe, params):
    row, day, problem = _row(ctx)
    if problem:
        return problem
    market = "equity" if ctx.kind == "equity" else "crypto"
    since = row.get("tide_since")
    value = {
        "tide": row.get("tide"), "tide_score": _num(row.get("tide_score"), 100),
        "tide_unconfirmed": row.get("tide_raw") if row.get("tide_raw") != row.get("tide") else None,
        "days_since_turn": None if not since else (_utc(row["day"]) - _utc(since)).days,
        "turned_on": since, "sea": row.get("sea"), "sea_score": _num(row.get("sea_score")),
        "wind": row.get(f"wind_{market}"), "wind_score": _num(row.get(f"wind_{market}_score"), 100),
        "market": market, "as_of": row["day"],
    }
    return _result(ctx, row, day, value, ("tide", "sea"))


@signal(id="tides.current", version=1, name="Tides: one current", unit="label", **COMMON,
        params={"current": Param("dollar", "choice", choices=CURRENTS,
                                 doc="Which of the twelve currents to read")},
        calculation=("One current from the day's Tides record: its direction (the 30-day change over its typical size "
                     "in the past 5 years: rising above +0.5, falling below -0.5, else flat), its level against its "
                     "own last 5 years of daily readings (0-100: very low under 20, low, normal, high, very high from "
                     "80), its push on risk (sign x tanh of that momentum, -100..+100; helping above +20, hurting "
                     "below -20) and its latest value."),
        interpretation="Which way one macro input is moving and how unusual its level is. Descriptive.")
def tides_current(ctx, timeframe, params):
    row, day, problem = _row(ctx)
    if problem:
        return problem
    key = params["current"]
    band = row.get(f"{key}_band")
    value = {
        "current": key, "direction": row.get(f"{key}_dir"),
        "level": None if band is None else str(band).replace(" ", "_"), "level_score": _num(row.get(f"{key}_score")),
        "effect": row.get(f"{key}_effect"), "push": _num(row.get(f"{key}_contrib"), 100),
        "value": _num(row.get(f"{key}_value"), 1, 4), "as_of": row["day"],
    }
    if value["direction"] == "unknown":
        value["direction"] = None
    return _result(ctx, row, day, value, (f"{key}_contrib", f"{key}_score"))


@signal(id="tides.storm", version=1, name="Tides: storm warning", unit="days", **COMMON,
        params={"days": Param(2, "int", minimum=1, maximum=14,
                              doc="A warning when a major release is this many days away or fewer")},
        calculation=("Days from this close to the next scheduled major release (Fed rate decision, CPI inflation, "
                     "jobs report; release days from the Fed and BLS schedules), for each kind and the nearest, and "
                     "a warning when the nearest is within the chosen number of days. A release on the day of this "
                     "close has already happened by the close and counts as 'today'."),
        interpretation="That a scheduled market-moving release is close. It says nothing about what it will show.")
def tides_storm(ctx, timeframe, params):
    row, day, problem = _row(ctx)
    if problem:
        return problem
    loaded = ctx.tides()
    ref = day                                           # the close's own day (crypto) or session (equity)
    future = {}
    today = []
    for kind, when in loaded.get("events") or []:
        name = EVENT_NAMES.get(kind)
        if not name:
            continue
        d = _utc(when)
        if d == ref:
            today.append(name)
        elif d > ref and name not in future:
            future[name] = (d - ref).days
    if not future:
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING,
                            notes=["No scheduled major release is known after this close."])
    nearest = min(future, key=lambda k: (future[k], k))
    close_at = ref + (pd.Timedelta(days=1) if ctx.kind != "equity" else pd.Timedelta(hours=21))
    value = {
        "warning": future[nearest] <= params["days"], "days_to_next": future[nearest], "next": nearest,
        "days_to_fed": future.get("fed"), "days_to_cpi": future.get("cpi"), "days_to_jobs": future.get("jobs"),
        "released_today": bool(today), "today": sorted(today)[0] if today else None,
    }
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=value,
                        observed_at=iso(min(close_at, ctx.now)), available_at=iso(min(close_at, ctx.now)),
                        evidence={"events_known": len(loaded.get("events") or [])},
                        provenance=["Federal Reserve and BLS release schedules"], notes=[])
