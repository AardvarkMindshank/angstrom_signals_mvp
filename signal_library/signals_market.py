"""
Priority 2 signals from stored market data: capital flows and derivatives positioning.

Capital flows (market-level context, not asset signals):
- Values are read with their publication history: each day's latest revision, the time Angstrom first
  saw it (first_seen) and whether that first sighting was a history backfill. A backfilled day's
  availability time is unknown, so it is flagged and excluded in point-in-time mode.
- ETF net flows are creations minus redemptions of US spot Bitcoin ETFs. Stablecoin supply change is net
  issuance across all stablecoins; it is not evidence of money going into Bitcoin or any particular coin.

Derivatives (crypto only): from the coin's stored Coinalyze record. Open interest, funding, long/short
ratio and liquidations are reported data; the price-and-open-interest reading is an inference, and the
liquidation levels are estimates. Each output says which.
"""

from __future__ import annotations

import math

import pandas as pd

import capital_flows

from .core import (
    CONFIRMED, INSUFFICIENT, LEVELS, MISSING, OBSERVATION, OK, SCOPE_CRYPTO_ASSET, SCOPE_MARKET_BTC,
    SCOPE_MARKET_CRYPTO, STALE, Param, SignalResult, iso, signal,
)

COINALYZE = "Coinalyze (open interest, funding, long/short, liquidations), stored about hourly"


# ============================================================================ point-in-time flows

def daily_values(rows: list[dict], as_of=None, point_in_time: bool = False) -> pd.DataFrame:
    """One row per (subject, day): the value known at `as_of` (latest revision by then), when it was first
    seen, and whether that first sighting was a backfill. point_in_time=True drops backfilled sightings,
    because their real publication time is unknown."""
    if not rows:
        return pd.DataFrame(columns=["subject", "date", "value", "first_seen", "backfilled", "revisions"])
    df = pd.DataFrame(rows)
    df["fetched_at"] = pd.to_datetime(df["fetched_at"], utc=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["backfilled"] = df.get("backfilled", False)
    df["backfilled"] = df["backfilled"].fillna(False).astype(bool)
    if point_in_time:
        df = df[~df["backfilled"]]
    if as_of is not None:
        cutoff = pd.Timestamp(as_of)
        cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff
        df = df[df["fetched_at"] <= cutoff]
    if df.empty:
        return pd.DataFrame(columns=["subject", "date", "value", "first_seen", "backfilled", "revisions"])
    df = df.sort_values("fetched_at")
    grouped = df.groupby(["subject", "observed_date"], sort=True)
    out = pd.DataFrame({
        "value": grouped["value"].last(),
        "first_seen": grouped["fetched_at"].first(),
        "backfilled": grouped["backfilled"].first(),
        "revisions": grouped["value"].nunique() - 1,
    }).reset_index().rename(columns={"observed_date": "date"})
    return out.sort_values(["subject", "date"]).reset_index(drop=True)


def _attribution(source: str, date: str) -> str:
    spec = capital_flows.SOURCES[source]
    return spec["attribution"].replace("{date}", str(date))


def _flow_rows(ctx, source, series, subject):
    loaded = ctx.capital_flows(source, series, subject)
    if loaded.get("error"):
        return None, SignalResult(ref={}, subject=ctx.subject, status=MISSING, notes=[loaded["error"]])
    return loaded["rows"], None


def _stale(latest_date: str, now, max_days: int) -> bool:
    return (pd.Timestamp(now).tz_convert("UTC").normalize().tz_localize(None) - pd.Timestamp(latest_date)).days > max_days


FLOW_PARAMS = {"point_in_time": Param(False, "bool", doc="ignore backfilled history (for research replays)")}


@signal(
    id="flows.btc_etf", version=1, name="Bitcoin spot ETF net flows", category="flows",
    output=OBSERVATION, unit="USD", scope=SCOPE_MARKET_BTC, timeframes=("1D",), requires=("capital_flows",),
    params=FLOW_PARAMS,
    calculation=("From stored daily observations (TFTC tracker): the latest session's total net flow; sums over the last "
                 "5 and 20 sessions; the previous 5-session sum and the change between them (acceleration); and each "
                 "fund's latest flow. Each day uses its latest revision; first_seen and backfill are kept."),
    interpretation=("Net creations minus redemptions across US spot Bitcoin ETFs: observed money moving into or out of "
                    "the funds. Market context for Bitcoin; it is not a forecast."),
    limitations=("Published after the US session (at least one day late) and the newest day can be revised. US trading "
                 "days only. Values before Angstrom started collecting are a backfill: when they were really published "
                 "is not known."),
)
def flows_btc_etf(ctx, timeframe, params):
    rows, failed = _flow_rows(ctx, "tftc_btc_etf", "etf_net_flow", "BTC")
    if failed:
        return failed
    table = daily_values(rows, as_of=ctx.now, point_in_time=params["point_in_time"])
    total = table[table["subject"] == "BTC"]
    if len(total) < 5:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=[f"{len(total)} sessions stored."])
    values = total["value"].tolist()
    latest = total.iloc[-1]
    sum5, sum20 = sum(values[-5:]), sum(values[-20:]) if len(values) >= 20 else None
    prev5 = sum(values[-10:-5]) if len(values) >= 10 else None
    per_fund = {}
    fund_rows, _ = _flow_rows(ctx, "tftc_btc_etf", "etf_net_flow", "BTC:*")
    if fund_rows:
        funds = daily_values(fund_rows, as_of=ctx.now, point_in_time=params["point_in_time"])
        today = funds[funds["date"] == latest["date"]]
        per_fund = {r["subject"].split(":", 1)[1]: round(float(r["value"]), 2)
                    for _, r in today.sort_values("value", key=abs, ascending=False).iterrows()}
    value = {
        "latest_date": str(latest["date"]), "latest_net_flow_usd": round(float(latest["value"]), 2),
        "sum_5_sessions_usd": round(sum5, 2), "sum_20_sessions_usd": None if sum20 is None else round(sum20, 2),
        "previous_5_sessions_usd": None if prev5 is None else round(prev5, 2),
        "change_in_5_session_sum_usd": None if prev5 is None else round(sum5 - prev5, 2),
        "sessions_in_window": len(values), "per_fund_latest_usd": per_fund,
        "latest_revisions": int(latest["revisions"]),
    }
    stale = _stale(str(latest["date"]), ctx.now, 5)
    return SignalResult(
        ref={}, subject=ctx.subject, status=STALE if stale else OK, confirmation=CONFIRMED, value=value,
        observed_at=iso(latest["date"]), available_at=iso(latest["first_seen"]), backfilled=bool(latest["backfilled"]),
        evidence={"last_sessions": [{"date": str(r["date"]), "usd": float(r["value"]), "first_seen": iso(r["first_seen"]),
                                     "backfilled": bool(r["backfilled"])} for _, r in total.tail(10).iterrows()]},
        provenance=[_attribution("tftc_btc_etf", latest["date"])],
        notes=(["Newest stored session is more than 5 days old."] if stale else [])
        + (["This session was loaded from history, not observed live."] if bool(latest["backfilled"]) else []),
    )


@signal(
    id="flows.stablecoin_supply", version=1, name="Stablecoin supply change", category="flows",
    output=OBSERVATION, unit="USD", scope=SCOPE_MARKET_CRYPTO, timeframes=("1D",), requires=("capital_flows",),
    params=FLOW_PARAMS,
    calculation=("From stored daily totals (DefiLlama, all stablecoins): latest supply; change over 7 and 30 calendar "
                 "days in US$ and %; the 7-day change before that and the difference between them (acceleration)."),
    interpretation=("Net issuance of stablecoins: more dollars available on crypto rails. It is not evidence that money "
                    "entered Bitcoin or any particular coin."),
    limitations=("A daily total; issuer mints and burns can be lumpy. The newest day can be revised. History loaded on the "
                 "first run is a backfill."),
)
def flows_stablecoins(ctx, timeframe, params):
    rows, failed = _flow_rows(ctx, "defillama_stablecoins", "stablecoin_supply", "ALL")
    if failed:
        return failed
    table = daily_values(rows, as_of=ctx.now, point_in_time=params["point_in_time"])
    if len(table) < 15:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=[f"{len(table)} days stored."])
    series = table.set_index(pd.to_datetime(table["date"]))["value"]
    latest_day = series.index[-1]

    def at(days):
        before = series[series.index <= latest_day - pd.Timedelta(days=days)]
        return None if before.empty else float(before.iloc[-1])

    now_v = float(series.iloc[-1])
    v7, v14, v30 = at(7), at(14), at(30)
    change7 = None if v7 is None else now_v - v7
    prior7 = None if v7 is None or v14 is None else v7 - v14
    change30 = None if v30 is None else now_v - v30
    latest = table.iloc[-1]
    value = {
        "latest_date": str(latest["date"]), "supply_usd": round(now_v, 2),
        "change_7d_usd": None if change7 is None else round(change7, 2),
        "change_7d_pct": None if change7 is None else round(change7 / v7 * 100, 4),
        "change_30d_usd": None if change30 is None else round(change30, 2),
        "change_30d_pct": None if change30 is None else round(change30 / v30 * 100, 4),
        "previous_7d_change_usd": None if prior7 is None else round(prior7, 2),
        "acceleration_7d_usd": None if change7 is None or prior7 is None else round(change7 - prior7, 2),
    }
    stale = _stale(str(latest["date"]), ctx.now, 3)
    return SignalResult(
        ref={}, subject=ctx.subject, status=STALE if stale else OK, confirmation=CONFIRMED, value=value,
        observed_at=iso(latest["date"]), available_at=iso(latest["first_seen"]), backfilled=bool(latest["backfilled"]),
        provenance=[capital_flows.SOURCES["defillama_stablecoins"]["name"]],
        notes=["Net issuance across all stablecoins; not a measure of money entering a specific asset."]
        + (["Newest stored day is more than 3 days old."] if stale else []),
    )


# ============================================================================ derivatives positioning

def _derivatives(ctx):
    record = ctx.derivatives()
    if not record or record.get("error"):
        return None, None, SignalResult(ref={}, subject=ctx.subject, status=MISSING,
                                        notes=[(record or {}).get("error") or "No derivatives record."])
    series = record.get("series") or {}
    t = series.get("t") or []
    if len(t) < 25:
        return None, None, SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT,
                                        notes=["Fewer than 25 hourly points stored."])
    frame = pd.DataFrame({k: series.get(k) for k in ("price", "oi", "ls", "funding", "liq_long", "liq_short")},
                         index=pd.to_datetime([int(x) for x in t], unit="s", utc=True))
    frame = frame.apply(pd.to_numeric, errors="coerce").sort_index()
    return record, frame, None


def _age_hours(record, now) -> float | None:
    try:
        stamp = pd.Timestamp(record.get("updated_at"))
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp
        return (pd.Timestamp(now) - stamp).total_seconds() / 3600
    except Exception:
        return None


def _base(ctx, record, frame, value, evidence, notes, max_age=3.0):
    age = _age_hours(record, ctx.now)
    stale = age is None or age > max_age
    return SignalResult(
        ref={}, subject=ctx.subject, status=STALE if stale else OK, confirmation=CONFIRMED, value=value,
        observed_at=iso(frame.index[-1]), available_at=iso(record.get("updated_at")), evidence=evidence,
        provenance=[COINALYZE] + [f"markets: {', '.join(record.get('markets') or [])}"],
        notes=list(notes) + ([f"Stored record is {age:.1f} hours old." if age is not None else "Record time unknown."]
                             if stale else []),
    )


def _pct(now, then):
    if now is None or then is None or not then or any(map(lambda v: isinstance(v, float) and math.isnan(v), (now, then))):
        return None
    return round((now - then) / abs(then) * 100, 3)


@signal(
    id="positioning.oi_price", version=1, name="Open interest and price (24h)", category="positioning",
    output=OBSERVATION, unit="% and labels", scope=SCOPE_CRYPTO_ASSET, timeframes=("1h",), requires=("derivatives",),
    params={"hours": Param(24, "int", 4, 160, doc="window in hours")},
    calculation=("From the stored hourly series: open interest (US$, summed across the coin's main perpetual markets) "
                 "and price now versus `hours` ago, as % changes; the inferred positioning reading from their "
                 "combination; latest and average funding over the window; long/short account ratio now and its change."),
    interpretation=("Rising open interest with rising price suggests new longs (build-up); with falling price, new shorts. "
                    "Falling open interest with rising price suggests shorts closing; with falling price, longs closing "
                    "(unwinding). These readings are inferences from two reported numbers, not observed trades."),
    limitations=("Covers the markets Coinalyze reports for the coin, not every venue. Open interest in US$ also moves with "
                 "price itself. Funding is shown as reported per funding interval."),
)
def positioning_oi_price(ctx, timeframe, params):
    record, frame, failed = _derivatives(ctx)
    if failed:
        return failed
    now_row = frame.iloc[-1]
    then = frame[frame.index <= frame.index[-1] - pd.Timedelta(hours=params["hours"])]
    if then.empty:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["Window longer than stored history."])
    then_row = then.iloc[-1]
    oi_change, price_change = _pct(now_row["oi"], then_row["oi"]), _pct(now_row["price"], then_row["price"])
    reading = None
    if oi_change is not None and price_change is not None:
        if oi_change > 0:
            reading = "long build-up (inferred)" if price_change > 0 else "short build-up (inferred)"
        elif oi_change < 0:
            reading = "short covering (inferred)" if price_change > 0 else "long unwinding (inferred)"
    window = frame[frame.index > then.index[-1]]
    value = {
        "open_interest_usd": None if pd.isna(now_row["oi"]) else round(float(now_row["oi"]), 2),
        "open_interest_change_pct": oi_change, "price_change_pct": price_change, "positioning_reading": reading,
        "funding_latest": None if pd.isna(now_row["funding"]) else float(now_row["funding"]),
        "funding_average": None if window["funding"].dropna().empty else round(float(window["funding"].mean()), 6),
        "long_short_ratio": None if pd.isna(now_row["ls"]) else float(now_row["ls"]),
        "long_short_ratio_change": None if pd.isna(now_row["ls"]) or pd.isna(then_row["ls"])
        else round(float(now_row["ls"] - then_row["ls"]), 4),
        "window_hours": params["hours"],
    }
    return _base(ctx, record, frame, value, {"from": iso(then.index[-1]), "to": iso(frame.index[-1])},
                 ["Open interest, funding and long/short ratio are reported; the positioning reading is inferred."])


@signal(
    id="positioning.liquidations", version=1, name="Liquidations (24h)", category="positioning",
    output=OBSERVATION, unit="USD", scope=SCOPE_CRYPTO_ASSET, timeframes=("1h",), requires=("derivatives",),
    params={"hours": Param(24, "int", 1, 160, doc="window in hours")},
    calculation=("Sum of reported long and short liquidations (US$) over the window across the coin's markets, the longs' "
                 "share of the total, and the largest single hour."),
    interpretation="Which side has been forced out recently, and how much. Reported data.",
    limitations="Exchanges under-report liquidations; totals are a floor, not the full amount.",
)
def positioning_liquidations(ctx, timeframe, params):
    record, frame, failed = _derivatives(ctx)
    if failed:
        return failed
    window = frame[frame.index > frame.index[-1] - pd.Timedelta(hours=params["hours"])]
    longs, shorts = float(window["liq_long"].fillna(0).sum()), float(window["liq_short"].fillna(0).sum())
    total = longs + shorts
    biggest = (window["liq_long"].fillna(0) + window["liq_short"].fillna(0))
    value = {"longs_usd": round(longs, 2), "shorts_usd": round(shorts, 2), "total_usd": round(total, 2),
             "longs_share_pct": None if not total else round(longs / total * 100, 2),
             "largest_hour_usd": round(float(biggest.max()), 2) if len(biggest) else None,
             "largest_hour": iso(biggest.idxmax()) if len(biggest) and biggest.max() > 0 else None,
             "window_hours": params["hours"]}
    return _base(ctx, record, frame, value, {"hours_in_window": len(window)}, ["Reported liquidations (a lower bound)."])


@signal(
    id="positioning.liquidation_levels", version=1, name="Nearest estimated liquidation levels", category="positioning",
    output=LEVELS, unit="price", scope=SCOPE_CRYPTO_ASSET, timeframes=("1h",), requires=("derivatives",),
    calculation=("From the stored liquidation-level estimate (open interest added over the last 7 days, spread over a "
                 "typical leverage mix): the nearest and the largest estimated long-liquidation level below price and "
                 "short-liquidation level above, with their distance from price in % and their estimated US$."),
    interpretation="Where leveraged positions would be forced closed if price got there, by estimate.",
    limitations=("An estimate from public open interest, not exchange order data: actual leverage and stops are unknown. "
                 "Not a liquidation heatmap."),
)
def positioning_liq_levels(ctx, timeframe, params):
    record, frame, failed = _derivatives(ctx)
    if failed:
        return failed
    if record.get("status") != "ok":
        return SignalResult(ref={}, subject=ctx.subject, status=MISSING, notes=["No liquidation-level estimate for this coin."])
    price = float(frame["price"].dropna().iloc[-1])

    def clean(rows, side):
        out = []
        for r in rows or []:
            try:
                p, usd = float(r.get("price")), float(r.get("usd"))
            except (TypeError, ValueError):
                continue
            if p > 0 and usd > 0 and ((side == "longs" and p < price) or (side == "shorts" and p > price)):
                out.append({"price": p, "usd_estimate": round(usd, 2), "distance_pct": round((p - price) / price * 100, 3)})
        return out

    longs, shorts = clean(record.get("longs"), "longs"), clean(record.get("shorts"), "shorts")
    pick = lambda rows, key: (min(rows, key=key) if rows else None)  # noqa: E731
    value = {
        "price": price,
        "nearest_long_level": pick(longs, lambda r: abs(r["distance_pct"])),
        "largest_long_level": max(longs, key=lambda r: r["usd_estimate"]) if longs else None,
        "nearest_short_level": pick(shorts, lambda r: abs(r["distance_pct"])),
        "largest_short_level": max(shorts, key=lambda r: r["usd_estimate"]) if shorts else None,
        "levels_below": len(longs), "levels_above": len(shorts),
    }
    return _base(ctx, record, frame, value, {"all_long_levels": longs, "all_short_levels": shorts},
                 ["Estimated levels, not observed liquidations."], max_age=3.0)
