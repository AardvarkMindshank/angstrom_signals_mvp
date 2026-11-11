"""
Display replays (design section 6): reconstruct what signals say at a past time T from current providers, to show
on screen. Descriptive only.

- Any date may be shown, including dates in the protected hold-out period, because nothing here produces a
  statistic: this module has no way to save, export in bulk or score its results, and research code refuses its
  results (signal_library.replay_research.accept). A guard test keeps research and statistics modules from
  importing this one.
- Requests are capped (MAX_DISPLAY_STEPS time steps per run).
- Results are "reconstructed as of T": providers revise data, so a later display replay may differ; the replay
  record keeps a hash of the exact inputs used so a difference is detectable.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .replay import (
    DISPLAY, FLOW_DAYS, RECONSTRUCTED, RECONSTRUCTED_LIMITED, SPLIT_LIMITATION, CandleHistory, ReplayRun, utc,
)

MAX_DISPLAY_STEPS = 90


def live_candles(kind: str, asset_id: str, timeframe: str, range_key: str | None = None):
    """The longest candle history the chart can load for this timeframe (or the range asked for), without the forming
    candle."""
    import chart_data

    ranges = [r for r in reversed(chart_data.RANGES) if chart_data.availability(timeframe, r)[0]]
    if range_key and range_key in ranges:
        ranges = [range_key]
    if not ranges:
        return {"error": f"No {timeframe} candles available."}
    loaded = chart_data.load_candles(kind, asset_id, timeframe, ranges[0])
    if loaded.get("error"):
        return {"error": loaded["error"]}
    candles = loaded["candles"]
    raw = candles[~candles["forming"].astype(bool)] if "forming" in candles.columns else candles
    if raw.empty:
        return {"error": f"No closed {timeframe} candles."}
    crypto = kind == "crypto"
    source = {
        "provider": loaded.get("source") or "Yahoo Finance via chart_data",
        "quality": RECONSTRUCTED if crypto else RECONSTRUCTED_LIMITED,
        "limitations": [] if crypto else [SPLIT_LIMITATION],
        "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "range_loaded": ranges[0], "history_from": raw.index[0].isoformat(),
    }
    return CandleHistory(raw, timeframe, kind, loaded.get("session"), source)


def flows_as_of(supabase):
    """Stored flow rows for a replay at T: observed in the live loader's day window before T and first seen by T.
    Backfilled rows are never used in replays."""
    def load(source: str, series: str, subject: str, as_of) -> dict:
        t = utc(as_of)
        since = (t - pd.Timedelta(days=FLOW_DAYS)).date().isoformat()
        query = (supabase.table("capital_flow_observations")
                 .select("subject, observed_date, value, fetched_at, backfilled")
                 .eq("source", source).eq("series", series).gte("observed_date", since)
                 .lte("fetched_at", t.isoformat()).eq("backfilled", False))
        query = query.like("subject", subject.replace("*", "%")) if "*" in subject else query.eq("subject", subject)
        rows = query.order("observed_date").limit(20000).execute().data or []
        if not rows:
            return {"error": f"No stored {series} observations from {source} first seen by {t.isoformat()}."}
        return {"rows": rows}
    return load


def sentiment_as_of(supabase):
    """Stored sentiment rows the database had received by T (first_seen_at), newest 400, oldest first. Without the
    first_seen_at column the rows come back without it and the replay treats sentiment as live only."""
    def load(subject_key: str, as_of) -> dict:
        t = utc(as_of)
        try:
            rows = (supabase.table("sentiment_history")
                    .select("score, recorded_at, model, coverage, events, sources, first_seen_at")
                    .eq("subject_key", subject_key).lte("first_seen_at", t.isoformat())
                    .order("recorded_at", desc=True).limit(400).execute().data or [])
        except Exception:
            return {"rows": [{"recorded_at": None}]}       # no first_seen_at column yet: live only
        if not rows:
            return {"error": f"No stored sentiment for {subject_key} first seen by {t.isoformat()}."}
        return {"rows": list(reversed(rows))}
    return load


def options_as_of(supabase):
    """Stored options snapshots the database had received by T (first_seen_at), from the 10 days before T."""
    from .loaders import OPTIONS_COLUMNS, OPTIONS_DAYS

    def load(subject_key: str, as_of) -> dict:
        t = utc(as_of)
        try:
            rows = (supabase.table("options_pain").select(OPTIONS_COLUMNS).eq("asset_key", subject_key)
                    .gte("recorded_at", (t - pd.Timedelta(days=OPTIONS_DAYS)).isoformat())
                    .lte("first_seen_at", t.isoformat()).order("recorded_at").limit(2000).execute().data or [])
        except Exception:
            return {"error": "Options snapshots could not be read."}
        if not rows:
            return {"error": f"No options snapshot for {subject_key.split('|', 1)[-1]} first seen by {t.isoformat()}."}
        return {"rows": rows}
    return load


def display_run(supabase=None, *, max_steps: int = MAX_DISPLAY_STEPS, candles=None, **kwargs) -> ReplayRun:
    return ReplayRun(DISPLAY, candles or live_candles, flows=flows_as_of(supabase) if supabase is not None else None,
                     sentiment=sentiment_as_of(supabase) if supabase is not None else None,
                     options=options_as_of(supabase) if supabase is not None else None,
                     max_steps=min(max_steps, MAX_DISPLAY_STEPS), **kwargs)
