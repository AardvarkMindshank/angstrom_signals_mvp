"""What MarketNavi read at a trade's entry and exit (Trade Log spec v0.5, "Stored history" and snapshot rules).

Readings worked out from prices (the regime; Trend, Stretch and Flow) are rebuilt for each moment by the same code
the dashboard uses, from daily bars that had finished before that moment, so nothing from later can leak in. Where
the daily record (readings_daily) shows what MarketNavi actually saved for that bar before the trade, the snapshot
is "observed"; otherwise "reconstructed". Inputs that are not prices can't be rebuilt, so they come from what was
saved at the time: asset and market sentiment (sentiment_history), the crypto Fear & Greed index (Alternative.me's
daily history) and the VIX (the Tides record). A reading with nothing saved near the time says so.

Research hold-out: these snapshots use data after 30 Oct 2024 because that is when the trades happened. They are for
the member's logbook only and must never feed research statistics, studies or signal tuning.

Everything here is pure: the sync (tradelog_sync.py) loads the data and passes it in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

MIN_BARS = 60
SENTIMENT_WINDOW = timedelta(days=3)
USE = "logbook"                              # never research


def _when(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def rebuild(bars, kind: str, moment: datetime) -> dict | None:
    """The regime and Trend/Stretch/Flow from daily bars that finished before the moment's day (UTC), or None."""
    import group_readings
    import pandas as pd
    import stored_readings
    from scoring import calculate_indicators

    if bars is None or len(bars) == 0:
        return None
    day = pd.Timestamp(moment.astimezone(timezone.utc).date())
    index = pd.DatetimeIndex(bars.index)
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)
    earlier = bars[index.normalize() < day]
    if len(earlier) < MIN_BARS:
        return None
    result = group_readings.score(calculate_indicators(earlier.tail(500)), kind, moment)
    row = stored_readings.daily_row("x", {"version": result.get("fingerprint"), "fields": {"signals": result}})
    if not row:
        return None
    return {k: row[k] for k in ("day", "trend", "stretch", "flow", "regime", "version")}


def observed_for(rebuilt: dict | None, record: dict, moment: datetime) -> dict | None:
    """The daily record's row for the rebuilt bar, if MarketNavi had saved it before the moment."""
    if not rebuilt:
        return None
    row = record.get(rebuilt["day"])
    seen = _when((row or {}).get("first_seen_at"))
    return row if row and seen and seen <= moment else None


def latest_before(series, moment: datetime, window: timedelta | None = None):
    """The last (time, value) at or before the moment, optionally no older than the window; None otherwise."""
    best = None
    for when, value in series or []:
        t = _when(when)
        if t is None or value is None or t > moment:
            continue
        if window is not None and moment - t > window:
            continue
        if best is None or t > best[0]:
            best = (t, value)
    return best


def daily_before(series, moment: datetime):
    """The last daily value dated before the moment's day (a day's close is known once the day is over)."""
    day = moment.astimezone(timezone.utc).date().isoformat()
    best = None
    for d, value in series or []:
        d = str(d)[:10]
        if value is None or d >= day:
            continue
        if best is None or d > best[0]:
            best = (d, value)
    return best


def snapshot(trip: dict, moment_name: str, *, bars=None, kind: str = "Stock", record: dict | None = None,
             asset_sentiment=None, market_sentiment=None, fear_greed=None, vix=None) -> dict:
    """One snapshot row for trade_snapshots: {readings, source, definitions}."""
    moment = _when(trip["opened_at"] if moment_name == "entry" else trip["closed_at"])
    crypto = trip.get("asset_class") == "crypto"
    readings: dict = {"use": USE}

    rebuilt = rebuild(bars, kind, moment) if trip.get("asset_key") else None
    seen = observed_for(rebuilt, record or {}, moment)
    source = "observed" if seen else "reconstructed" if rebuilt else "unavailable"
    base = seen or rebuilt
    if base:
        readings.update({"bar": rebuilt["day"], "regime": base.get("regime"), "trend": base.get("trend"),
                         "stretch": base.get("stretch"), "flow": base.get("flow")})

    fear = daily_before(fear_greed if crypto else vix, moment)
    readings["fear"] = ({"name": "Fear & Greed" if crypto else "VIX", "value": fear[1], "day": fear[0]}
                        if fear else {"name": "Fear & Greed" if crypto else "VIX", "value": None})
    for key, series in (("asset_sentiment", asset_sentiment), ("market_sentiment", market_sentiment)):
        hit = latest_before(series, moment, SENTIMENT_WINDOW)
        readings[key] = {"value": float(hit[1]), "at": hit[0].isoformat()} if hit else {"value": None}
    return {"readings": readings, "source": source, "definitions": str((rebuilt or {}).get("version") or "")[:64]}
