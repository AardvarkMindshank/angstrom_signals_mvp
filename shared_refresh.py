"""Shared price history and sentiment, written once and read by every account.

The background worker replaces prices on the technical clock and sentiment on
the sentiment clock. A session writes a row only when that asset has none yet.
"""

from __future__ import annotations

import os
import time

import pandas as pd

from data_fetchers import crypto_ticker, fetch_crypto_data, fetch_stock_data, period_for_days
from market_store import (
    asset_market_key,
    frame_from_row,
    load_market_moods,
    load_shared_market,
    row_timestamp,
    save_market_mood,
    save_price_frame,
    save_sentiment,
    sentiment_from_row,
    sentiment_refresh_due,
    technical_refresh_due,
)
from sentiment import (
    MACRO_MOODS,
    analyze_market_mood,
    analyze_market_sentiment,
    sentiment_query,
    sentiment_ready,
)

PRICE_HISTORY_CAP = 730
# How many sentiment writes one worker run will start. The oldest go first.
SENTIMENT_BATCH = 4


def canonical_asset_id(kind: str, asset_id: str) -> str:
    """The id stored on the shared row."""
    return asset_market_key(kind, asset_id).split("|", 1)[1]


def next_update(stored_at: float | None, interval: float) -> float | None:
    """When the next shared update is due. None when nothing has been saved yet."""
    if stored_at is None:
        return None
    return float(stored_at) + float(interval)


def slice_history(frame: pd.DataFrame | None, days: int) -> pd.DataFrame:
    """The tail of stored bars this account uses for its own score and chart."""
    if frame is None or frame.empty:
        return pd.DataFrame() if frame is None else frame
    count = max(15, int(days or 200))
    return frame.tail(count)


def fetch_bars(kind: str, asset_id: str, days: int):
    """One price download. The same bars are then stored for every account."""
    span = max(15, min(int(days or 200), PRICE_HISTORY_CAP))
    if kind == "Crypto":
        return fetch_crypto_data(asset_id, span)
    return fetch_stock_data(asset_id, period=period_for_days(span))


def create_price_row(supabase, kind: str, asset_id: str, days: int):
    """Save the first price history for an asset that has none.

    Returns the bars, an error, and whether the row was stored. The bars are
    still returned when storage is not ready, so this session can score them.
    """
    frame, err = fetch_bars(kind, asset_id, max(int(days or 200), 200))
    if err or frame is None or frame.empty or len(frame) < 15:
        return pd.DataFrame(), err or "No price history.", False
    saved = save_price_frame(supabase, kind, asset_id, frame)
    if not saved:
        print("Shared prices could not be saved. Run the latest supabase_rls.sql.")
    return slice_history(frame, days), None, saved


def read_or_create_bars(supabase, kind: str, asset_id: str, days: int):
    """Stored bars, or one new save when this asset has no price history yet.

    A row that exists is returned as it was saved, even when the next update is due.
    The third value is True only when this call wrote the first row.
    """
    key = asset_market_key(kind, asset_id)
    row = load_shared_market(supabase, [key]).get(key)
    frame = frame_from_row(row)
    if len(frame) >= 15:
        return slice_history(frame, days), None, False
    created, err, saved = create_price_row(supabase, kind, asset_id, days)
    if err:
        return pd.DataFrame(), err, False
    return created, None, saved


def ensure_new_asset(supabase, kind: str, asset_id: str, label: str, days: int) -> None:
    """Write the first sentiment and prices when this asset is not stored yet."""
    key = asset_market_key(kind, asset_id)
    row = load_shared_market(supabase, [key]).get(key) or {}
    if len(frame_from_row(row)) < 15:
        _created, _err, _saved = create_price_row(supabase, kind, asset_id, days)
        row = load_shared_market(supabase, [key]).get(key) or row
    report, _stored_at = sentiment_from_row(row)
    if report and report.get("ok"):
        return
    if not sentiment_ready():
        return
    ticker = crypto_ticker(asset_id) if kind == "Crypto" else asset_id
    report = analyze_market_sentiment(sentiment_query(kind, label, ticker), True)
    if report.get("ok"):
        save_sentiment(supabase, kind, asset_id, report, time.time())


def refresh_price_catalog(supabase, catalog: dict, days: int) -> dict:
    """Replace price history that is missing or older than the technical clock.

    catalog maps (kind, asset_id) to a display label. The returned frames are
    keyed by (kind, canonical id) and still need slicing to one account's history.
    """
    keys = [asset_market_key(kind, asset_id) for kind, asset_id in catalog]
    stored = load_shared_market(supabase, keys) if keys else {}
    frames = {}
    refreshed = 0
    for kind, asset_id in catalog:
        identity = canonical_asset_id(kind, asset_id)
        row = stored.get(asset_market_key(kind, asset_id))
        frame = frame_from_row(row)
        due = technical_refresh_due(row_timestamp(row, "prices_updated_at"))
        if due or len(frame) < 15:
            try:
                fetched, err = fetch_bars(kind, asset_id, days)
            except Exception as exc:
                print(f"Price refresh failed for {identity}: {exc}")
                fetched, err = None, str(exc)
            if err:
                print(err)
            elif fetched is not None and len(fetched) >= 15:
                if save_price_frame(supabase, kind, asset_id, fetched):
                    refreshed += 1
                frame = fetched
        if frame is not None and len(frame) >= 15:
            frames[(kind, identity)] = frame
    print(f"Shared prices: {refreshed} refreshed, {len(frames)} ready.")
    return frames


def _force_market_mood() -> bool:
    """True only when this worker run was started to rewrite both market reports."""
    return os.getenv("FORCE_MARKET_MOOD", "").strip().lower() in {"1", "true", "yes"}


def _save_mood(supabase, spec: dict, force: bool = False) -> None:
    report = analyze_market_mood(spec["key"], spec["label"], spec["query"], True, force=force)
    if report.get("ok"):
        save_market_mood(supabase, spec["key"], spec["query"], report, time.time())
        readings = sum(len(group.get("items") or []) for group in (report.get("gauges") or []))
        print(f"Saved {spec['label']} sentiment with {readings} readings.")
    else:
        print(f"Sentiment skipped for {spec['label']}: {report.get('reason') or 'not saved'}")


def _save_asset_sentiment(supabase, kind: str, asset_id: str, label: str) -> None:
    ticker = crypto_ticker(asset_id) if kind == "Crypto" else asset_id
    report = analyze_market_sentiment(sentiment_query(kind, label, ticker), True)
    if report.get("ok"):
        save_sentiment(supabase, kind, asset_id, report, time.time())
        print(f"Saved sentiment for {label or asset_id}.")
    else:
        print(f"Sentiment skipped for {label or asset_id}: {report.get('reason') or 'not saved'}")


def refresh_due_sentiment(supabase, catalog: dict) -> None:
    """Replace market and asset sentiment that is older than the sentiment clock.

    One run writes at most SENTIMENT_BATCH scores, oldest first, so a large
    watchlist does not hold up the price and alert pass. A run started with
    FORCE_MARKET_MOOD also rewrites the crypto and stock reports immediately.
    """
    if not sentiment_ready():
        print("Shared sentiment skipped: set the XAI_API_KEY secret for the background worker.")
        return
    slots = SENTIMENT_BATCH
    force_moods = _force_market_mood()
    if force_moods:
        print("Shared sentiment: rewriting crypto and stock market sentiment on this run.")
    moods = load_market_moods(supabase) or {}
    for spec in MACRO_MOODS:
        row = moods.get(spec["key"]) if isinstance(moods, dict) else None
        due = sentiment_refresh_due(row_timestamp(row, "sentiment_updated_at"))
        if not due and not force_moods:
            continue
        if due:
            if slots <= 0:
                break
            slots -= 1
        try:
            _save_mood(supabase, spec, force=force_moods)
        except Exception as exc:
            print(f"Sentiment failed for {spec['label']}: {exc}")
    if slots <= 0 or not catalog:
        print("Shared sentiment: batch finished.")
        return
    keys = [asset_market_key(kind, asset_id) for kind, asset_id in catalog]
    stored = load_shared_market(supabase, keys)
    now = time.time()
    due = []
    for (kind, asset_id), label in catalog.items():
        row = stored.get(asset_market_key(kind, asset_id))
        stored_at = row_timestamp(row, "sentiment_updated_at")
        if not sentiment_refresh_due(stored_at):
            continue
        age = now - stored_at if stored_at is not None else 10**12
        due.append((age, kind, asset_id, str(label or asset_id)))
    due.sort(reverse=True)
    for _age, kind, asset_id, label in due[:slots]:
        try:
            _save_asset_sentiment(supabase, kind, asset_id, label)
        except Exception as exc:
            print(f"Sentiment failed for {label}: {exc}")
    print("Shared sentiment: batch finished.")
