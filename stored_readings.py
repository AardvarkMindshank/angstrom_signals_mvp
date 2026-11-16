"""Readings worked out by the background worker and saved next to the prices (16 Nov 2026).

Working out one asset's readings (indicators, Trend/Stretch/Flow, the table's figures) takes about half a second.
The page did it whenever an asset's price had changed, which is every 5 minutes for crypto, so most visits waited
several seconds for it. Now the worker that saves the prices (run_alerts.py → shared_refresh.py) works them out
from the very bars it saves and stores them on the same row ("readings"). The page uses them only when they were
made from exactly the bars it has, by the same definitions, in the same hour; anything else, it works them out
itself as before. Only the worker can write them (the asset_market write guard keeps them as they are for
signed-in accounts).
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone

import pandas as pd


def _hour(now: datetime | None = None) -> str:
    """The hour a reading belongs to, as the page's own score memory counts it (UTC)."""
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H")


def _fingerprint(frame: pd.DataFrame) -> dict:
    return {"bars": int(len(frame)), "close": float(frame["close"].iloc[-1]),
            "last": pd.Timestamp(frame.index[-1]).strftime("%Y-%m-%d")}


def build(frame: pd.DataFrame, kind: str) -> dict | None:
    """The readings to save, worked out from the bars as the page will read them back (frame_from_records)."""
    import group_readings
    import signals_view
    from scoring import calculate_indicators

    if frame is None or frame.empty or len(frame) < 15:
        return None
    fields = signals_view.row_fields(calculate_indicators(frame), kind)
    if not isinstance(fields, dict):
        return None
    return {"version": group_readings.FINGERPRINT, "hour": _hour(), **_fingerprint(frame), "fields": fields}


def use(row: dict | None, frame: pd.DataFrame) -> dict | None:
    """The saved readings for these bars, or None when they don't match exactly (then the page works them out)."""
    import group_readings

    saved = (row or {}).get("readings") if isinstance(row, dict) else None
    if not isinstance(saved, dict) or not isinstance(saved.get("fields"), dict):
        return None
    if frame is None or frame.empty or "close" not in frame.columns:
        return None
    if saved.get("version") != group_readings.FINGERPRINT or saved.get("hour") != _hour():
        return None
    mine = _fingerprint(frame)
    if any(saved.get(name) != value for name, value in mine.items()):
        return None
    return copy.deepcopy(saved["fields"])
