"""
Research replays (design section 6): reconstructions that may feed statistics, tests or parameter choices.

- They read ONLY the frozen, versioned development dataset (the research price cache on the reports branch,
  data/prices). Each file is read and parsed whole; rows dated on or after the hold-out start (2024-10-30) are then
  filtered out immediately, before the data is returned, so they never reach signal evaluation, statistics or caches.
- Requests for any T on or after the hold-out start are refused before data is touched (signal_library.replay).
- Every run records the dataset: where it lives, the manifest hash and the hash of every file actually read, plus
  the code and execution environment (clarification 2 of the review: the data itself is kept, on the reports
  branch, not only its hashes).
- `accept` is the gate for anything that computes statistics: it refuses results that did not come from here.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from .replay import (
    HOLDOUT_START, RECONSTRUCTED, RECONSTRUCTED_LIMITED, RESEARCH, CandleHistory, ReplayRefused, ReplayRun,
)

US_SESSION = ("America/New_York", 9 * 60 + 30, 16 * 60)
ADJUSTED_LIMITATION = ("Research share prices are split- and dividend-adjusted daily bars downloaded once: historical "
                       "price levels, and indicators derived from them, can differ from what traders saw at the time.")
CUT_RULE = ("each file is read and parsed whole; rows dated on or after 2024-10-30 are filtered out immediately, before "
            "the data is returned, so they never reach signal evaluation")


class FrozenDailyCandles:
    """Daily (and weekly, grouped from daily) candles from the frozen research cache. Asset ids are its tickers."""

    research_dataset = True

    def __init__(self, prices_dir, *, location: str | None = None, reports_commit: str | None = None):
        self.folder = Path(prices_dir)
        manifest_bytes = (self.folder / "manifest.json").read_bytes()
        self.manifest = json.loads(manifest_bytes)
        self.dataset = {
            "name": "research price cache (frozen development data)",
            "location": location or "reports branch: data/prices",
            "reports_commit": reports_commit,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "downloaded_at": self.manifest.get("downloaded_at"),
            "cut_rule": CUT_RULE,
            "files_read": {},
        }
        self._daily: dict = {}

    def _read(self, ticker: str) -> pd.DataFrame | None:
        if ticker not in self._daily:
            info = (self.manifest.get("files") or {}).get(ticker)
            if not info:
                self._daily[ticker] = None
                return None
            data = (self.folder / info["file"]).read_bytes()
            with gzip.open(io.BytesIO(data), "rt", encoding="utf-8") as handle:
                frame = pd.read_csv(handle, index_col="date", parse_dates=["date"])
            frame = frame.sort_index()
            frame = frame.loc[frame.index < HOLDOUT_START.tz_localize(None)]       # hold-out rows are dropped here, before the data is returned
            frame = frame[["open", "high", "low", "close", "volume"]].astype(float)
            frame.index = pd.DatetimeIndex(frame.index).tz_localize("UTC")
            self.dataset["files_read"][ticker] = {"file": info["file"], "sha256": hashlib.sha256(data).hexdigest(),
                                                  "rows_kept": int(len(frame)),
                                                  "last_kept": frame.index[-1].date().isoformat() if len(frame) else None}
            self._daily[ticker] = frame
        return self._daily[ticker]

    def __call__(self, kind: str, asset_id: str, timeframe: str):
        if timeframe not in ("1D", "1W"):
            return {"error": "The frozen research dataset holds daily candles only (1D, and 1W grouped from them)."}
        daily = self._read(asset_id)
        if daily is None or daily.empty:
            return {"error": f"{asset_id} is not in the frozen research dataset."}
        crypto = str(asset_id).upper().endswith("-USD")
        if (kind == "crypto") != crypto:
            return {"error": f"{asset_id} is not a {kind} asset in the research dataset."}
        import chart_data

        raw = chart_data.group_weekly(daily) if timeframe == "1W" else daily
        source = {"provider": "frozen research price cache (Yahoo daily bars, downloaded once)",
                  "quality": RECONSTRUCTED if crypto else RECONSTRUCTED_LIMITED,
                  "limitations": [] if crypto else [ADJUSTED_LIMITATION],
                  "dataset_file": self.dataset["files_read"][asset_id]["file"],
                  "file_sha256": self.dataset["files_read"][asset_id]["sha256"]}
        return CandleHistory(raw, timeframe, kind, None if crypto else US_SESSION, source)


def research_run(prices_dir, *, location: str | None = None, reports_commit: str | None = None, **kwargs) -> ReplayRun:
    candles = FrozenDailyCandles(prices_dir, location=location, reports_commit=reports_commit)
    return ReplayRun(RESEARCH, candles, dataset=candles.dataset, **kwargs)


def accept(record: dict) -> dict:
    """The gate for statistics: only research replays of the frozen dataset, never display reconstructions."""
    if not isinstance(record, dict) or record.get("mode") != RESEARCH:
        raise ReplayRefused("Only research replays can be used for statistics, tests or parameter choices.")
    dataset = record.get("dataset") or {}
    if not dataset.get("manifest_sha256"):
        raise ReplayRefused("A research replay must name its frozen dataset.")
    for cutoff in record.get("cutoffs") or []:
        if pd.Timestamp(cutoff) >= HOLDOUT_START:
            raise ReplayRefused("A research replay reached the protected hold-out period.")
    return record
