"""
Replay certification suite (design section 4). Run by replay_certify.py in CI; tests run a small version locally.

For every candle signal and timeframe, on every dataset that has that timeframe, at 50+ cutoffs T:

1. Independent truncated reference. In a SEPARATE PROCESS, with a fresh DataContext and empty caches, the signal is
   computed from raw candles that this module cut at T with its own loop (not the replay code), before any
   indicator is computed. The replay result must equal it exactly (complete canonical JSON, every nested event,
   level, evidence item and timestamp; only the administrative computed_at is left out).
2. Future-data poisoning. Rows whose candle closes after T (including the candle containing T) are altered:
   noise, spikes, deleted rows, inserted rows, shifted volume; for flows, later revisions, late first sightings
   and later backfills. The replay at T must not change in any field.
3. Cache isolation. A cold run, a run warmed with later cutoffs, and a run after the shared live cache was filled
   must all give the same result; the shared live cache must not change size because of a replay.
4. Timestamp invariant. No market-data timestamp anywhere in the result is after T.
5. Boundaries. Cutoffs include exact candle closes, one second before and after, runs of consecutive closes,
   weekends, share session opens, daylight-saving changes and the times around swing confirmations, divergence
   confirmation and expiry, and structure breaks found in the data.

Slice-equivalence (section 4.3) is certified separately: indicators computed once on the whole history and sliced
must also equal the independent reference.

Datasets: synthetic only, plus frozen development data cut before 2024-10-30. Hold-out rows are filtered out right after each file is parsed
and never reach evaluation.
"""

from __future__ import annotations

import importlib
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import chart_data

from . import engine
from .context import RANGE_FOR, DataContext
from .core import REGISTRY, SignalRef
from .replay import (
    CERTIFICATION, HOLDOUT_START, CandleHistory, ReplayRun, cut_flow_rows, future_timestamps, utc,
)

POISONS = ("noise", "spike", "delete", "insert", "volume")
FLOW_POISONS = ("revision", "late_sighting", "late_backfill")
CANDLE_SIGNALS_EXCLUDED = ()


# ---------------------------------------------------------------------------------------------- datasets

@dataclass
class Dataset:
    name: str
    kind: str                        # crypto | equity | market
    asset_id: str
    histories: dict = field(default_factory=dict)    # timeframe -> CandleHistory
    flows: list | None = None        # stored flow rows (market datasets)
    flow_spec: tuple | None = None   # (source, series) the flow rows belong to
    sentiment: list | None = None    # stored sentiment rows (any subject key reads them)
    options: list | None = None      # stored options max-pain snapshot rows (any subject key reads them)
    description: str = ""

    def candles(self, kind, asset_id, timeframe):
        h = self.histories.get(timeframe)
        return h if h is not None else {"error": f"No {timeframe} candles in {self.name}."}

    def sentiment_loader(self, rows=None):
        rows = self.sentiment if rows is None else rows

        def load(subject_key, as_of):
            return {"rows": [dict(r) for r in rows]} if rows else {"error": "none"}
        return load if rows is not None else None

    def options_loader(self, rows=None):
        rows = self.options if rows is None else rows

        def load(subject_key, as_of):
            return {"rows": [dict(r) for r in rows]} if rows else {"error": "none"}
        return load if rows is not None else None

    def flow_loader(self, rows=None):
        rows = self.flows if rows is None else rows

        def load(source, series, subject, as_of):
            picked = [r for r in rows if r.get("_source", "") in ("", source)
                      and (r["subject"].startswith(subject[:-1]) if subject.endswith("*") else r["subject"] == subject)]
            return {"rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in picked]} if picked \
                else {"error": "none"}
        return load


def _walk(n: int, seed: int, start: float = 100.0, vol: float = 0.004):
    rng = np.random.default_rng(seed)
    # Regime-switching drift so trends, ranges, swings and divergences all occur.
    drift = np.repeat(rng.normal(0, vol / 3, n // 400 + 1), 400)[:n]
    steps = rng.normal(drift, vol, n)
    close = start * np.exp(np.cumsum(steps))
    spread = np.abs(rng.normal(0, vol, n)) * close
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.lognormal(6, 0.6, n)
    return open_, high, low, close, volume


def synthetic_crypto(days: int = 500, seed: int = 11, end="2024-06-30 00:00") -> Dataset:
    """15-minute bars around the clock, grouped into 1h/4h (UTC blocks), 1D and 1W like the chart."""
    index = pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=days * 96, freq="15min")
    o, h, l, c, v = _walk(len(index), seed)
    raw = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}, index=index)
    src = {"provider": "synthetic crypto (15m random walk)", "quality": "reconstructed", "limitations": []}
    hist = {"15m": CandleHistory(raw, "15m", "crypto", None, src),
            "30m": CandleHistory(chart_data.group_utc(raw, 30), "30m", "crypto", None, src),
            "1h": CandleHistory(chart_data.group_utc(raw, 60), "1h", "crypto", None, src),
            "4h": CandleHistory(chart_data.group_utc(raw, 240), "4h", "crypto", None, src),
            "12h": CandleHistory(chart_data.group_utc(raw, 720), "12h", "crypto", None, src),
            "1D": CandleHistory(chart_data.group_daily(raw), "1D", "crypto", None, src),
            "1W": CandleHistory(chart_data.group_weekly(chart_data.group_daily(raw)), "1W", "crypto", None, src)}
    return Dataset(f"synthetic-crypto-s{seed}", "crypto", "synthetic-coin", hist,
                   description=f"{days} days of synthetic 15-minute crypto bars (seed {seed}), grouped like the chart")


def synthetic_equity(days: int = 500, seed: int = 23, end="2024-06-28") -> Dataset:
    """15-minute bars inside the New York session on weekdays (spanning daylight-saving changes)."""
    session = ("America/New_York", 9 * 60 + 30, 16 * 60)
    dates = pd.bdate_range(end=end, periods=int(days * 5 / 7))
    stamps = []
    for d in dates:
        open_local = pd.Timestamp(d.date(), tz=session[0]) + pd.Timedelta(minutes=session[1])
        stamps.extend(open_local + pd.Timedelta(minutes=15 * k) for k in range(26))
    index = pd.DatetimeIndex(stamps).tz_convert("UTC")
    o, h, l, c, v = _walk(len(index), seed, vol=0.003)
    raw = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}, index=index)
    src = {"provider": "synthetic share (15m random walk, New York session)", "quality": "reconstructed", "limitations": []}
    daily = chart_data.group_daily(raw)
    hist = {"15m": CandleHistory(raw, "15m", "equity", session, src),
            "30m": CandleHistory(chart_data.group_session(raw, 30, session).tz_convert("UTC"), "30m", "equity", session, src),
            "1h": CandleHistory(chart_data.group_session(raw, 60, session).tz_convert("UTC"), "1h", "equity", session, src),
            "4h": CandleHistory(chart_data.group_session(raw, 240, session).tz_convert("UTC"), "4h", "equity", session, src),
            "12h": CandleHistory(chart_data.group_session(raw, 720, session).tz_convert("UTC"), "12h", "equity", session, src),
            "1D": CandleHistory(daily, "1D", "equity", session, src),
            "1W": CandleHistory(chart_data.group_weekly(daily), "1W", "equity", session, src)}
    return Dataset(f"synthetic-equity-s{seed}", "equity", "SYNTH", hist,
                   description=f"{len(dates)} sessions of synthetic 15-minute share bars (seed {seed}), New York hours")


def development_datasets(prices_dir: str, tickers=("BTC-USD", "SOL-USD", "AAPL", "JPM")) -> list[Dataset]:
    """Frozen development data, cut before the hold-out as each file is read (replay_research.FrozenDailyCandles)."""
    from .replay_research import FrozenDailyCandles

    frozen = FrozenDailyCandles(prices_dir, location="reports branch: data/prices (development rows only)")
    out = []
    for ticker in tickers:
        kind = "crypto" if ticker.endswith("-USD") else "equity"
        hist = {}
        for tf in ("1D", "1W"):
            got = frozen(kind, ticker, tf)
            if isinstance(got, CandleHistory):
                hist[tf] = got
        if hist:
            assert max(h.raw.index[-1] for h in hist.values()) < HOLDOUT_START
            out.append(Dataset(f"dev-{ticker}", kind, ticker, hist,
                               description=f"frozen development daily data for {ticker}, before 2024-10-30"))
    return out


def synthetic_flows(seed: int = 5, sessions: int = 200, end="2024-06-28") -> list[Dataset]:
    """Stored ETF-style and stablecoin-style rows with first-seen times, next-day revisions and a backfill."""
    rng = np.random.default_rng(seed)
    rows = []
    days = pd.bdate_range(end=end, periods=sessions)
    for i, day in enumerate(days):
        d = day.date().isoformat()
        seen = (day + pd.Timedelta(hours=23)).tz_localize("UTC")
        backfilled = i < 20
        first = pd.Timestamp(days[25].date()).tz_localize("UTC") if backfilled else seen
        for subject, scale in (("BTC", 300.0), ("BTC:IBIT", 180.0), ("BTC:FBTC", 120.0)):
            value = float(rng.normal(0, scale))
            rows.append({"_source": "tftc_btc_etf", "subject": subject, "observed_date": d, "value": value,
                         "fetched_at": first.isoformat(), "backfilled": backfilled})
            if i % 3 == 0 and not backfilled:      # revised the next morning
                rows.append({"_source": "tftc_btc_etf", "subject": subject, "observed_date": d,
                             "value": value + float(rng.normal(0, 20)),
                             "fetched_at": (seen + pd.Timedelta(hours=9)).isoformat(), "backfilled": False})
    supply = 1.2e11
    for day in pd.date_range(end=end, periods=int(sessions * 1.4)):
        supply *= 1 + float(rng.normal(0.0005, 0.002))
        seen = (day + pd.Timedelta(hours=26)).tz_localize("UTC")
        rows.append({"_source": "defillama_stablecoins", "subject": "ALL", "observed_date": day.date().isoformat(),
                     "value": supply, "fetched_at": seen.isoformat(), "backfilled": False})
    text = "synthetic stored {} with first-seen times, next-day revisions and a backfill (seed {})"
    return [Dataset(f"synthetic-etf-flows-s{seed}", "market", "bitcoin",
                    flows=[r for r in rows if r["_source"] == "tftc_btc_etf"], description=text.format("ETF flows", seed)),
            Dataset(f"synthetic-stablecoins-s{seed}", "market", "crypto",
                    flows=[r for r in rows if r["_source"] == "defillama_stablecoins"],
                    description=text.format("stablecoin supply", seed))]


# ---------------------------------------------------------------------------------------------- independent cut

def reference_cut(history: CandleHistory, as_of) -> pd.DataFrame | None:
    """The live window at T, written separately from replay.window_positions as a plain loop."""
    t = utc(as_of)
    starts, ends = _reference_times(history)
    closed = [i for i, end in enumerate(ends) if end <= t]
    if not closed:
        return None
    last = closed[-1]
    days = chart_data.RANGE_DAYS[RANGE_FOR[history.timeframe]]
    if days is None:
        first_shown = closed[0]
    else:
        range_start = t - pd.Timedelta(days=days)
        inside = [i for i in closed if starts[i] >= range_start]
        if not inside:
            return None
        first_shown = inside[0]
    if last - first_shown + 1 < chart_data.MIN_CANDLES:
        return None
    begin = max(closed[0], first_shown - chart_data.WARMUP_CANDLES)
    begin = max(begin, last + 1 - chart_data.MAX_CANDLES)
    return history.raw.iloc[begin:last + 1].copy()


_REF_TIMES: dict = {}


def _reference_times(history: CandleHistory):
    """Candle starts and closes for the reference, computed here in a plain loop (once per history)."""
    key = id(history)
    if key not in _REF_TIMES:
        kind = "crypto" if history.kind == "crypto" else "equity"
        starts = list(history.raw.index)
        _REF_TIMES[key] = (history, starts,
                           [chart_data.candle_end(x, history.timeframe, kind, history.session) for x in starts])
    _, starts, ends = _REF_TIMES[key]
    return starts, ends


def _indicators(path: str):
    module, name = path.split(":")
    return getattr(importlib.import_module(module), name)


def canonical(result) -> str:
    data = result.as_dict() if hasattr(result, "as_dict") else dict(result)
    data.pop("computed_at", None)
    return json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))


def _reference_worker(job: dict) -> list[dict]:
    """Runs in a separate process. Gets only data already cut at T; builds a fresh context per cutoff."""
    import signal_library  # noqa: F401  (registers the signals in this process)
    for module in job.get("imports") or []:
        importlib.import_module(module)
    from signal_library import engine as worker_engine
    from signal_library.context import DataContext as WorkerContext
    from signal_library.core import SignalRef as WorkerRef

    indicators = _indicators(job["indicators"])
    refs = [WorkerRef(r["id"], r["version"], r["timeframe"], tuple(sorted(r["params"].items()))) for r in job["refs"]]
    out = []
    for step in job["steps"]:
        worker_engine.clear_cache()
        frames = {}
        for tf, message in job.get("missing", {}).items():
            frames[tf] = {"error": message}
        for tf, raw in step["candles"].items():
            if raw is None:   # same wording as the replay path, so an empty window compares equal
                frames[tf] = {"error": f"No {tf} candles had closed by {step['as_of'].isoformat()} in this data."}
                continue
            frame = indicators(raw.copy())
            frame["forming"] = False
            frames[tf] = {"frame": frame, "session": job["sessions"].get(tf), "source": job["provider"]}

        def candle_loader(kind, asset, tf, frames=frames):
            return frames.get(tf) or {"error": f"No {tf} candles."}

        rows = step.get("flows")
        feelings = step.get("sentiment")
        snaps = step.get("options")

        def sentiment_loader(subject_key, rows=feelings):
            return {"rows": [dict(r) for r in rows]} if rows else {"error": "none"}

        def options_loader(subject_key, rows=snaps):
            return {"rows": [dict(r) for r in rows]} if rows else {"error": "none"}

        def flows_loader(source, series, subject, rows=rows):
            picked = [r for r in (rows or []) if r.get("_source", "") in ("", source)
                      and (r["subject"].startswith(subject[:-1]) if subject.endswith("*") else r["subject"] == subject)]
            return {"rows": [{k: v for k, v in r.items() if not k.startswith("_")} for r in picked]} if picked \
                else {"error": "none"}
        ctx = WorkerContext(job["kind"], job["asset_id"], candle_loader=candle_loader,
                            flows_loader=flows_loader if rows is not None else None, now=step["as_of"],
                            sentiment_loader=sentiment_loader if feelings is not None else None,
                            options_loader=options_loader if snaps is not None else None)
        results = worker_engine.evaluate(refs, ctx)
        out.append({k: canonical(v) for k, v in results.items()})
    worker_engine.clear_cache()
    return out


# ---------------------------------------------------------------------------------------------- cutoffs

def _event_times(results: dict) -> list[pd.Timestamp]:
    keys = ("confirmed_at", "expired_at", "invalidated_at", "broken_at", "retest_at")
    found = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in keys and isinstance(x, str):
                    try:
                        found.append(utc(x))
                    except ValueError:
                        pass
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for r in results.values():
        walk(r.value)
    return sorted(set(found))


def choose_cutoffs(dataset: Dataset, timeframe: str, n: int, seed: int, refs) -> list[pd.Timestamp]:
    h = dataset.histories[timeframe]
    span_start = max(x.raw.index[0] for x in dataset.histories.values())
    span_end = min(pd.Timestamp(x.ends[-1], tz="UTC") for x in dataset.histories.values())
    lo = span_start + (span_end - span_start) * 0.45
    eligible = h.ends[(h.ends >= lo.value) & (h.ends <= span_end.value)]
    rng = np.random.default_rng(seed)
    picks: set = set()
    if len(eligible) == 0:
        return []

    def ts(ns):
        return pd.Timestamp(int(ns), tz="UTC")
    for e in rng.choice(eligible, size=min(len(eligible), max(10, n * 2 // 5)), replace=False):
        picks.add(ts(e))                                                                  # exact closes
    start = int(rng.integers(0, max(1, len(eligible) - 8)))
    picks.update(ts(e) for e in eligible[start:start + 8])                                # consecutive closes
    for e in rng.choice(eligible, size=min(len(eligible), 8), replace=False):
        picks.add(ts(e) - pd.Timedelta(seconds=1))                                        # one second early
    for e in rng.choice(eligible, size=min(len(eligible), 4), replace=False):
        picks.add(ts(e) + pd.Timedelta(seconds=1))
    if dataset.kind == "equity":
        days = pd.date_range(lo.normalize(), span_end.normalize(), freq="D", tz="UTC")
        saturdays = [d + pd.Timedelta(hours=12) for d in days if d.weekday() == 5]
        picks.update(saturdays[:: max(1, len(saturdays) // 3)][:3])                       # weekends
        opens = [pd.Timestamp(d.date(), tz="America/New_York") + pd.Timedelta(minutes=570) for d in days
                 if d.weekday() < 5]
        picks.update(o.tz_convert("UTC") for o in opens[:: max(1, len(opens) // 3)][:3])  # session opens
        for d in days:                                                                    # daylight-saving changes
            local = pd.Timestamp(d.date(), tz="America/New_York")
            if (local + pd.Timedelta(days=1)).utcoffset() != local.utcoffset():
                picks.add((pd.Timestamp((d + pd.Timedelta(days=2)).date(), tz="America/New_York")
                           + pd.Timedelta(hours=16)).tz_convert("UTC"))
    # Around events found in the data: confirmations, expiries, breaks.
    run = ReplayRun(CERTIFICATION, dataset.candles, flows=dataset.flow_loader() if dataset.flows else None,
                    indicators=_INDICATORS["fn"])
    probe = engine.evaluate(refs, run.context(dataset.kind, dataset.asset_id, span_end))
    events = [e for e in _event_times(probe) if lo <= e <= span_end]
    for e in events[-6:]:
        picks.update({e, e - pd.Timedelta(seconds=1)})
    first_enough = lo
    picks.add(first_enough)
    while len(picks) < n:
        picks.add(ts(rng.choice(eligible)) - pd.Timedelta(seconds=int(rng.integers(0, 3600))))
    return sorted(p for p in picks if lo <= p <= span_end)


_INDICATORS = {"fn": None, "path": None}


# ---------------------------------------------------------------------------------------------- poisoning

def poisoned(history: CandleHistory, as_of, variant: str, seed: int) -> CandleHistory:
    t = utc(as_of).value
    raw = history.raw.copy()
    after = history.ends > t
    rng = np.random.default_rng(seed)
    idx = np.flatnonzero(after)
    if len(idx) == 0:
        return history
    ends = history.ends.copy()
    if variant == "noise":
        f = rng.lognormal(0, 0.05, len(idx))
        for col in ("open", "high", "low", "close"):
            raw.iloc[idx, raw.columns.get_loc(col)] *= f
        raw.iloc[idx, raw.columns.get_loc("high")] = raw.iloc[idx][["open", "high", "low", "close"]].max(axis=1).values
        raw.iloc[idx, raw.columns.get_loc("low")] = raw.iloc[idx][["open", "high", "low", "close"]].min(axis=1).values
    elif variant == "spike":
        raw.iloc[idx, raw.columns.get_loc("high")] *= 5.0
        raw.iloc[idx, raw.columns.get_loc("low")] *= 0.2
        raw.iloc[idx, raw.columns.get_loc("close")] *= 3.0
    elif variant == "delete":
        keep = np.ones(len(raw), dtype=bool)
        keep[idx[rng.random(len(idx)) < 0.5]] = False
        raw, ends = raw[keep], ends[keep]
    elif variant == "insert":
        extra = raw.iloc[idx].copy()
        extra.index = extra.index + pd.Timedelta(minutes=1)
        extra["close"] = extra["close"] * 1.5
        extra["high"] = extra[["high", "close"]].max(axis=1)
        kind = "crypto" if history.kind == "crypto" else "equity"
        extra_ends = np.array([chart_data.candle_end(x, history.timeframe, kind, history.session).value
                               for x in extra.index], dtype="int64")
        raw = pd.concat([raw, extra])
        ends = np.concatenate([ends, extra_ends])
        order = np.argsort(raw.index.asi8, kind="stable")
        raw, ends = raw.iloc[order], ends[order]
    elif variant == "volume":
        raw.iloc[idx, raw.columns.get_loc("volume")] *= 1000.0
    return CandleHistory(raw, history.timeframe, history.kind, history.session, history.source, ends=ends)


def poisoned_flows(rows: list[dict], as_of, variant: str, seed: int) -> list[dict]:
    t = utc(as_of)
    rng = np.random.default_rng(seed)
    out = [dict(r) for r in rows]
    later = (t + pd.Timedelta(hours=1)).isoformat()
    visible = [r for r in rows if utc(r["fetched_at"]) <= t]
    if variant == "revision":            # later revisions of days already seen
        for r in visible[-30:]:
            out.append({**r, "value": float(r["value"]) * float(rng.normal(3, 1)), "fetched_at": later})
    elif variant == "late_sighting":     # days first seen only after T (including days before T)
        for k in range(10):
            day = (t - pd.Timedelta(days=k)).date().isoformat()
            for subject in sorted({r["subject"] for r in rows}):
                out.append({"_source": next((r.get("_source", "") for r in rows if r["subject"] == subject), ""),
                            "subject": subject, "observed_date": day, "value": 9.9e9, "fetched_at": later,
                            "backfilled": False})
    elif variant == "late_backfill":     # history loaded after T
        for r in visible[-30:]:
            out.append({**r, "value": -1.0, "fetched_at": later, "backfilled": True})
    return out


# ---------------------------------------------------------------------------------------------- running

def _first_difference(a: str, b: str) -> str:
    x, y = json.loads(a), json.loads(b)

    def walk(p, u, v):
        if type(u) is not type(v):
            return f"{p}: {str(u)[:60]} vs {str(v)[:60]}"
        if isinstance(u, dict):
            for k in sorted(set(u) | set(v)):
                if k not in u or k not in v:
                    return f"{p}.{k}: missing on one side"
                d = walk(f"{p}.{k}", u[k], v[k])
                if d:
                    return d
            return ""
        if isinstance(u, list):
            if len(u) != len(v):
                return f"{p}: {len(u)} vs {len(v)} items"
            for i, (s, w) in enumerate(zip(u, v)):
                d = walk(f"{p}[{i}]", s, w)
                if d:
                    return d
            return ""
        return "" if u == v else f"{p}: {str(u)[:60]} vs {str(v)[:60]}"
    return walk("", x, y) or "differs"


# Slice equivalence (docs/design/point_in_time.md §13): the sliced shortcut and the exact path compute the same
# numbers by different routes, so they may differ in the last binary digits, and differently on different CPUs.
# Numbers are equal when |a - b| <= SLICE_TOLERANCE * max(1, |a|, |b|); everything else must match exactly. The
# reference, poisoning, cache and timestamp checks stay exact.
SLICE_TOLERANCE = 1e-9


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _slice_difference(a: str, b: str, tolerance: float = SLICE_TOLERANCE) -> str:
    """"" when equal within the tolerance; otherwise the first difference, without raw float digits."""
    x, y = json.loads(a), json.loads(b)

    def walk(p, u, v):
        if _is_number(u) and _is_number(v):
            gap = abs(u - v)
            if gap <= tolerance * max(1.0, abs(u), abs(v)):
                return ""
            return f"{p}: differs by {gap:.1e} (beyond the {tolerance:.0e} tolerance)"
        if type(u) is not type(v):
            return f"{p}: different kinds of value"
        if isinstance(u, dict):
            for k in sorted(set(u) | set(v)):
                if k not in u or k not in v:
                    return f"{p}.{k}: missing on one side"
                d = walk(f"{p}.{k}", u[k], v[k])
                if d:
                    return d
            return ""
        if isinstance(u, list):
            if len(u) != len(v):
                return f"{p}: {len(u)} vs {len(v)} items"
            for i, (s, w) in enumerate(zip(u, v)):
                d = walk(f"{p}[{i}]", s, w)
                if d:
                    return d
            return ""
        return "" if u == v else f"{p}: {str(u)[:60]} vs {str(v)[:60]}"
    return walk("", x, y)


@dataclass
class Tally:
    cutoffs: int = 0
    checks: dict = field(default_factory=lambda: {"reference": 0, "poison": 0, "cache": 0, "timestamps": 0,
                                                  "slice": 0})
    failures: list = field(default_factory=list)
    slice_failures: list = field(default_factory=list)
    statuses: dict = field(default_factory=dict)
    per_dataset: dict = field(default_factory=dict)


def _refs_for(dataset: Dataset, timeframe: str, include=None, only=None) -> list[SignalRef]:
    refs = []
    for d in REGISTRY.latest():
        if d.id.startswith("test.") and not (include and d.id in include):
            continue
        if only and d.id not in only:
            continue
        if dataset.options is not None:
            if "options" in d.requires and timeframe in d.timeframes and d.scope == "asset" and dataset.kind != "market":
                refs.append(SignalRef.make(d, timeframe))
            continue
        if "options" in d.requires:
            continue
        if dataset.sentiment is not None:
            if "sentiment" in d.requires and timeframe in d.timeframes and (
                    (dataset.kind == "market" and d.scope.startswith("market:")
                     and dataset.asset_id in d.scope.split(":", 1)[1].split("|"))
                    or (dataset.kind != "market" and d.scope == "asset")):
                refs.append(SignalRef.make(d, timeframe))
            continue
        if dataset.kind == "market":
            if "capital_flows" in d.requires and timeframe in d.timeframes and d.scope == f"market:{dataset.asset_id}":
                refs.append(SignalRef.make(d, timeframe, point_in_time=True))
        elif d.scope in ("asset", "crypto_asset") and "candles" in d.requires and timeframe in d.timeframes:
            if d.scope == "crypto_asset" and dataset.kind != "crypto":
                continue
            refs.append(SignalRef.make(d, timeframe))
    return refs


def certify_dataset(dataset: Dataset, timeframe: str, *, cutoffs: int, pool, tallies: dict, seed: int = 7,
                    log=print, include=None, only=None, imports=()) -> None:
    refs = _refs_for(dataset, timeframe, include, only)
    if not refs:
        return
    keys = {r.instance_key: f"{r.id}@{r.version}" for r in refs}
    stored = not dataset.histories
    if stored:
        rows = dataset.flows if dataset.flows is not None else (
            dataset.sentiment if dataset.sentiment is not None else dataset.options)
        day_key, seen_key = ("observed_date", "fetched_at") if dataset.flows is not None else ("recorded_at", "first_seen_at")
        days = sorted({str(r[day_key])[:10] for r in rows})
        lo = pd.Timestamp(days[len(days) // 3], tz="UTC")
        hi = pd.Timestamp(days[-1], tz="UTC") + pd.Timedelta(days=2)
        rng = np.random.default_rng(seed)
        points = set(pd.to_datetime(rng.uniform(lo.value, hi.value, cutoffs), utc=True).floor("s"))
        seen = sorted({utc(r[seen_key]) for r in rows if lo <= utc(r[seen_key]) <= hi})
        for s in seen[-10:]:
            points.update({s, s - pd.Timedelta(seconds=1)})
        times = sorted(points)
    else:
        times = choose_cutoffs(dataset, timeframe, cutoffs, seed, refs)
    if not times:
        return
    needed = list(dataset.histories) if any(r.id == "mtf.alignment" for r in refs) else [timeframe]

    # 1. reference, in a separate process, from data this module cut
    steps = []
    for t in times:
        step = {"as_of": t, "candles": {tf: reference_cut(dataset.histories[tf], t) for tf in needed}
                if not stored else {}}
        if dataset.flows is not None:
            step["flows"] = cut_flow_rows_reference(dataset.flows, t)
        if dataset.sentiment is not None:
            step["sentiment"] = cut_sentiment_rows_reference(dataset.sentiment, t)
        if dataset.options is not None:
            step["options"] = cut_sentiment_rows_reference(dataset.options, t)
        steps.append(step)
    job = {"indicators": _INDICATORS["path"], "imports": list(imports), "kind": dataset.kind, "asset_id": dataset.asset_id,
           "refs": [r.as_dict() for r in refs], "steps": steps,
           "sessions": {tf: h.session for tf, h in dataset.histories.items()},
           "missing": {tf: dataset.candles(dataset.kind, dataset.asset_id, tf).get("error")
                       for tf in ("15m", "30m", "1h", "4h", "12h", "1D", "1W") if tf not in dataset.histories},
           "provider": next(iter(dataset.histories.values())).source.get("provider", "") if dataset.histories else ""}
    reference = pool.submit(_reference_worker, job).result()

    flows = dataset.flow_loader() if dataset.flows is not None else None
    feeling = dataset.sentiment_loader()
    snaps = dataset.options_loader()
    clean_run = ReplayRun(CERTIFICATION, dataset.candles, flows=flows, sentiment=feeling, options=snaps,
                          indicators=_INDICATORS["fn"])
    slice_run = ReplayRun(CERTIFICATION, dataset.candles, flows=flows, sentiment=feeling, options=snaps,
                          indicators=_INDICATORS["fn"], shortcut=True)
    # The clean replay visits the cutoffs in a shuffled order, so state carried between evaluations (a later
    # cutoff seen first) shows up as a difference from the independent reference.
    order = np.random.default_rng(seed + 1).permutation(len(times))
    for i in order:
        t, ref_out = times[i], reference[i]
        got = engine.evaluate(refs, clean_run.context(dataset.kind, dataset.asset_id, t))
        sliced = engine.evaluate(refs, slice_run.context(dataset.kind, dataset.asset_id, t)) \
            if not stored else None
        if not stored:
            variants = [POISONS[(2 * i) % 5], POISONS[(2 * i + 1) % 5]]
        elif dataset.flows is not None:
            variants = [FLOW_POISONS[i % 3]]
        elif dataset.options is not None:
            variants = [OPTIONS_POISONS[(2 * i) % 3], OPTIONS_POISONS[(2 * i + 1) % 3]]
        else:
            variants = [SENTIMENT_POISONS[i % 3]]
        poisoned_results = []
        for v in variants:
            if stored and dataset.flows is not None:
                rows = poisoned_flows(dataset.flows, t, v, seed + i)
                prun = ReplayRun(CERTIFICATION, dataset.candles, flows=dataset.flow_loader(rows),
                                 indicators=_INDICATORS["fn"])
            elif stored and dataset.options is not None:
                rows = poisoned_options(dataset.options, t, v, seed + i)
                prun = ReplayRun(CERTIFICATION, dataset.candles, options=dataset.options_loader(rows),
                                 indicators=_INDICATORS["fn"])
            elif stored:
                rows = poisoned_sentiment(dataset.sentiment, t, v, seed + i)
                prun = ReplayRun(CERTIFICATION, dataset.candles, sentiment=dataset.sentiment_loader(rows),
                                 indicators=_INDICATORS["fn"])
            else:
                bad = {tf: poisoned(dataset.histories[tf], t, v, seed + i) for tf in needed}
                prun = ReplayRun(CERTIFICATION, lambda k, a, tf, bad=bad: bad.get(tf) or dataset.candles(k, a, tf),
                                 indicators=_INDICATORS["fn"])
            poisoned_results.append((v, engine.evaluate(refs, prun.context(dataset.kind, dataset.asset_id, t))))
        cache_results = []
        if i % 5 == 0:
            later = [x for x in times if x > t][:2]
            warm = ReplayRun(CERTIFICATION, dataset.candles, flows=flows, sentiment=feeling, options=snaps,
                             indicators=_INDICATORS["fn"])
            for x in later:
                engine.evaluate(refs, warm.context(dataset.kind, dataset.asset_id, x))
            cache_results.append(("warmed with later cutoffs",
                                  engine.evaluate(refs, warm.context(dataset.kind, dataset.asset_id, t))))
            if not stored:
                live = DataContext(dataset.kind, dataset.asset_id, now=times[-1] + pd.Timedelta(days=1),
                                   candle_loader=lambda k, a, tf: _live_frame(dataset, tf))
                engine.evaluate(refs, live)
                size = len(engine._CACHE)
                cold = ReplayRun(CERTIFICATION, dataset.candles, flows=flows, indicators=_INDICATORS["fn"])
                cache_results.append(("after the live cache was filled",
                                      engine.evaluate(refs, cold.context(dataset.kind, dataset.asset_id, t))))
                if len(engine._CACHE) != size:
                    cache_results.append(("replay wrote to the shared live cache", None))
        for key, label in keys.items():
            tally = tallies.setdefault((label, timeframe), Tally())
            tally.cutoffs += 1
            tally.per_dataset[dataset.name] = tally.per_dataset.get(dataset.name, 0) + 1
            mine = canonical(got[key])
            tally.statuses[got[key].status] = tally.statuses.get(got[key].status, 0) + 1
            tally.checks["reference"] += 1
            if mine != ref_out[key]:
                tally.failures.append(f"{dataset.name} T={t.isoformat()} reference: "
                                      + _first_difference(mine, ref_out[key]))
            tally.checks["timestamps"] += 1
            late = future_timestamps(got[key], t)
            if late:
                tally.failures.append(f"{dataset.name} T={t.isoformat()} timestamp {late[0][0]}={late[0][1]} after T")
            for v, res in poisoned_results:
                tally.checks["poison"] += 1
                if canonical(res[key]) != mine:
                    tally.failures.append(f"{dataset.name} T={t.isoformat()} poison '{v}': "
                                          + _first_difference(mine, canonical(res[key])))
            for what, res in cache_results:
                tally.checks["cache"] += 1
                if res is None:
                    tally.failures.append(f"{dataset.name} T={t.isoformat()} cache: {what}")
                elif canonical(res[key]) != mine:
                    tally.failures.append(f"{dataset.name} T={t.isoformat()} cache ({what}): "
                                          + _first_difference(mine, canonical(res[key])))
            if sliced is not None:
                tally.checks["slice"] += 1
                gap = _slice_difference(canonical(sliced[key]), ref_out[key])
                if gap:
                    tally.slice_failures.append(f"{dataset.name} T={t.isoformat()}: {gap}")
    log(f"  {dataset.name} {timeframe}: {len(times)} cutoffs, {len(refs)} signals")


SENTIMENT_POISONS = ("late_import", "later_scores", "future_first_seen")


def cut_sentiment_rows_reference(rows: list[dict], as_of) -> list[dict]:
    """Independent version of replay.cut_sentiment_rows: received by the database by T, recorded by T."""
    t = utc(as_of)
    keep = []
    for r in rows:
        if r.get("first_seen_at") is None or pd.Timestamp(r["first_seen_at"]) > t:
            continue
        if pd.Timestamp(r["recorded_at"]) > t:
            continue
        keep.append(dict(r))
    return keep


def poisoned_sentiment(rows: list[dict], as_of, variant: str, seed: int) -> list[dict]:
    """Rows that must not count at T: imported later with an earlier recorded_at (a backfill), scores recorded
    after T, and rows recorded before T but only received after T."""
    t = utc(as_of)
    rng = np.random.default_rng(seed)
    out = [dict(r) for r in rows]
    later = (t + pd.Timedelta(minutes=30)).isoformat()
    if variant == "late_import":
        for k in range(12):
            when = (t - pd.Timedelta(hours=6 * k + 1)).isoformat()
            out.append({"score": float(rng.uniform(0, 100)), "recorded_at": when, "first_seen_at": later,
                        "model": "import", "coverage": "ok", "events": 9, "sources": 9})
    elif variant == "later_scores":
        for k in range(1, 6):
            when = (t + pd.Timedelta(hours=12 * k)).isoformat()
            out.append({"score": 99.0, "recorded_at": when, "first_seen_at": when, "model": "m", "coverage": "ok",
                        "events": 5, "sources": 5})
    elif variant == "future_first_seen":
        for r in out[-8:]:
            if utc(r["recorded_at"]) <= t:
                out.append({**r, "score": 1.0, "recorded_at": (utc(r["recorded_at"]) + pd.Timedelta(seconds=1)).isoformat(),
                            "first_seen_at": later})
    return out


def synthetic_sentiment(seed: int = 9, days: int = 150, end="2024-06-28") -> list[Dataset]:
    """Twice-daily stored sentiment scores (0..100) with database receipt times, thin-news days and gaps."""
    rng = np.random.default_rng(seed)
    rows = []
    level = 50.0
    for when in pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=days * 2, freq="12h"):
        if rng.random() < 0.08:
            continue                                           # missed update: a gap, not a neutral score
        level = float(np.clip(level + rng.normal(0, 6), 0, 100))
        thin = rng.random() < 0.15
        recorded = when + pd.Timedelta(minutes=int(rng.integers(0, 50)))
        rows.append({"score": round(level, 2), "recorded_at": recorded.isoformat(),
                     "first_seen_at": (recorded + pd.Timedelta(seconds=int(rng.integers(0, 90)))).isoformat(),
                     "model": "grok-test", "coverage": "thin" if thin else "ok",
                     "events": int(rng.integers(1, 3)) if thin else int(rng.integers(4, 15)),
                     "sources": int(rng.integers(1, 3)) if thin else int(rng.integers(3, 10))})
    text = f"synthetic stored sentiment, twice daily with gaps and thin-news days (seed {seed})"
    return [Dataset(f"synthetic-sentiment-{kind}-{asset}", kind, asset, sentiment=rows, description=text)
            for kind, asset in (("market", "crypto"), ("market", "stocks"), ("crypto", "synthetic-coin"),
                                ("equity", "SYNTH"))]


OPTIONS_POISONS = ("late_import", "later_snapshots", "future_first_seen")


def poisoned_options(rows: list[dict], as_of, variant: str, seed: int) -> list[dict]:
    """Snapshot rows that must not count at T: a backfilled snapshot (taken before T, received after T), snapshots
    taken after T, and copies of earlier rows with a moved max pain that the database only received after T."""
    t = utc(as_of)
    rng = np.random.default_rng(seed)
    out = [dict(r) for r in rows]
    later = (t + pd.Timedelta(minutes=30)).isoformat()
    keys = sorted({r["asset_key"] for r in rows})
    if variant == "late_import":
        when = (t - pd.Timedelta(minutes=int(rng.integers(1, 120)))).isoformat()
        for key in keys:
            for k in range(1, 6):
                out.append({"asset_key": key, "recorded_at": when, "first_seen_at": later,
                            "expiry": (t + pd.Timedelta(days=k)).date().isoformat(), "spot": 1.0,
                            "max_pain": float(rng.uniform(1, 10)), "call_oi": 1.0, "put_oi": 99.0, "source": "import"})
    elif variant == "later_snapshots":
        for key in keys:
            for k in range(1, 4):
                when = (t + pd.Timedelta(hours=4 * k)).isoformat()
                out.append({"asset_key": key, "recorded_at": when, "first_seen_at": when,
                            "expiry": (t + pd.Timedelta(days=2)).date().isoformat(), "spot": 2.0, "max_pain": 1.0,
                            "call_oi": 5.0, "put_oi": 5.0, "source": "later"})
    elif variant == "future_first_seen":
        for r in out[-12:]:
            if utc(r["recorded_at"]) <= t:
                out.append({**r, "max_pain": float(r["max_pain"]) * 3,
                            "recorded_at": (utc(r["recorded_at"]) + pd.Timedelta(seconds=1)).isoformat(),
                            "first_seen_at": later})
    return out


def synthetic_options(seed: int = 11, days: int = 150, end="2024-06-28") -> list[Dataset]:
    """Options snapshots like the worker's: crypto every 4 hours (daily, weekly and monthly expiries, 08:00 UTC
    settlement), an equity once per weekday (weekly and monthly expiries), with missed snapshots, late receipt and
    a missing underlying price now and then."""
    rng = np.random.default_rng(seed)
    out = []
    for kind, asset, every, key in (("crypto", "bitcoin", "4h", "Crypto|bitcoin"),
                                     ("equity", "SYNTH", "1D", "Stock|SYNTH")):
        rows, spot = [], 100.0
        for when in pd.date_range(end=pd.Timestamp(end, tz="UTC"), periods=days * (6 if every == "4h" else 1),
                                  freq=every):
            if kind == "equity" and when.weekday() >= 5:
                continue
            if rng.random() < 0.07:
                continue                                              # a missed snapshot: a gap, never a guess
            spot = float(spot * np.exp(rng.normal(0, 0.02)))
            taken = when + pd.Timedelta(minutes=int(rng.integers(0, 40)) + (15 * 60 if kind == "equity" else 0))
            seen = taken + pd.Timedelta(seconds=int(rng.integers(1, 120)))
            day = taken.normalize().tz_localize(None)
            expiries = {(day + pd.Timedelta(days=k)).date() for k in range(0, 70)
                        if (day + pd.Timedelta(days=k)).weekday() == 4}
            if kind == "crypto":
                expiries |= {(day + pd.Timedelta(days=k)).date() for k in (0, 1, 2)}
            for d in sorted(set(expiries))[: (10 if kind == "crypto" else 7)]:
                rows.append({"asset_key": key, "recorded_at": taken.isoformat(), "first_seen_at": seen.isoformat(),
                             "expiry": d.isoformat(),
                             "spot": None if rng.random() < 0.03 else round(spot, 4),
                             "max_pain": round(spot * float(rng.uniform(0.9, 1.1)), 2),
                             "call_oi": float(rng.integers(100, 5000)), "put_oi": float(rng.integers(100, 5000)),
                             "source": "synthetic"})
        text = f"synthetic options snapshots ({'every 4 hours' if every == '4h' else 'weekdays'}; seed {seed})"
        out.append(Dataset(f"synthetic-options-{kind}-{asset}", kind, asset, options=rows, description=text))
    return out


def cut_flow_rows_reference(rows: list[dict], as_of) -> list[dict]:
    """Independent version of replay.cut_flow_rows: first seen by T, not backfilled, inside the day window."""
    t = utc(as_of)
    first_day = (t - pd.Timedelta(days=120)).date().isoformat()
    keep = []
    for r in rows:
        if r.get("backfilled"):
            continue
        if pd.Timestamp(r["fetched_at"]) > t:
            continue
        if not (first_day <= r["observed_date"] <= t.date().isoformat()):
            continue
        keep.append(dict(r))
    return keep


_LIVE_FRAMES: dict = {}


def _live_frame(dataset: Dataset, tf: str) -> dict:
    key = (dataset.name, tf)
    if key not in _LIVE_FRAMES:
        h = dataset.histories.get(tf)
        if h is None:
            return {"error": "none"}
        frame = _INDICATORS["fn"](h.raw.copy())
        frame["forming"] = False
        _LIVE_FRAMES[key] = {"frame": frame, "session": h.session, "source": "live fill"}
    return _LIVE_FRAMES[key]


def run_suite(datasets: list[Dataset], *, indicators: str, cutoffs: int = 50, timeframes=None, log=print,
              include=None, only=None, imports=()) -> dict:
    """Certify every candle and flow signal on the datasets. Returns the certification record's 'signals' part
    plus a summary."""
    _INDICATORS["path"] = indicators
    _INDICATORS["fn"] = _indicators(indicators)
    _LIVE_FRAMES.clear()
    _REF_TIMES.clear()
    tallies: dict = {}
    ctx = multiprocessing.get_context("spawn")
    # A spawned worker re-runs the parent's main script unless it has none. Under test runners (and Streamlit's
    # AppTest) that script is not importable, so the worker starts from a clean main module instead.
    import sys
    import types

    real_main = sys.modules.get("__main__")
    sys.modules["__main__"] = types.ModuleType("__main__")
    try:
        pool = ProcessPoolExecutor(max_workers=1, mp_context=ctx)
        pool.submit(int, 0).result()
    finally:
        sys.modules["__main__"] = real_main
    with pool:
        for ds in datasets:
            tfs = (["1D", "4h"] if ds.options is not None else ["1D"]) if not ds.histories else [tf for tf in ("15m", "30m", "1h", "4h", "12h", "1D", "1W") if tf in ds.histories]
            for tf in tfs:
                if timeframes and tf not in timeframes:
                    continue
                certify_dataset(ds, tf, cutoffs=cutoffs, pool=pool, tallies=tallies, log=log, include=include,
                                only=only, imports=imports)
    engine.clear_cache()
    signals: dict = {}
    for (key, tf), t in sorted(tallies.items()):
        enough = bool(t.per_dataset) and min(t.per_dataset.values()) >= cutoffs
        produced = t.statuses.get("ok", 0) + t.statuses.get("stale", 0) > 0
        ok = not t.failures and enough and produced
        entry = {
            "algorithm": "certified" if ok else "not_certified",
            "reason": None if ok else (t.failures[0] if t.failures else
                                       "never produced a reading on the test data" if not produced else
                                       f"fewer than {cutoffs} cutoffs on a dataset: {t.per_dataset}"),
            "slice_equivalent": ok and t.checks["slice"] > 0 and not t.slice_failures,
            "slice_reason": None if (t.checks["slice"] and not t.slice_failures) else
            (t.slice_failures[0] if t.slice_failures else "not tested"),
            "cutoffs": t.cutoffs, "cutoffs_per_dataset": dict(sorted(t.per_dataset.items())),
            "checks": dict(t.checks), "failures": len(t.failures),
            "result_statuses": dict(sorted(t.statuses.items())),
        }
        signals.setdefault(key, {})[tf] = entry
    for d in REGISTRY.latest():
        if "derivatives" in d.requires and not only:
            for tf in d.timeframes:
                signals.setdefault(d.key, {})[tf] = {
                    "algorithm": "not_certified", "slice_equivalent": False, "slice_reason": "not tested",
                    "reason": "Derivatives have no stored history (live only); see decision E.",
                    "cutoffs": 0, "checks": {}, "failures": 0, "result_statuses": {}}
    return signals
