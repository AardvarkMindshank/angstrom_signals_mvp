"""
Supabase-backed loaders for a DataContext (stored data only; no new tables, no extra API calls).

- derivatives: the coin's stored Leverage & liquidations record in asset_market.liq_levels
  (Coinalyze, refreshed about hourly by the worker; about 7 days of hourly series).
- capital flows: capital_flow_observations (append-only; first-seen times; backfill flag).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

FLOW_DAYS = 120   # days of flow history read; enough for 20-session and 30-day windows


def derivatives_loader(supabase):
    from market_store import asset_market_key

    def load(kind: str, asset_id: str) -> dict:
        if kind != "crypto":
            return {"error": "Derivatives data covers crypto only."}
        rows = (supabase.table("asset_market").select("liq_levels, liq_updated_at")
                .eq("asset_key", asset_market_key("Crypto", asset_id)).limit(1).execute().data or [])
        if not rows or not isinstance(rows[0].get("liq_levels"), dict):
            return {"error": "No stored derivatives record for this coin yet (made about hourly for watched coins)."}
        record = dict(rows[0]["liq_levels"])
        record["updated_at"] = rows[0].get("liq_updated_at")
        return record
    return load


def flows_loader(supabase):
    def load(source: str, series: str, subject: str) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(days=FLOW_DAYS)).date().isoformat()
        query = (supabase.table("capital_flow_observations")
                 .select("subject, observed_date, value, fetched_at, backfilled")
                 .eq("source", source).eq("series", series).gte("observed_date", since))
        query = query.like("subject", subject.replace("*", "%")) if "*" in subject else query.eq("subject", subject)
        rows = query.order("observed_date").limit(20000).execute().data or []
        if not rows:
            return {"error": f"No stored {series} observations from {source}."}
        return {"rows": rows}
    return load
