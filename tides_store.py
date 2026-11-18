"""
Where the Tides signals read their daily rows (signal_library/signals_tides.py), 18 Nov 2026.

- To 29 Oct 2024: data/tides_history.csv.gz, the point-in-time history built by tides_history.py on GitHub (saved on
  the reports branch, data/tides/, and copied here after checking). Each row counts as seen at 21:30 UTC on its
  day, after that day's US close.
- From 30 Oct 2024: the tides_daily table, added to by the background worker (sql/2026-12-05_tides_daily.sql). Each
  row counts from the time the database first saw it (first_seen_at).
- Storm warnings: data/tides_events.csv (Fed decisions, CPI and jobs-report release days to Oct 2024) plus the
  macro calendar (macro_calendar.py) for later dates.

Every row carries recorded_at (the US close it describes, 21:15 UTC: after the VIX closes) and first_seen_at, the
same pair the sentiment rows use, so replays cut them by the same rule.
"""

from __future__ import annotations

import time
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"
HISTORY = DATA / "tides_history.csv.gz"
EVENTS = DATA / "tides_events.csv"
RECORDED = pd.Timedelta(hours=21, minutes=15)
SEEN = pd.Timedelta(hours=21, minutes=30)
TTL = 3600                       # seconds the recent rows are kept before reading the table again
MAJOR = ("fomc", "cpi", "jobs")

# Release days between the saved history and the macro calendar's first entries (BLS and Fed schedules).
BRIDGE = (("jobs", "2024-11-01"), ("cpi", "2024-11-13"), ("jobs", "2024-12-06"), ("cpi", "2024-12-11"),
          ("jobs", "2025-01-10"))

_SUPABASE = None
_RECENT: dict = {"at": 0.0, "rows": []}


def configure(supabase) -> None:
    """The app and the worker hand over their database client once; without one only the saved history is read."""
    global _SUPABASE
    _SUPABASE = supabase


def _stamp(day: str, offset: pd.Timedelta) -> str:
    return (pd.Timestamp(day, tz="UTC") + offset).isoformat()


@lru_cache(maxsize=1)
def history_rows() -> tuple:
    if not HISTORY.exists():
        return ()
    table = pd.read_csv(HISTORY, index_col="date")
    out = []
    for day, row in table.iterrows():
        body = {k: (v.item() if hasattr(v, "item") else v) for k, v in row.items() if pd.notna(v)}
        out.append({**body, "day": str(day)[:10], "recorded_at": _stamp(day, RECORDED),
                    "first_seen_at": _stamp(day, SEEN), "source": "saved history"})
    return tuple(out)


def recent_rows() -> list[dict]:
    if _SUPABASE is None:
        return []
    if time.time() - _RECENT["at"] < TTL:
        return _RECENT["rows"]
    try:
        got = (_SUPABASE.table("tides_daily").select("day, body, first_seen_at").order("day")
               .limit(5000).execute().data or [])
    except Exception:
        got = []
    rows = [{**(r.get("body") or {}), "day": str(r["day"])[:10], "recorded_at": _stamp(r["day"], RECORDED),
             "first_seen_at": r["first_seen_at"], "source": "daily record"} for r in got]
    _RECENT.update(at=time.time(), rows=rows)
    return rows


@lru_cache(maxsize=1)
def events() -> tuple:
    rows = []
    if EVENTS.exists():
        rows = [(str(k), str(d)[:10]) for k, d in pd.read_csv(EVENTS)[["kind", "date"]].itertuples(index=False)]
    last = {k: max((d for kk, d in rows if kk == k), default="") for k in MAJOR}    # per kind: each list ends apart
    rows += [e for e in BRIDGE if e[1] > last[e[0]]]
    try:
        import macro_calendar as mc

        for e in mc.events():
            day = pd.Timestamp(e["at"]).tz_convert("America/New_York").strftime("%Y-%m-%d")
            if e["kind"] in MAJOR and day > last[e["kind"]]:
                rows.append((e["kind"], day))
    except Exception:
        pass
    return tuple(sorted(set(rows), key=lambda e: (e[1], e[0])))


def load() -> dict:
    """The default loader for a DataContext: every row and event (the signal picks what was known by its time)."""
    saved = list(history_rows())
    last = saved[-1]["day"] if saved else ""
    rows = saved + [r for r in recent_rows() if r["day"] > last]
    if not rows:
        return {"error": "No Tides readings are available."}
    return {"rows": rows, "events": [list(e) for e in events()]}


def replay_source(as_of) -> dict:
    """For display and research replays: the same rows (the replay cuts them at its time)."""
    return load()
