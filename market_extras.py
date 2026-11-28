"""The shared market extras the classic app's server used to look up behind the scenes while members browsed: each
stock's next earnings date, market cap and rank, and asset logos. The background worker (run_alerts.py) now keeps
them up to date for every watched and funnel asset, so they stay fresh in both apps and after the classic app is
retired. Each step is capped per run and never holds up the alert pass. Logs carry counts only."""
from __future__ import annotations

import time
from datetime import datetime, timezone

EARNINGS_SECONDS = 12 * 3600          # as the classic app: a stock's report date is looked up twice a day
EARNINGS_PER_RUN = 30
STOCK_CAPS_PER_RUN = 40
LOGOS_PER_RUN = 20


def _rows(supabase, keys: list[str]) -> dict:
    out = {}
    for i in range(0, len(keys), 150):
        try:
            data = (supabase.table("asset_market")
                    .select("asset_key, kind, asset_id, logo_url, market_stats_updated_at, next_earnings, earnings_checked_at")
                    .in_("asset_key", keys[i:i + 150]).execute().data or [])
        except Exception as exc:
            print(f"Market extras: rows not read ({str(exc)[:120]})")
            continue
        out.update({r["asset_key"]: r for r in data if isinstance(r, dict) and r.get("asset_key")})
    return out


def earnings_due(catalog: dict, rows: dict, now: float | None = None) -> list[str]:
    """Stocks whose report date was never looked up, or not in the last 12 hours; the oldest first."""
    from market_store import _stored_at, asset_market_key

    now = now or time.time()
    due = []
    for kind, aid in catalog:
        if kind != "Stock":
            continue
        checked = _stored_at((rows.get(asset_market_key(kind, aid)) or {}).get("earnings_checked_at"))
        if checked is None or now - checked >= EARNINGS_SECONDS:
            due.append((checked or 0.0, str(aid).upper()))
    return [t for _c, t in sorted(due)]


def keep_known(found: dict, rows: dict, today: str) -> dict:
    """A "no date" answer never wipes a known report date that is still ahead (the classic app's rule)."""
    from market_store import asset_market_key

    out = {}
    for ticker, when in found.items():
        before = str((rows.get(asset_market_key("Stock", ticker)) or {}).get("next_earnings") or "")[:10]
        out[ticker] = when or (before if before and before >= today else None)
    return out


def refresh_due(supabase, catalog: dict) -> None:
    from data_fetchers import crypto_logo_urls, crypto_market_stats, stock_logo_url, stock_market_caps, stock_next_earnings
    from market_store import asset_market_key, save_earnings, save_logos, save_market_stats

    keys = [asset_market_key(k, a) for k, a in catalog]
    rows = _rows(supabase, keys)
    # Stocks someone opened (an asset page, a search) but nobody watches: their report date is looked up too, once,
    # so an asset page never says "no date" just because the stock isn't on a watchlist.
    try:
        extra = (supabase.table("asset_market").select("asset_key, kind, asset_id, logo_url, market_stats_updated_at, "
                                                       "next_earnings, earnings_checked_at")
                 .eq("kind", "Stock").is_("earnings_checked_at", "null").limit(EARNINGS_PER_RUN).execute().data or [])
        for r in extra:
            if r.get("asset_id") and r.get("asset_key") not in rows:
                rows[r["asset_key"]] = r
                catalog = {**catalog, ("Stock", str(r["asset_id"]).upper()): None} if isinstance(catalog, dict) else catalog
    except Exception:
        pass
    minute = datetime.now(timezone.utc).minute
    try:
        due = earnings_due(catalog, rows)[:EARNINGS_PER_RUN]
        if due:
            found = keep_known(stock_next_earnings(due), rows, datetime.now(timezone.utc).date().isoformat())
            save_earnings(supabase, found)
            print(f"Earnings dates: {len(found)} of {len(due)} stocks answered")
    except Exception as exc:
        print(f"Earnings dates skipped: {str(exc)[:160]}")
    if minute % 30 < 5:                # market cap and rank, twice an hour (the classic app kept them 30 minutes)
        try:
            coins = [a for k, a in catalog if k == "Crypto"]
            stats = crypto_market_stats(coins) if coins else {}
            stocks = [str(a).upper() for k, a in catalog if k == "Stock"][:STOCK_CAPS_PER_RUN]
            caps = stock_market_caps(stocks) if stocks else {}
            save_market_stats(supabase, [{"kind": "Crypto", "asset_id": c, "cap": s.get("cap"), "rank": s.get("rank")}
                                         for c, s in stats.items()]
                              + [{"kind": "Stock", "asset_id": t, "cap": c, "rank": None} for t, c in caps.items()])
            print(f"Market caps: {len(stats)} coins, {len(caps)} stocks")
        except Exception as exc:
            print(f"Market caps skipped: {str(exc)[:160]}")
    if minute < 5:                     # missing logos, once an hour
        try:
            lacking = [(k, a) for k, a in catalog
                       if not str((rows.get(asset_market_key(k, a)) or {}).get("logo_url") or "").startswith("https://")]
            coins = [a for k, a in lacking if k == "Crypto"][:LOGOS_PER_RUN]
            stocks = [str(a).upper() for k, a in lacking if k == "Stock"][:LOGOS_PER_RUN]
            fresh = [{"kind": "Crypto", "asset_id": c, "logo_url": u} for c, u in (crypto_logo_urls(coins) if coins else {}).items()]
            for t in stocks:
                url = stock_logo_url(t)
                if url:
                    fresh.append({"kind": "Stock", "asset_id": t, "logo_url": url})
            save_logos(supabase, fresh)
            if lacking:
                print(f"Logos: {len(fresh)} found of {len(lacking)} missing")
        except Exception as exc:
            print(f"Logos skipped: {str(exc)[:160]}")
