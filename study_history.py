"""
Saved daily positioning history for "What followed" studies (written by history_backfill.py to the reports branch,
data/derivatives/<COIN>-USD.csv.gz; it stops at 29 Oct 2024, like the saved prices).

A study evaluates a Set as at the close of each day. The loader below gives the engine a derivatives record holding
only the daily series up to that day, so the daily positioning signals (positioning.funding, positioning.long_short)
never see a later day. Hourly positioning is never saved, so hourly signals stay unavailable in studies.
"""

from __future__ import annotations

import bisect
from pathlib import Path

import pandas as pd

# Signals a study can read from saved history (what_followed.studyable), with the first day it covers.
SAVED_SINCE = {"positioning.funding": "2020-01", "positioning.long_short": "2020-05"}


class SavedHistory:
    def __init__(self, folder: str | Path):
        """folder: the saved data folder (holding prices/ and derivatives/)."""
        self.folder = Path(folder)
        self._coins: dict = {}

    def _coin(self, symbol: str):
        if symbol not in self._coins:
            path = self.folder / "derivatives" / f"{symbol}.csv.gz"
            if not path.exists():
                self._coins[symbol] = None
            else:
                d = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
                t = [int(pd.Timestamp(x).tz_localize("UTC").timestamp()) for x in d["date"]]
                markets = str(d["markets"].dropna().iloc[0]).split("|") if d["markets"].notna().any() else []
                self._coins[symbol] = (t, {k: d[k].tolist() for k in ("funding", "ls")}, markets)
        return self._coins[symbol]

    def derivatives_at(self, symbol: str, day):
        """A derivatives loader for the engine as at the close of `day` (crypto only)."""
        day = pd.Timestamp(day)
        day = day.tz_localize("UTC") if day.tzinfo is None else day
        limit = int(day.normalize().timestamp())

        def load(kind: str, asset_id: str) -> dict:
            got = self._coin(symbol) if kind == "crypto" else None
            if got is None:
                return {"error": "No saved positioning history for this asset."}
            t, cols, markets = got
            n = bisect.bisect_right(t, limit)
            if not n:
                return {"error": "No saved positioning history before this day."}
            clean = lambda v: None if v is None or v != v else float(v)  # noqa: E731
            return {"status": "ok", "markets": markets, "updated_at": (day + pd.Timedelta(days=1)).isoformat(),
                    "daily": {"t": t[:n], **{k: [clean(v) for v in vals[:n]] for k, vals in cols.items()}}}

        return load
