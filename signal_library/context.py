"""
Data access for the Signal Library, kept apart from the calculations.

A DataContext loads each input once per evaluation pass and hands the same object to every
signal that needs it, so ten signals on 4h candles cause one candle fetch and one indicator pass.
Signals never fetch anything themselves; tests pass in their own loaders.

Data keys a definition can require:
    "candles"        closed and forming candles for the signal's timeframe, with the standard
                     indicator columns from scoring.calculate_indicators (same formulas as the charts)
    "derivatives"    hourly open interest, long/short ratio, funding and liquidations for a coin
                     (the stored Leverage & liquidations record; about 7 days, refreshed hourly)
    "capital_flows"  stored capital-flow observations (append-only, with first-seen times)
    "sentiment"      stored headline-sentiment observations (sentiment_history: score, recorded_at, model,
                     coverage, and first_seen_at once that column exists)
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

import chart_data

# The longest range each timeframe can load (the chart's own limits).
RANGE_FOR = {"15m": "1M", "30m": "1M", "1h": "1Y", "4h": "1Y", "12h": "1Y", "1D": "1Y", "1W": "All"}


def default_candle_loader(kind: str, asset_id: str, timeframe: str) -> dict:
    """chart_data candles plus the standard indicators. Returns the chart_data dict with "frame"."""
    from scoring import calculate_indicators

    loaded = chart_data.load_candles(kind, asset_id, timeframe, RANGE_FOR[timeframe])
    if loaded.get("error"):
        return loaded
    candles = loaded["candles"]
    frame = calculate_indicators(candles[["open", "high", "low", "close", "volume"]])
    frame["forming"] = candles["forming"]
    loaded["frame"] = frame
    return loaded


class DataContext:
    """Inputs for one subject. kind is "crypto" or "equity" (or "market" for market-level subjects)."""

    def __init__(self, kind: str, asset_id: str, *, candle_loader: Callable | None = None,
                 derivatives_loader: Callable | None = None, flows_loader: Callable | None = None, now=None,
                 sentiment_loader: Callable | None = None):
        self.kind = kind
        self.asset_id = asset_id
        self.now = pd.Timestamp(now) if now is not None else pd.Timestamp.now(tz="UTC")
        if self.now.tzinfo is None:
            self.now = self.now.tz_localize("UTC")
        self._candle_loader = candle_loader or default_candle_loader
        self._derivatives_loader = derivatives_loader
        self._flows_loader = flows_loader
        self._sentiment_loader = sentiment_loader
        self._memo: dict = {}

    @property
    def subject(self) -> str:
        return f"{self.kind}:{self.asset_id}"

    def candles(self, timeframe: str) -> dict:
        key = ("candles", timeframe)
        if key not in self._memo:
            try:
                self._memo[key] = self._candle_loader(self.kind, self.asset_id, timeframe)
            except Exception as exc:  # one failed input never breaks the other signals
                self._memo[key] = {"error": f"Could not load {timeframe} candles ({exc})"}
        return self._memo[key]

    def derivatives(self) -> dict:
        if "derivatives" not in self._memo:
            if self._derivatives_loader is None:
                self._memo["derivatives"] = {"error": "No derivatives data source configured"}
            else:
                try:
                    self._memo["derivatives"] = self._derivatives_loader(self.kind, self.asset_id)
                except Exception as exc:
                    self._memo["derivatives"] = {"error": f"Could not load derivatives ({exc})"}
        return self._memo["derivatives"]

    def capital_flows(self, source: str, series: str, subject: str) -> dict:
        key = ("flows", source, series, subject)
        if key not in self._memo:
            if self._flows_loader is None:
                self._memo[key] = {"error": "No capital-flow data source configured"}
            else:
                try:
                    self._memo[key] = self._flows_loader(source, series, subject)
                except Exception as exc:
                    self._memo[key] = {"error": f"Could not load capital flows ({exc})"}
        return self._memo[key]

    def sentiment(self, subject_key: str) -> dict:
        key = ("sentiment", subject_key)
        if key not in self._memo:
            if self._sentiment_loader is None:
                self._memo[key] = {"error": "No sentiment data source configured"}
            else:
                try:
                    self._memo[key] = self._sentiment_loader(subject_key)
                except Exception as exc:
                    self._memo[key] = {"error": f"Could not load sentiment ({exc})"}
        return self._memo[key]

    def fingerprint(self, requires: tuple, timeframe: str) -> str:
        """Changes when the data a signal depends on changes, so cached results expire correctly."""
        parts = []
        if "candles" in requires:
            loaded = self.candles(timeframe)
            frame = loaded.get("frame")
            if frame is not None and len(frame):
                parts.append(f"{timeframe}:{len(frame)}:{frame.index[-1]}:{float(frame['close'].iloc[-1])}")
            else:
                parts.append(f"{timeframe}:none")
        if "derivatives" in requires:
            parts.append(str((self.derivatives() or {}).get("updated_at")))
        return "|".join(parts)


def confirmed_frame(loaded: dict) -> pd.DataFrame | None:
    """Closed candles only."""
    frame = loaded.get("frame") if loaded else None
    if frame is None or frame.empty:
        return None
    if "forming" in frame.columns:
        frame = frame[~frame["forming"].astype(bool)]
    return frame
