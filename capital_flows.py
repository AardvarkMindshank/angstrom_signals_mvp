"""Observed capital flows: collection only (no display, no signal yet).

What is collected, and why: see the "Capital flows: data availability audit" doc. Two free daily series
at market level, both observed money rather than price-and-volume proxies:

- Bitcoin spot ETF net flows (all US funds, and per fund), from the TFTC tracker.
- Total stablecoin supply (sum of all stablecoins' circulating USD value), from DefiLlama.

Every source has an entry in SOURCES recording its licence, commercial-use and redistribution terms,
attribution, upgrade path and what must happen before a commercial launch. Only sources whose status
is "active" are fetched. A source whose terms allow development use but not commercial redistribution
would be "isolated" (fetched, stored, never shown to users) until it is replaced or upgraded; one whose
terms our use would break is "inactive" and never fetched.

Storage (table capital_flow_observations, see sql/2026-11-03_capital_flows.sql) is append-only: a row
per (source, series, subject, date, value). A revised value is a new row; the first published value is
the one with the earliest fetched_at. Rows loaded from a source's history on the first run are marked
backfilled, so research knows when a value was really available (see is_point_in_time).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AngstromSignals/1.0; research)"}
REFRESH_SECONDS = 6 * 60 * 60          # a few looks a day; both sources publish at most daily
RECENT_DAYS = 14                       # days re-read on each refresh, so revisions are caught

# ----------------------------------------------------------------------------- source register

SOURCES = {
    "tftc_btc_etf": {
        "name": "The Commoner Bitcoin ETF Tracker (TFTC)",
        "url": "https://www.tftc.io/bitcoin-etf-flows/data.json",
        "docs": "https://www.tftc.io/bitcoin-etf-flows/methodology",
        "measures": "Daily net creations minus redemptions of US spot Bitcoin ETFs, US$, total and per fund",
        "kind": "observed",
        "scope": "market (Bitcoin)",
        "frequency": "daily, at least one session behind; newest day can be revised",
        "history": "since 2024-01-11",
        "licence": "CC BY 4.0",
        "commercial_use": "allowed",
        "redistribution": "allowed with attribution",
        "attribution": "Source: The Commoner Bitcoin ETF Tracker by TFTC (tftc.io/bitcoin-etf-flows), data through {date}.",
        "cost": "free",
        "upgrade_path": "SoSoValue paid API or a paid ETF-flow vendor if more coins or an SLA are needed (price not checked)",
        "before_launch": "Show the credit line wherever the data appears. Upstream is SoSoValue and issuer "
                         "disclosures via Farside; confirm continuity or contract a primary source.",
        "status": "active",
    },
    "defillama_stablecoins": {
        "name": "DefiLlama stablecoins API",
        "url": "https://stablecoins.llama.fi/stablecoincharts/all",
        "docs": "https://apis.io/apis/defillama/defillama-stablecoins-api/",
        "measures": "Daily total circulating supply of all stablecoins, in US$ (change = net issuance)",
        "kind": "observed",
        "scope": "market (crypto)",
        "frequency": "daily points",
        "history": "multi-year",
        "licence": "listed as open data (full terms to confirm)",
        "commercial_use": "to confirm",
        "redistribution": "to confirm",
        "attribution": "Source: DefiLlama (defillama.com).",
        "cost": "free public API, no key",
        "upgrade_path": "DefiLlama Pro API, about $300 a month (higher limits)",
        "before_launch": "Confirm DefiLlama's terms allow showing derived figures in a paid product.",
        "status": "active",
    },
    "coinmetrics_community": {
        "name": "Coin Metrics Community API",
        "url": "https://community-api.coinmetrics.io/v4",
        "docs": "https://docs.coinmetrics.io/service-and-support/coverage",
        "measures": "On-chain metrics, possibly exchange flows (which metrics are free not confirmed)",
        "kind": "estimate (labelled wallets)",
        "scope": "per coin",
        "licence": "CC BY-NC",
        "commercial_use": "not allowed",
        "redistribution": "non-commercial only",
        "cost": "free",
        "upgrade_path": "Coin Metrics Pro (price not checked)",
        "before_launch": "Needs a commercial licence before any use in Angstrom.",
        "status": "inactive",   # Angstrom is a business: even development use is not clearly non-commercial
    },
    "farside": {
        "name": "Farside Investors ETF flow tables",
        "url": "https://farside.co.uk/",
        "measures": "Daily Bitcoin, Ether and Solana ETF flows",
        "kind": "observed, partly estimated",
        "scope": "market",
        "licence": "not stated",
        "commercial_use": "not stated",
        "redistribution": "not stated",
        "cost": "free to view; no API",
        "upgrade_path": "Ask Farside for permission, or a paid ETF-flow API",
        "before_launch": "Not used: no stated terms and no API (scraping would need permission).",
        "status": "inactive",
    },
}


def active_sources() -> list[str]:
    return [key for key, spec in SOURCES.items() if spec.get("status") in ("active", "isolated")]


def user_visible(source: str) -> bool:
    """Only active sources may ever be shown to users; isolated ones are stored for research only."""
    return SOURCES.get(source, {}).get("status") == "active"


# ----------------------------------------------------------------------------- parsing (no network)

def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _day(value) -> str | None:
    """YYYY-MM-DD from a date string or a unix timestamp (seconds, as number or string)."""
    if value is None:
        return None
    text = str(value).strip()
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text), timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_tftc(payload: dict) -> list[dict]:
    """Observations from TFTC data.json: total net flow, total net assets, and each fund's flow (US$).
    A market holiday (net flow 0 and no per-fund split) is skipped."""
    rows = []
    for day in (payload or {}).get("days") or []:
        if not isinstance(day, dict):
            continue
        date = _day(day.get("date"))
        flow = _number(day.get("netFlowUsd"))
        per_fund = day.get("perEtfUsd") if isinstance(day.get("perEtfUsd"), dict) else {}
        if date is None or flow is None or (flow == 0 and not per_fund):
            continue
        rows.append(_row("tftc_btc_etf", "etf_net_flow", "BTC", date, flow))
        assets = _number(day.get("totalNetAssetsUsd"))
        if assets is not None:
            rows.append(_row("tftc_btc_etf", "etf_total_net_assets", "BTC", date, assets))
        for fund, value in per_fund.items():
            amount = _number(value)
            if amount is not None and str(fund).strip():
                rows.append(_row("tftc_btc_etf", "etf_net_flow", f"BTC:{str(fund).strip().upper()[:12]}", date, amount))
    return rows


def parse_defillama_total(payload) -> list[dict]:
    """Observations from DefiLlama stablecoincharts/all: total circulating supply in US$ per day
    (the sum over all pegs of totalCirculatingUSD)."""
    rows = []
    for point in payload if isinstance(payload, list) else []:
        if not isinstance(point, dict):
            continue
        date = _day(point.get("date"))
        totals = point.get("totalCirculatingUSD")
        if date is None or not isinstance(totals, dict):
            continue
        values = [_number(v) for v in totals.values()]
        values = [v for v in values if v is not None]
        if values:
            rows.append(_row("defillama_stablecoins", "stablecoin_supply", "ALL", date, sum(values)))
    return rows


def _row(source: str, series: str, subject: str, date: str, value: float) -> dict:
    spec = SOURCES[source]
    return {"source": source, "series": series, "subject": subject, "observed_date": date,
            "value": round(float(value), 2), "unit": "USD", "kind": spec["kind"]}


def is_point_in_time(row: dict) -> bool:
    """True when fetched_at is a fair 'available from' time: not loaded from a history backfill."""
    return not bool(row.get("backfilled"))


# ----------------------------------------------------------------------------- fetch and store

FETCHERS = {
    "tftc_btc_etf": parse_tftc,
    "defillama_stablecoins": parse_defillama_total,
}


def fetch(source: str, getter=None) -> list[dict]:
    spec = SOURCES[source]
    if spec.get("status") not in ("active", "isolated"):
        raise PermissionError(f"{source} is {spec.get('status')}: not fetched")
    get = getter or (lambda url: requests.get(url, headers=_HEADERS, timeout=30))
    response = get(spec["url"])
    response.raise_for_status()
    return FETCHERS[source](response.json())


def _last_fetch(supabase, source: str) -> float | None:
    """When this source was last fetched (from the fetch log), or None."""
    rows = (
        supabase.table("capital_flow_fetches").select("fetched_at")
        .eq("source", source).order("fetched_at", desc=True).limit(1).execute().data or []
    )
    if not rows:
        return None
    try:
        return datetime.fromisoformat(str(rows[0]["fetched_at"]).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _has_rows(supabase, source: str) -> bool:
    rows = supabase.table("capital_flow_observations").select("source").eq("source", source).limit(1).execute().data
    return bool(rows)


def _log_fetch(supabase, source: str, ok: bool, rows: int, latest: str | None, note: str = "") -> None:
    try:
        supabase.table("capital_flow_fetches").insert({
            "source": source, "ok": ok, "rows_sent": rows, "latest_date": latest, "note": note[:300],
        }).execute()
    except Exception as exc:
        print(f"Capital flows: fetch log not written for {source}: {str(exc)[:120]}")


def store(supabase, rows: list[dict], backfilled: bool, now: datetime | None = None) -> int:
    """Insert observations; an identical (source, series, subject, date, value) is ignored."""
    if not rows:
        return 0
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    payload = [dict(r, fetched_at=stamp, backfilled=bool(backfilled)) for r in rows]
    for start in range(0, len(payload), 500):
        (
            supabase.table("capital_flow_observations")
            .upsert(payload[start:start + 500], on_conflict="source,series,subject,observed_date,value",
                    ignore_duplicates=True)
            .execute()
        )
    return len(payload)


def recent(rows: list[dict], days: int = RECENT_DAYS) -> list[dict]:
    dates = sorted({r["observed_date"] for r in rows})
    keep = set(dates[-days:])
    return [r for r in rows if r["observed_date"] in keep]


def refresh_due_flows(supabase, now: float | None = None, getter=None) -> None:
    """Fetch each active source when its last fetch (in the fetch log) is older than REFRESH_SECONDS.
    The first run loads the full history (marked backfilled); later runs store only the most recent
    days, so a revision becomes a new row and the first published value is kept."""
    now = time.time() if now is None else now
    for source in active_sources():
        try:
            last = _last_fetch(supabase, source)
            first_run = not _has_rows(supabase, source)
        except Exception as exc:
            print(f"Capital flows skipped (run sql/2026-11-03_capital_flows.sql): {str(exc)[:120]}")
            return
        if last is not None and now - last < REFRESH_SECONDS:
            continue
        try:
            rows = fetch(source, getter)
        except Exception as exc:
            _log_fetch(supabase, source, False, 0, None, f"fetch failed: {exc}")
            print(f"Capital flows: {source} not fetched: {str(exc)[:160]}")
            continue
        latest = max((r["observed_date"] for r in rows), default=None)
        if not rows:
            _log_fetch(supabase, source, False, 0, None, "no rows parsed: the format may have changed")
            print(f"Capital flows: {source} returned nothing usable (format change?).")
            continue
        chosen = rows if first_run else recent(rows)
        try:
            written = store(supabase, chosen, backfilled=first_run)
        except Exception as exc:
            _log_fetch(supabase, source, False, 0, latest, f"store failed: {exc}")
            print(f"Capital flows: {source} not stored: {str(exc)[:160]}")
            continue
        _log_fetch(supabase, source, True, written, latest, "backfill" if first_run else "")
        print(f"Capital flows: {source} {'backfilled' if first_run else 'refreshed'}, {written} rows sent, "
              f"latest {latest}.")
