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


SENTIMENT_ROWS = 400     # newest observations read per subject (about 6 months at two a day)


def sentiment_loader(supabase):
    """sentiment_history rows for one subject (crypto, stock, or an asset key such as Crypto|sui), oldest first.
    first_seen_at is included once the column exists (sql/2026-11-05_sentiment_first_seen.sql)."""
    def load(subject_key: str) -> dict:
        columns = "score, recorded_at, model, coverage, events, sources"
        rows = None
        for cols in (columns + ", first_seen_at", columns):
            try:
                rows = (supabase.table("sentiment_history").select(cols).eq("subject_key", subject_key)
                        .order("recorded_at", desc=True).limit(SENTIMENT_ROWS).execute().data or [])
                break
            except Exception:
                continue
        if rows is None:
            return {"error": "Sentiment history could not be read."}
        if not rows:
            return {"error": f"No stored sentiment for {subject_key}."}
        return {"rows": list(reversed(rows))}
    return load


OPTIONS_DAYS = 10        # days of options snapshots read per subject (the signal uses the newest one)
OPTIONS_COLUMNS = "recorded_at, expiry, spot, max_pain, call_oi, put_oi, source, first_seen_at"


def options_loader(supabase):
    """options_pain rows for one subject (Crypto|bitcoin, Stock|AAPL), oldest first."""
    def load(subject_key: str) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(days=OPTIONS_DAYS)).isoformat()
        try:
            rows = (supabase.table("options_pain").select(OPTIONS_COLUMNS).eq("asset_key", subject_key)
                    .gte("recorded_at", since).order("recorded_at").limit(2000).execute().data or [])
        except Exception:
            return {"error": "Options snapshots could not be read (run sql/2026-11-21_options_pain.sql)."}
        if not rows:
            return {"error": f"No options snapshots stored for {subject_key.split('|', 1)[-1]} yet."}
        return {"rows": rows}
    return load
