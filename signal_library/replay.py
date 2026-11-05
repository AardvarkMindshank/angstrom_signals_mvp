"""
Point-in-time evaluation ("replay"): what a signal says at a past time T, using only inputs knowable at T.
Design: docs/design/point_in_time.md (revision 2, accepted 4 Nov 2026). This module is the shared foundation;
the two ways in are kept apart on purpose:

    signal_library.replay_display    current providers, descriptive only, never saved or used for statistics
    signal_library.replay_research   the frozen development dataset only, refuses the hold-out period

A replay is an AS-OF RECONSTRUCTION: today's algorithms, the live lookback window, inputs cut at T. It is not a
claim about what the app displayed at T.

Rules enforced here (and by the engine, which calls `permit` and `verify`):
- Candles: only candles whose close is at or before T, inside the same window the live app loads (range plus
  warm-up candles, capped like the chart). The candle containing T is dropped, not shown as forming: its values
  would include data from after T.
- Stored flows: rows first seen at or before T, inside the live loader's day window; backfilled rows are never
  used (point_in_time is required).
- Derivatives: not replayable (no stored history).
- Every market-data timestamp in a result (observed_at, available_at and every timestamp inside the value and the
  evidence) must be at or before T, or the result becomes an error. `computed_at` is administrative (when the
  reconstruction ran) and is exempt.
- Each run has its own bounded result cache; the shared live cache is never read or written.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import chart_data

from . import certification
from .context import RANGE_FOR, DataContext
from .core import ERROR, SignalResult

# Fixed in the validation spec (research.HOLDOUT_START, tag holdout-spec-v1); a test keeps the two equal.
HOLDOUT_START = pd.Timestamp("2024-10-30", tz="UTC")

DISPLAY = "display"
RESEARCH = "research"
CERTIFICATION = "certification"   # the certification harness only: algorithm checks switched off, no hold-out data
MODES = (DISPLAY, RESEARCH, CERTIFICATION)

from .core import NOT_REPLAYABLE  # noqa: E402,F401

# Source quality (design section 4.2)
POINT_IN_TIME = "point_in_time"
RECONSTRUCTED = "reconstructed"
RECONSTRUCTED_LIMITED = "reconstructed_with_limitations"
UNAVAILABLE = "unavailable"
SPLIT_LIMITATION = ("Share prices are today's split-adjusted copy: historical price levels, and indicators derived "
                    "from them, can differ from what traders saw at the time.")

FLOW_DAYS = 120          # same day window as the live flows loader (signal_library.loaders.FLOW_DAYS)
RUN_CACHE_SIZE = 4096
FRAME_CACHE_SIZE = 32    # reused indicator frames per run (one per timeframe and window is enough for stepping)
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([+-]\d{2}:\d{2}|Z)?)?$")
ADMIN_FIELDS = ("computed_at",)


class ReplayRefused(ValueError):
    """A replay request that the rules do not allow (hold-out date, wrong data source, step cap)."""


def utc(ts) -> pd.Timestamp:
    stamp = pd.Timestamp(ts)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


# ---------------------------------------------------------------------------------------------- candle history

@dataclass
class CandleHistory:
    """Raw closed-and-forming candles for one (kind, asset, timeframe), loaded once per run."""
    raw: pd.DataFrame                  # open, high, low, close, volume; index = candle start (UTC), sorted
    timeframe: str
    kind: str
    session: tuple | None
    source: dict                       # provider, quality, limitations, dataset identity
    ends: np.ndarray = field(default=None, repr=False)   # candle close times, int64 ns UTC

    def __post_init__(self):
        raw = self.raw[["open", "high", "low", "close", "volume"]].astype(float)
        index = raw.index if raw.index.tz is not None else raw.index.tz_localize("UTC")
        self.raw = raw.set_axis(index.tz_convert("UTC").as_unit("ns")).sort_index()
        self.raw = self.raw[~self.raw.index.duplicated(keep="last")]
        if self.ends is None:
            kind = "crypto" if self.kind == "crypto" else "equity"
            self.ends = np.array([chart_data.candle_end(s, self.timeframe, kind, self.session).value
                                  for s in self.raw.index], dtype="int64")


def window_positions(history: CandleHistory, as_of) -> tuple[int, int]:
    """[first, last) positions of the candles the live app would hold at T: closed by T, from the range start
    minus the warm-up candles, capped like the chart (chart_data.load_candles)."""
    t = utc(as_of).value
    stop = int(np.searchsorted(history.ends, t, side="right"))       # ends are increasing with starts
    while stop > 0 and history.ends[stop - 1] > t:                    # defensive for irregular sessions
        stop -= 1
    if stop == 0:
        return 0, 0
    days = chart_data.RANGE_DAYS[RANGE_FOR[history.timeframe]]
    starts = history.raw.index.asi8
    if days is None:
        first_shown = 0
    else:
        range_start = (utc(as_of) - pd.Timedelta(days=days)).value
        first_shown = int(np.searchsorted(starts[:stop], range_start, side="left"))
    if stop - first_shown < chart_data.MIN_CANDLES:      # the live loader refuses too few candles in the range
        return 0, 0
    begin = max(0, first_shown - chart_data.WARMUP_CANDLES)
    begin = max(begin, stop - chart_data.MAX_CANDLES)
    return begin, stop


def frame_hash(frame: pd.DataFrame) -> str:
    values = pd.util.hash_pandas_object(frame, index=True).values
    return hashlib.sha256(values.tobytes()).hexdigest()


def default_indicators(raw: pd.DataFrame) -> pd.DataFrame:
    from scoring import calculate_indicators

    return calculate_indicators(raw)


# ---------------------------------------------------------------------------------------------- the run

class ReplayRun:
    """One replay session: a mode, its data sources, a private cache and the reproducibility record.

    candles(kind, asset_id, timeframe) -> CandleHistory, or {"error": text}
    flows(source, series, subject, as_of) -> {"rows": [...]} or {"error": text}; rows must carry fetched_at
    """

    def __init__(self, mode: str, candles, *, flows=None, sentiment=None, indicators=None,
                 dataset: dict | None = None,
                 max_steps: int | None = None, shortcut: bool = False, check_certification: bool | None = None,
                 reuse_frames: bool = False, slice_allow: set | None = None,
                 environment: dict | None = None):
        if mode not in MODES:
            raise ReplayRefused(f"Unknown replay mode {mode!r}.")
        if mode == RESEARCH and not getattr(candles, "research_dataset", False):
            raise ReplayRefused("Research replays read only the frozen development dataset.")
        if mode == RESEARCH and flows is not None and not getattr(flows, "research_dataset", False):
            raise ReplayRefused("Research replays read only frozen, versioned data.")
        self.mode = mode
        self.candles_source = candles
        self.flows_source = flows
        self.sentiment_source = sentiment
        self.indicators = indicators or default_indicators
        self.dataset = dataset if dataset is not None else {}
        self.max_steps = max_steps
        self.shortcut = shortcut
        # Reuse a timeframe's indicator frame when the cut window is the same candles as at an earlier cutoff
        # (no candle closed in between): the input rows are identical, so the frame is too.
        self.reuse_frames = reuse_frames
        self.slice_allow = slice_allow     # benchmarks only: (signal key, timeframe) pairs allowed to slice
        self.frame_cache: OrderedDict = OrderedDict()
        self.frame_reuses = 0
        self.check_certification = (mode != CERTIFICATION) if check_certification is None else check_certification
        self.environment = environment
        self.result_cache: OrderedDict = OrderedDict()
        self.started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()   # administrative
        self._histories: dict = {}
        self._full_frames: dict = {}
        self.steps: set = set()
        self.inputs: dict = {}         # (subject, timeframe or source, T) -> input description and hash
        self.signals: dict = {}        # instance_key -> ref, certification, source quality

    # -- requests ---------------------------------------------------------------------------------------------
    def context(self, kind: str, asset_id: str, as_of) -> "ReplayContext":
        t = utc(as_of)
        if self.mode == RESEARCH and t >= HOLDOUT_START:
            raise ReplayRefused(f"Research replays stop before the protected hold-out ({HOLDOUT_START.date()}).")
        if self.max_steps is not None and t not in self.steps and len(self.steps) >= self.max_steps:
            raise ReplayRefused(f"This replay is limited to {self.max_steps} time steps.")
        self.steps.add(t)
        return ReplayContext(self, kind, asset_id, t)

    def history(self, kind: str, asset_id: str, timeframe: str):
        key = (kind, asset_id, timeframe)
        if key not in self._histories:
            try:
                got = self.candles_source(kind, asset_id, timeframe)
            except Exception as exc:
                got = {"error": f"Could not load {timeframe} candles ({exc})"}
            self._histories[key] = got
        return self._histories[key]

    def full_frame(self, history: CandleHistory) -> pd.DataFrame:
        """Indicators computed once on the whole history (only used for slice-equivalent signals)."""
        key = id(history)
        if key not in self._full_frames:
            frame = self.indicators(history.raw.copy())
            frame["forming"] = False
            self._full_frames[key] = frame
        return self._full_frames[key]

    # -- engine hooks -----------------------------------------------------------------------------------------
    def permit(self, definition, ref, ctx) -> SignalResult | None:
        """None when the signal may run in this replay; otherwise the not-replayable result."""
        reason = None
        if "derivatives" in definition.requires:
            reason = "Derivatives data is live only: no stored history exists to replay."
        elif "capital_flows" in definition.requires and not dict(ref.params).get("point_in_time"):
            reason = "Only point-in-time flows can be replayed (backfilled history has no known publication time)."
        elif self.check_certification:
            status = certification.status(definition.key, ref.timeframe)
            if status.get("algorithm") != "certified":
                reason = f"Not certified for replay: {status.get('reason') or 'no certification record'}."
        if reason is None:
            return None
        return SignalResult(ref=ref.as_dict(), subject=ctx.subject, status=NOT_REPLAYABLE, notes=[reason],
                            instance_key=ref.instance_key)

    def slice_ok(self, signal_key: str | None, timeframe: str) -> bool:
        if not self.shortcut or signal_key is None:
            return False
        if self.slice_allow is not None:
            return (signal_key, timeframe) in self.slice_allow
        if self.mode == CERTIFICATION:
            return True
        return bool(certification.status(signal_key, timeframe).get("slice_equivalent"))

    def verify(self, result: SignalResult, ctx: "ReplayContext") -> SignalResult:
        """Every market-data timestamp at or before T, or the result becomes an error."""
        late = future_timestamps(result, ctx.as_of)
        if late:
            field_name, stamp = late[0]
            return SignalResult(ref=result.ref, subject=result.subject, status=ERROR, instance_key=result.instance_key,
                                computed_at=result.computed_at,
                                notes=[f"Replay integrity: {field_name} {stamp} is after the cutoff {ctx.as_of.isoformat()}."])
        return result

    def note_signal(self, definition, ref, ctx, result) -> None:
        cert = certification.status(definition.key, ref.timeframe)
        self.signals.setdefault(ref.instance_key, {
            **ref.as_dict(), "key": definition.key, "instance_key": ref.instance_key,
            "certification": {k: cert.get(k) for k in ("algorithm", "slice_equivalent", "reason")}
            | {"suite": certification.suite_reference()},
        })

    # -- the reproducibility record ---------------------------------------------------------------------------
    def record(self) -> dict:
        return {
            "mode": self.mode,
            "kind": "as-of reconstruction",
            "cutoffs": sorted(t.isoformat() for t in self.steps),
            "administrative": {"run_started_at": self.started_at,
                               "note": "When the reconstruction ran; not market data, exempt from the cutoff rule."},
            "code": code_identity(),
            "environment": self.environment or environment_identity(),
            "dataset": self.dataset,
            "inputs": [dict(v) for v in self.inputs.values()],
            "signals": list(self.signals.values()),
            "hold_out": {"start": HOLDOUT_START.date().isoformat(), "tag": "holdout-spec-v1",
                         "research_refuses_on_or_after": self.mode == RESEARCH},
        }


class ReplayContext(DataContext):
    """A DataContext at time T inside a ReplayRun. Signals use it exactly like a live context."""

    def __init__(self, run: ReplayRun, kind: str, asset_id: str, as_of: pd.Timestamp):
        super().__init__(kind, asset_id, now=as_of)
        self.replay = run
        self.as_of = as_of
        self.result_cache = run.result_cache
        self.current_signal: str | None = None
        self.mode = run.mode

    def candles(self, timeframe: str) -> dict:
        path = "slice" if self.replay.slice_ok(self.current_signal, timeframe) else "exact"
        key = ("candles", timeframe, path)
        if key not in self._memo:
            try:
                self._memo[key] = self._cut(timeframe, path)
            except Exception as exc:
                self._memo[key] = {"error": f"Could not load {timeframe} candles ({exc})"}
        return self._memo[key]

    def _cut(self, timeframe: str, path: str) -> dict:
        history = self.replay.history(self.kind, self.asset_id, timeframe)
        if not isinstance(history, CandleHistory):
            return {"error": (history or {}).get("error") or f"No {timeframe} candles."}
        begin, stop = window_positions(history, self.as_of)
        if stop - begin < 1:
            return {"error": f"No {timeframe} candles had closed by {self.as_of.isoformat()} in this data."}
        raw = history.raw.iloc[begin:stop]
        reuse_key = (id(history), begin, stop, path)
        frame = self.replay.frame_cache.get(reuse_key) if self.replay.reuse_frames else None
        if frame is not None:
            self.replay.frame_cache.move_to_end(reuse_key)
            self.replay.frame_reuses += 1
        elif path == "slice":
            frame = self.replay.full_frame(history).iloc[begin:stop].copy()
        else:
            frame = self.replay.indicators(raw.copy())
            frame["forming"] = False
        if self.replay.reuse_frames:
            self.replay.frame_cache[reuse_key] = frame
            while len(self.replay.frame_cache) > FRAME_CACHE_SIZE:
                self.replay.frame_cache.popitem(last=False)
        self.replay.inputs[(self.subject, timeframe, self.as_of.value, path)] = {
            "subject": self.subject, "timeframe": timeframe, "cutoff": self.as_of.isoformat(),
            "candles": int(len(raw)), "first": raw.index[0].isoformat(), "last": raw.index[-1].isoformat(),
            "sha256": frame_hash(raw), "source": history.source, "path": path,
        }
        return {"frame": frame, "session": history.session, "source": history.source.get("provider", ""),
                "source_quality": history.source.get("quality"), "limitations": history.source.get("limitations", [])}

    def derivatives(self) -> dict:
        return {"error": "Derivatives data is live only: no stored history exists to replay."}

    def capital_flows(self, source: str, series: str, subject: str) -> dict:
        key = ("flows", source, series, subject)
        if key in self._memo:
            return self._memo[key]
        if self.replay.flows_source is None:
            got = {"error": "No flow data source in this replay."}
        else:
            try:
                got = self.replay.flows_source(source, series, subject, self.as_of)
            except Exception as exc:
                got = {"error": f"Could not load capital flows ({exc})"}
        if not got.get("error"):
            got = {"rows": cut_flow_rows(got.get("rows") or [], self.as_of)}
            if not got["rows"]:
                got = {"error": f"No {series} observations first seen by {self.as_of.isoformat()}."}
            else:
                digest = hashlib.sha256(json.dumps(got["rows"], sort_keys=True, default=str).encode()).hexdigest()
                self.replay.inputs[(self.subject, f"{source}/{series}/{subject}", self.as_of.value)] = {
                    "subject": self.subject, "source": source, "series": series, "rows_subject": subject,
                    "cutoff": self.as_of.isoformat(), "rows": len(got["rows"]), "sha256": digest,
                    "quality": POINT_IN_TIME}
        self._memo[key] = got
        return got

    def sentiment(self, subject_key: str) -> dict:
        key = ("sentiment", subject_key)
        if key in self._memo:
            return self._memo[key]
        if self.replay.sentiment_source is None:
            got = {"error": "No sentiment source in this replay."}
        else:
            try:
                got = self.replay.sentiment_source(subject_key, self.as_of)
            except Exception as exc:
                got = {"error": f"Could not load sentiment ({exc})"}
        if not got.get("error"):
            rows = got.get("rows") or []
            if rows and not all(r.get("first_seen_at") for r in rows):
                got = {"error": "Sentiment is live only until first_seen_at is recorded "
                                "(run sql/2026-11-05_sentiment_first_seen.sql)."}
            else:
                got = {"rows": cut_sentiment_rows(rows, self.as_of)}
                if not got["rows"]:
                    got = {"error": f"No sentiment first seen by {self.as_of.isoformat()}."}
                else:
                    digest = hashlib.sha256(json.dumps(got["rows"], sort_keys=True, default=str).encode()).hexdigest()
                    self.replay.inputs[(self.subject, f"sentiment/{subject_key}", self.as_of.value)] = {
                        "subject": self.subject, "source": "sentiment_history", "series": subject_key,
                        "cutoff": self.as_of.isoformat(), "rows": len(got["rows"]), "sha256": digest,
                        "quality": POINT_IN_TIME}
        self._memo[key] = got
        return got

    def fingerprint(self, requires: tuple, timeframe: str) -> str:
        # Within one run the inputs at a cutoff are fixed, so the cutoff alone identifies them. (Loading candles here
        # would compute every indicator frame by the exact path before the signal runs, defeating the shortcuts.)
        return f"T={self.as_of.value}"


def cut_sentiment_rows(rows: list[dict], as_of) -> list[dict]:
    """Sentiment rows usable at T: received by the database (first_seen_at) and recorded at or before T."""
    t = utc(as_of)
    out = []
    for row in rows:
        seen, recorded = row.get("first_seen_at"), row.get("recorded_at")
        if not seen or not recorded or utc(seen) > t or utc(recorded) > t:
            continue
        out.append(dict(row))
    return out


def cut_flow_rows(rows: list[dict], as_of) -> list[dict]:
    """Stored flow rows usable at T: first seen at or before T, observed within the live day window, not backfilled."""
    t = utc(as_of)
    since = (t - pd.Timedelta(days=FLOW_DAYS)).date().isoformat()
    out = []
    for row in rows:
        seen = row.get("fetched_at")
        if seen is None or bool(row.get("backfilled")):
            continue
        if utc(seen) > t or str(row.get("observed_date")) < since or str(row.get("observed_date")) > t.date().isoformat():
            continue
        out.append(dict(row))
    return out


# ---------------------------------------------------------------------------------------------- invariants

def _timestamps(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _timestamps(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            yield from _timestamps(v, f"{path}[{i}]")
    elif isinstance(value, str) and _ISO.match(value):
        yield path, value


def future_timestamps(result, as_of) -> list[tuple[str, str]]:
    """Market-data timestamps in a result that fall after T. Administrative fields are exempt."""
    t = utc(as_of)
    data = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    late = []
    checked = {k: v for k, v in data.items() if k not in ADMIN_FIELDS and k not in ("ref", "instance_key", "subject")}
    for path, stamp in _timestamps(checked):
        try:
            when = utc(stamp)
        except (ValueError, TypeError):
            continue
        if len(stamp) == 10:   # a date: the day itself must have started by T
            when = utc(pd.Timestamp(stamp))
        if when > t:
            late.append((path, stamp))
    return late


# ---------------------------------------------------------------------------------------------- identities

_ROOT = Path(__file__).resolve().parents[1]


def code_identity() -> dict:
    commit = os.environ.get("GITHUB_SHA") or os.environ.get("RENDER_GIT_COMMIT")
    if not commit:
        try:
            import subprocess

            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True,
                                    timeout=5).stdout.strip() or None
        except Exception:
            commit = None
    return {"git_commit": commit, "replay_code_sha256": certification.code_hash()}


def environment_identity() -> dict:
    lock = _ROOT / "requirements-research.lock"
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest() if lock.exists() else None
    packages = {}
    for name in ("pandas", "numpy", "pandas_ta"):
        try:
            packages[name] = __import__(name).__version__
        except Exception:
            packages[name] = None
    return {"python": sys.version.split()[0], "platform": platform.platform(), "packages": packages,
            "lock_file": "requirements-research.lock" if lock_hash else None, "lock_sha256": lock_hash}
