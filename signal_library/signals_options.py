"""
Options max pain as a Signal Library signal.

    options.max_pain   where price sits against the max-pain strike of an options expiry

Max pain is the strike at which the open option contracts of one expiry would be worth the least at expiry (the
most option buyers lose). It is often said that price is drawn towards it as expiry nears. The evidence for that
is thin and mixed (strongest for large stocks in the last days before a monthly expiry), so this signal is
descriptive: it reports the distance, the side and the days left, and a Set decides what to make of them.

Read from options_pain (append-only snapshots taken by the background worker: Deribit's public book for Bitcoin
and Ethereum, about every 4 hours; Yahoo option chains for watched equities, once a day). Nobody publishes a
history of open interest, so the history is our own and starts on the day the snapshots began.
- The latest snapshot at or before the evaluation time is used; in a replay, only rows the database had received
  by then (first_seen_at, set by the database itself).
- price is the underlying price recorded with the snapshot, so distance and side describe the same moment.
- No snapshot is missing data, never a guess. Coins other than Bitcoin and Ethereum are unsupported.
"""

from __future__ import annotations

import pandas as pd

from .core import (
    CONFIRMED, MISSING, OBSERVATION, OK, SCOPE_ASSET, STALE, UNSUPPORTED, Param, SignalResult, iso, signal,
)

OPTION_COINS = {"bitcoin": "BTC", "ethereum": "ETH"}
STALE_HOURS = {"crypto": 12, "equity": 96}          # crypto every ~4 hours; equities daily, over weekends
SOURCE = {"crypto": "Deribit public options book (open interest by strike)",
          "equity": "Yahoo Finance option chains (open interest by strike)"}
LIMITATIONS = ("Max pain is a description of where open options would expire cheapest, not a price target; the "
               "evidence that price is drawn to it is thin and mixed. Crypto covers Bitcoin and Ethereum only "
               "(Deribit). Equities need a listed options chain. History starts when the snapshots began "
               "(November 2026) and is replayable only from when each snapshot first reached the database.")
PARAMS = {
    "min_days": Param(0, "int", 0, 60, doc="skip expiries closer than this many days (0 = the nearest expiry)"),
    "monthly": Param(False, "bool", doc="monthly expiries only (equities: third Friday; crypto: last Friday)"),
    "near_pct": Param(2.0, "float", 0.1, 20, doc="within this % of max pain counts as at max pain"),
}


def subject_key(ctx) -> str | None:
    identity = str(ctx.asset_id or "").strip()
    if ctx.kind == "equity":
        return f"Stock|{identity.upper()}"
    if ctx.kind == "crypto" and identity.lower() in OPTION_COINS:
        return f"Crypto|{identity.lower()}"
    return None


def expiry_moment(day: str, market: str) -> pd.Timestamp:
    """When an expiry settles: Deribit at 08:00 UTC; US equity options at the 16:00 New York close."""
    d = pd.Timestamp(str(day)[:10])
    if market == "crypto":
        return d.tz_localize("UTC") + pd.Timedelta(hours=8)
    return (d + pd.Timedelta(hours=16)).tz_localize("America/New_York").tz_convert("UTC")


def is_monthly(day: str, market: str) -> bool:
    d = pd.Timestamp(str(day)[:10])
    if market == "crypto":                              # the last Friday of the month
        return d.weekday() == 4 and (d + pd.Timedelta(days=7)).month != d.month
    # the third Friday, or the Thursday before it when the Friday is a market holiday
    return (d.weekday() == 4 and 15 <= d.day <= 21) or (d.weekday() == 3 and 14 <= d.day <= 20)


def _utc(value):
    try:
        t = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _number(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


@signal(id="options.max_pain", version=1, name="Options max pain", category="positioning", output=OBSERVATION,
        unit="% from max pain", scope=SCOPE_ASSET, timeframes=("1D", "4h"), requires=("options",),
        limitations=LIMITATIONS, params=PARAMS,
        polarity="positive distance = price above max pain (descriptive)",
        calculation=("From the newest stored options snapshot at or before the evaluation time: the first expiry "
                     "still ahead that is at least min_days away (monthly expiries only if monthly is on). "
                     "max_pain = the strike at which that expiry's open calls and puts would be worth the least. "
                     "distance_pct = (price - max_pain) / max_pain x 100, with price the underlying price recorded "
                     "with the snapshot. side = at when |distance_pct| <= near_pct, else above or below. "
                     "days_to_expiry = time to settlement (Deribit 08:00 UTC; US options 16:00 New York) in days. "
                     "expiry_week = 7 days or fewer. put_call_ratio = put / call open interest. Stale after 12 "
                     "hours (crypto) or 96 hours (equities)."),
        interpretation=("How far price is from the strike where options would expire cheapest, and how soon. Some "
                        "traders expect price to drift towards max pain into expiry; treat it as context."))
def options_max_pain(ctx, timeframe, params):
    market = "equity" if ctx.kind == "equity" else "crypto"
    key = subject_key(ctx)
    if key is None:
        return SignalResult(ref={}, subject=ctx.subject, status=UNSUPPORTED,
                            notes=["No options market we can read for this asset (crypto: Bitcoin and Ethereum "
                                   "on Deribit only)."])
    loaded = ctx.options(key)
    if loaded.get("error"):
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING, notes=[loaded["error"]])
    now = ctx.now
    rows = []
    for r in loaded.get("rows") or []:
        when = _utc(r.get("recorded_at"))
        if when is None or when > now or _number(r.get("max_pain")) is None or not r.get("expiry"):
            continue
        rows.append((when, r))
    if not rows:
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING,
                            notes=[f"No options snapshot recorded by {iso(now)}."])
    taken = max(w for w, _ in rows)
    snapshot = [r for w, r in rows if w == taken]
    choices = []
    for r in snapshot:
        settles = expiry_moment(r["expiry"], market)
        days = (settles - now).total_seconds() / 86400
        if days <= 0 or days < params["min_days"]:
            continue
        if params["monthly"] and not is_monthly(r["expiry"], market):
            continue
        choices.append((settles, r))
    if not choices:
        what = "monthly expiry" if params["monthly"] else "expiry"
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING,
                            notes=[f"The snapshot of {iso(taken)} has no {what} at least {params['min_days']} days "
                                   "ahead."])
    settles, row = min(choices, key=lambda c: (c[0], str(c[1]["expiry"])))
    pain = _number(row["max_pain"])
    price = _number(row.get("spot"))
    calls, puts = _number(row.get("call_oi")), _number(row.get("put_oi"))
    distance = None if price is None or not pain else round((price - pain) / pain * 100, 4)
    side = None if distance is None else ("at" if abs(distance) <= params["near_pct"]
                                          else "above" if distance > 0 else "below")
    days = round((settles - now).total_seconds() / 86400, 4)
    age_h = (now - taken).total_seconds() / 3600
    value = {
        "max_pain": pain, "price": price, "distance_pct": distance, "side": side,
        # The expiry is written as a label ("21 Jun 2024"), not an ISO date: a replay result carries no timestamp
        # after its cutoff, and an expiry is always ahead. days_to_expiry carries the timing.
        "expiry": f"{settles.day} {settles.strftime('%b %Y')}", "days_to_expiry": days,
        "expiry_week": days <= 7, "monthly_expiry": is_monthly(row["expiry"], market),
        "call_open_interest": calls, "put_open_interest": puts,
        "put_call_ratio": None if not calls or puts is None else round(puts / calls, 4),
        "recorded_at": iso(taken), "age_hours": round(age_h, 2), "subject_key": key,
        "source": row.get("source") or SOURCE[market],
    }
    notes = []
    stale = age_h > STALE_HOURS[market]
    if stale:
        notes.append(f"The newest options snapshot is {age_h:.0f} hours old (stale after {STALE_HOURS[market]}).")
    if price is None:
        notes.append("The snapshot has no underlying price, so distance and side are unknown.")
    seen = row.get("first_seen_at")
    return SignalResult(
        ref={}, subject=ctx.subject, status=STALE if stale else OK, confirmation=CONFIRMED, value=value,
        observed_at=iso(taken), available_at=iso(seen) if seen else iso(taken),
        evidence={"snapshot_rows": len(snapshot), "snapshots_read": len({w for w, _ in rows}),
                  "first_seen_recorded": seen is not None},
        provenance=[SOURCE[market]], notes=notes)
