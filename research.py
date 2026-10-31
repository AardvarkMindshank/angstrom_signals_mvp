"""Research backtests for the scoring audit (Sprint 1, Task 1, step 2).

This is a study tool, run by hand from the Research workflow. Nothing in the app uses it,
and it never changes how the live score works.

What it adds over backtest.py
- A fixed universe chosen before testing: about 60 large US stocks across sectors and 25 coins
  with long histories (see UNIVERSE_*). These are today's survivors, so results lean towards
  winners (SURVIVOR_NOTE is printed in every report).
- A frozen price cache: prices are downloaded once and saved, and every experiment reads the
  same copy, so results can be repeated and free data sources are not hammered.
- Completed bars only: the last bar of every download is dropped, because it may be unfinished.
- Family sub-scores: Trend, Stretch and Flow, from the factor points the live score already
  works out.
- A development period and a frozen hold-out (the last HOLDOUT_YEARS years). Experiments here
  run on the development period only. The hold-out leaves out BTC, ETH, Apple and Microsoft,
  whose recent years were already looked at on 29 Oct.
- Panel tests that rank assets only against their own class (stocks with stocks, coins with
  coins), so a result can never just be "crypto beat stocks that day".
- Noise bands from a block bootstrap that resamples the SAME runs of dates for every asset
  together, keeping the way assets move together.

Usage (needs pandas_ta and yfinance, so it runs in GitHub Actions):
    python research.py cache --out prices/          download the universe once
    python research.py run --prices prices/ --out results/
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------- universe

UNIVERSE_STOCKS = (
    # technology
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "ORCL", "IBM", "ADBE", "CRM", "INTC", "CSCO", "QCOM",
    "TXN", "AMD",
    # consumer
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "WMT", "COST", "PG", "KO", "PEP",
    # financials
    "JPM", "BAC", "WFC", "GS", "MS", "C", "AXP",
    # health care
    "JNJ", "PFE", "MRK", "ABBV", "UNH", "LLY", "AMGN",
    # energy and materials
    "XOM", "CVX", "COP", "SLB", "LIN", "NEM", "FCX",
    # industrials
    "CAT", "DE", "BA", "GE", "HON", "UPS", "LMT",
    # utilities, real estate, communication
    "NEE", "DUK", "AMT", "SPG", "T", "VZ", "DIS", "NFLX",
)
UNIVERSE_CRYPTO = (
    "BTC-USD", "ETH-USD", "XRP-USD", "LTC-USD", "BCH-USD", "ADA-USD", "DOGE-USD", "XLM-USD",
    "LINK-USD", "TRX-USD", "ETC-USD", "XMR-USD", "DASH-USD", "ZEC-USD", "EOS-USD", "NEO-USD",
    "BNB-USD", "XTZ-USD", "ATOM-USD", "VET-USD", "ALGO-USD", "DOT-USD", "SOL-USD", "AVAX-USD",
    "FIL-USD",
)
BENCHMARKS = {"stock": "^GSPC", "crypto": "BTC-USD"}
ALREADY_SEEN = ("BTC-USD", "ETH-USD", "AAPL", "MSFT")  # tested on 29 Oct: left out of the hold-out
HOLDOUT_YEARS = 2
HOLDOUT_START = pd.Timestamp("2024-10-30")  # fixed in the validation spec; checked against the cache
HORIZONS = (1, 3, 7, 14, 30)
LABEL_BARS = max(HORIZONS) + 1  # longest label: entry one bar after the signal, exit 30 bars later
PARITY_WINDOWS = (90, 200, 365)  # the app's history slider runs 90-365 days, default 200
METHOD_VERSION = 2  # 1 = first run (31 Oct 2026, commit a4e7a41); 2 = labels and scores stop at the boundary
MIN_PANEL = 8  # fewest assets on a date for a cross-sectional reading
BOOTSTRAP_RUNS = 400
SEED = 20261031

SURVIVOR_NOTE = (
    "Survivor bias: the universe is today's large companies and long-lived coins. Firms and coins "
    "that shrank or died are missing, so results lean towards winners. Point-in-time membership "
    "was not available from free data."
)

FAMILIES = {
    "Trend": ("Moving Averages", "ADX Trend", "MACD & Hist", "Ichimoku Cloud", "Performance"),
    "Stretch": ("RSI", "Stochastic", "Bollinger Bands"),
    "Flow": ("Volume", "OBV"),
}
FACTORS = (
    "RSI", "Stochastic", "Moving Averages", "ADX Trend", "MACD & Hist",
    "Ichimoku Cloud", "Bollinger Bands", "Volume", "OBV", "Performance",
)


def asset_class(ticker: str) -> str:
    return "crypto" if str(ticker).upper().endswith("-USD") else "stock"


# ----------------------------------------------------------------------------- price cache

def completed_bars(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop the last bar of a download: it may still be forming."""
    return frame.iloc[:-1] if len(frame) else frame


def save_frame(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.StringIO()
    frame.to_csv(buffer, index_label="date")
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(buffer.getvalue())


def load_frame(path: Path) -> pd.DataFrame:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        frame = pd.read_csv(handle, index_col="date", parse_dates=["date"])
    return frame.sort_index()


def ticker_file(ticker: str) -> str:
    return ticker.replace("^", "_").replace("/", "_") + ".csv.gz"


def download_universe(out_dir: str, years: int = 10, pause: float = 1.0) -> dict:
    """Download every ticker once and save it. Returns the manifest that is saved beside the files."""
    from backtest import load_prices

    out = Path(out_dir)
    tickers = list(UNIVERSE_STOCKS) + list(UNIVERSE_CRYPTO) + [BENCHMARKS["stock"]]
    manifest = {"downloaded_at": datetime.now(timezone.utc).isoformat(), "years": years, "files": {}, "failed": {}}
    for ticker in tickers:
        frame = None
        for attempt in range(3):
            try:
                frame = completed_bars(load_prices(ticker, f"{years}y"))
                break
            except Exception as exc:
                manifest["failed"][ticker] = str(exc)[:200]
                time.sleep(pause * (attempt + 2))
        if frame is None or frame.empty:
            continue
        manifest["failed"].pop(ticker, None)
        save_frame(frame, out / ticker_file(ticker))
        manifest["files"][ticker] = {
            "file": ticker_file(ticker), "bars": int(len(frame)),
            "first": str(frame.index[0])[:10], "last": str(frame.index[-1])[:10],
        }
        time.sleep(pause)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_cache(prices_dir: str) -> dict[str, pd.DataFrame]:
    folder = Path(prices_dir)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    return {ticker: load_frame(folder / info["file"]) for ticker, info in manifest["files"].items()}


# ----------------------------------------------------------------------------- periods

def holdout_start(frames: dict[str, pd.DataFrame], years: int = HOLDOUT_YEARS) -> pd.Timestamp:
    last = max(frame.index.max() for frame in frames.values() if len(frame))
    return pd.Timestamp(last) - pd.DateOffset(years=years)


def development_view(table: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    """Only dates before the hold-out. Development work never sees anything later."""
    return table.loc[table.index < start]


def holdout_view(table: pd.DataFrame, start: pd.Timestamp, ticker: str) -> pd.DataFrame | None:
    """Hold-out dates, or None for the assets already looked at on 29 Oct."""
    if ticker in ALREADY_SEEN:
        return None
    return table.loc[table.index >= start]


def development_frames(frames: dict[str, pd.DataFrame], start: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Every bar on or after the hold-out start removed, BEFORE anything is scored or labelled.

    Method v1 cut the signal dates but built forward returns on the full series, so the last
    development labels used up to LABEL_BARS bars of hold-out prices. From v2 nothing past the
    boundary is even loaded into the experiments; labels near the end simply come out empty.
    """
    return {t: development_view(f, start) for t, f in frames.items()}


def checked_start(frames: dict[str, pd.DataFrame]) -> pd.Timestamp:
    """The hold-out start from the cache must match the date fixed in the spec."""
    start = holdout_start(frames)
    if start.normalize() != HOLDOUT_START:
        raise SystemExit(f"Hold-out start from the cache is {start.date()}, the spec fixes {HOLDOUT_START.date()}.")
    return HOLDOUT_START


# ----------------------------------------------------------------------------- per-asset signals

def add_families(details: pd.DataFrame) -> pd.DataFrame:
    """Family sub-scores from the factor points: Trend, Stretch (positive = oversold), Flow."""
    out = details.copy()
    for family, members in FAMILIES.items():
        present = [m for m in members if m in out.columns]
        out[family] = out[present].sum(axis=1, min_count=1) if present else np.nan
    return out


def forward_table(closes: pd.Series, horizons=HORIZONS) -> pd.DataFrame:
    from backtest import forward_returns

    return pd.DataFrame({h: forward_returns(closes, h) for h in horizons})


# ----------------------------------------------------------------------------- statistics

def centred_ranks(values: pd.Series) -> pd.Series:
    """Ranks scaled to mean 0 and spread 1, so products average to a rank correlation."""
    ranks = values.rank()
    spread = ranks.std(ddof=0)
    if not spread or not np.isfinite(spread):
        return pd.Series(np.nan, index=values.index)
    return (ranks - ranks.mean()) / spread


def block_indices(n: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """Positions 0..n-1 resampled in circular runs of `block` consecutive dates."""
    block = max(1, min(int(block), n))
    starts = rng.integers(0, n, size=math.ceil(n / block))
    picks = (starts[:, None] + np.arange(block)[None, :]) % n
    return picks.ravel()[:n]


def ratio_bootstrap(sums: np.ndarray, counts: np.ndarray, block: int, runs: int = BOOTSTRAP_RUNS,
                    seed: int = SEED, joint: bool = True) -> tuple[float | None, float | None, float | None]:
    """Estimate and 95% band of sum(sums) / sum(counts).

    sums and counts are dates x assets. joint=True draws the same dates for every asset (the rule);
    joint=False draws each asset's dates separately, which is kept only to show, in tests, why
    that understates the noise when assets move together.
    """
    sums = np.nan_to_num(np.asarray(sums, dtype=float))
    counts = np.nan_to_num(np.asarray(counts, dtype=float))
    if sums.ndim == 1:
        sums, counts = sums[:, None], counts[:, None]
    total = counts.sum()
    if total <= 0:
        return None, None, None
    estimate = float(sums.sum() / total)
    rng = np.random.default_rng(seed)
    n, k = sums.shape
    draws = []
    for _ in range(runs):
        if joint:
            idx = block_indices(n, block, rng)
            s, c = sums[idx].sum(), counts[idx].sum()
        else:
            s = c = 0.0
            for j in range(k):
                idx = block_indices(n, block, rng)
                s += sums[idx, j].sum()
                c += counts[idx, j].sum()
        if c > 0:
            draws.append(s / c)
    if len(draws) < 20:
        return estimate, None, None
    low, high = np.percentile(draws, [2.5, 97.5])
    return estimate, float(low), float(high)


def block_for(horizon: int) -> int:
    """Runs of dates long enough to keep overlapping returns and slow-moving scores together."""
    return max(20, 2 * int(horizon))


def verdict(estimate, low, high) -> str:
    if estimate is None or low is None or high is None:
        return "too few"
    if low > 0:
        return "positive"
    if high < 0:
        return "negative"
    return "noise"


# ----------------------------------------------------------------------------- panel building

def panel(signals: dict[str, pd.Series], forwards: dict[str, pd.Series]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two dates x assets tables, aligned: the signal and its forward return."""
    sig = pd.DataFrame(signals).sort_index()
    fwd = pd.DataFrame(forwards).reindex(sig.index)
    keep = sig.notna() & fwd.notna()
    return sig.where(keep), fwd.where(keep)


def pooled_rank_correlation(sig: pd.DataFrame, fwd: pd.DataFrame, horizon: int, **kw):
    """Each asset's own rank correlation over time, pooled across assets; band from joint date blocks."""
    products = pd.DataFrame(index=sig.index)
    counts = pd.DataFrame(index=sig.index)
    for column in sig.columns:
        s, f = sig[column], fwd[column]
        keep = s.notna() & f.notna()
        if keep.sum() < 60 or s[keep].nunique() < 2:
            continue
        products[column] = (centred_ranks(s[keep]) * centred_ranks(f[keep])).reindex(sig.index)
        counts[column] = keep.astype(float)
    if products.empty:
        return None, None, None
    return ratio_bootstrap(products.fillna(0).values, counts.fillna(0).values, block_for(horizon), **kw)


def cross_sectional_by_date(sig: pd.DataFrame, fwd: pd.DataFrame, classes: dict[str, str]) -> pd.DataFrame:
    """Per date and class: the rank correlation across assets, and the top-third minus
    bottom-third return. Assets are only ever ranked against their own class.

    Same results as the first version (a pandas loop, kept in tests as the reference), written with
    numpy so a full run takes minutes instead of an hour."""
    from scipy.stats import rankdata

    rows = []
    for klass in sorted(set(classes.values())):
        members = [c for c in sig.columns if classes.get(c) == klass]
        if len(members) < MIN_PANEL:
            continue
        s_all, f_all = sig[members].to_numpy(dtype=float), fwd[members].to_numpy(dtype=float)
        for i, date in enumerate(sig.index):
            s, f = s_all[i], f_all[i]
            keep = ~np.isnan(s) & ~np.isnan(f)
            if keep.sum() < MIN_PANEL:
                continue
            s, f = s[keep], f[keep]
            if len(np.unique(s)) < 2:
                continue
            rs_, rf = rankdata(s), rankdata(f)
            ic = float(np.corrcoef(rs_, rf)[0, 1]) if rf.std() > 0 else float("nan")
            third = max(1, len(s) // 3)
            order = np.argsort(s, kind="mergesort")
            spread = float(f[order[-third:]].mean() - f[order[:third]].mean())
            rows.append({"date": date, "class": klass, "ic": ic, "spread": spread})
    return pd.DataFrame(rows)


def cross_sectional(sig, fwd, classes, horizon: int, klass: str) -> dict:
    """{"ic": (estimate, low, high), "spread": (...)} for one class, ranked within that class only."""
    table = cross_sectional_by_date(sig, fwd, classes)
    out = {}
    for column in ("ic", "spread"):
        series = pd.Series(dtype=float)
        if not table.empty:
            series = table[table["class"] == klass].set_index("date")[column].dropna()
        out[column] = (None, None, None) if len(series) < 60 else ratio_bootstrap(
            series.values, np.ones(len(series)), block_for(horizon))
    return out


def extreme_excess(flags: pd.DataFrame, fwd: pd.DataFrame, horizon: int):
    """Average forward return on flagged days minus each asset's own average, with its band."""
    excess = fwd - fwd.mean()
    on = flags.fillna(False).astype(bool) & excess.notna()
    sums = excess.where(on, 0.0).fillna(0.0)
    counts = on.astype(float)
    estimate, low, high = ratio_bootstrap(sums.values, counts.values, block_for(horizon))
    return estimate, low, high, int(counts.values.sum())


# ----------------------------------------------------------------------------- descriptive

def score_histogram(scores: pd.Series) -> dict:
    """How often the score reaches each level (point 1 of the second opinion)."""
    values = scores.dropna()
    if values.empty:
        return {"days": 0}
    edges = list(range(0, 101, 10))
    counts = np.histogram(values.clip(0, 100), bins=edges)[0]
    return {
        "days": int(len(values)),
        "bins": {f"{lo}-{lo + 9}" if lo < 90 else "90-100": int(n) for lo, n in zip(edges[:-1], counts)},
        "share_at_or_above_70": float((values >= 70).mean()),
        "share_at_or_above_80": float((values >= 80).mean()),
        "share_at_or_below_30": float((values <= 30).mean()),
        "share_at_or_below_20": float((values <= 20).mean()),
        "p10": float(values.quantile(0.10)),
        "p50": float(values.quantile(0.50)),
        "p90": float(values.quantile(0.90)),
        "min": float(values.min()),
        "max": float(values.max()),
    }


# ----------------------------------------------------------------------------- the run

def score_all(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Score + factor points per day for every asset (needs pandas_ta). Indicators use only past bars."""
    from backtest import score_details

    out = {}
    for ticker, frame in frames.items():
        if ticker == BENCHMARKS["stock"]:
            continue
        print(f"scoring {ticker} ({len(frame)} bars)", file=sys.stderr)
        try:
            out[ticker] = add_families(score_details(frame))
        except Exception as exc:
            print(f"  failed: {exc}", file=sys.stderr)
    return out


def parity_check(frames: dict[str, pd.DataFrame], details: dict[str, pd.DataFrame], window: int = 200,
                 samples: int = 12) -> dict:
    """Users' scores come from their last `window` bars; this run uses all history. Check they match."""
    from scoring import calculate_indicators, compute_score

    worst = 0.0
    checked = 0
    for ticker in list(details)[:4]:
        frame, table = frames[ticker], details[ticker]
        positions = np.linspace(window + 60, len(frame) - 1, samples).astype(int)
        for pos in positions:
            date = frame.index[pos]
            if date not in table.index or pd.isna(table.loc[date, "score"]):
                continue
            live = compute_score(calculate_indicators(frame.iloc[pos - window + 1: pos + 1]))["score"]
            worst = max(worst, abs(float(live) - float(table.loc[date, "score"])))
            checked += 1
    return {"window": window, "checked": checked, "max_difference": worst}


def regime_flags(frames: dict[str, pd.DataFrame], index: pd.Index, klass: str) -> pd.Series:
    """True on dates when the class benchmark (S&P 500 or Bitcoin) closes above its 200-day average."""
    bench = frames.get(BENCHMARKS[klass])
    if bench is None:
        return pd.Series(np.nan, index=index)
    close = bench["close"]
    above = (close > close.rolling(200).mean()).astype(float).where(close.rolling(200).mean().notna())
    return above.reindex(index).ffill()


def run_experiments(frames: dict[str, pd.DataFrame], details: dict[str, pd.DataFrame],
                    start: pd.Timestamp | None = None) -> dict:
    start = HOLDOUT_START if start is None else start
    frames = development_frames(frames, start)
    details = {t: development_view(d, start) for t, d in details.items()}
    classes = {t: asset_class(t) for t in details}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdout_starts": str(start)[:10],
        "assets": {k: sorted(t for t in details if classes[t] == k) for k in ("stock", "crypto")},
        "survivor_note": SURVIVOR_NOTE,
        "tests_counted": 0,
        "method_version": METHOD_VERSION,
    }

    # Point 1: how often the score reaches each level (development dates only from v2).
    report["histogram"] = {
        "per_asset": {t: score_histogram(d["score"]) for t, d in details.items()},
        "per_class": {
            k: score_histogram(pd.concat([d["score"] for t, d in details.items() if classes[t] == k]))
            for k in ("stock", "crypto")
        },
    }

    dev = {t: development_view(d, start) for t, d in details.items()}
    fwd = {t: development_view(forward_table(frames[t]["close"]), start) for t in details}
    signals = ["score", *FAMILIES, *FACTORS]

    def tally(n=1):
        report["tests_counted"] += n

    # Experiments 1, 4, 5 and 6 (merged): families, classes, single factors, ranking.
    blocks = {}
    for klass in ("stock", "crypto"):
        members = [t for t in dev if classes[t] == klass]
        for name in signals:
            for h in HORIZONS:
                sig, f = panel({t: dev[t][name] for t in members if name in dev[t]},
                               {t: fwd[t][h] for t in members})
                ts = pooled_rank_correlation(sig, f, h)
                both = cross_sectional(sig, f, classes, h, klass)
                cs, sp = both["ic"], both["spread"]
                tally(3)
                blocks.setdefault(klass, {}).setdefault(name, {})[h] = {
                    "time_series_ic": ts, "time_series": verdict(*ts),
                    "cross_section_ic": cs, "cross_section": verdict(*cs),
                    "top_minus_bottom_pct": sp, "ranking": verdict(*sp),
                }
    report["signals"] = blocks

    # Experiment 2: extremes, each asset's own deciles (cut from development data) and fixed lines.
    extremes = {}
    for klass in ("stock", "crypto"):
        members = [t for t in dev if classes[t] == klass]
        scores = pd.DataFrame({t: dev[t]["score"] for t in members})
        trend = pd.DataFrame({t: dev[t]["Trend"] for t in members})
        stretch = pd.DataFrame({t: dev[t]["Stretch"] for t in members})
        rules = {
            "top 10% of own scores": scores.ge(scores.quantile(0.9)),
            "bottom 10% of own scores": scores.le(scores.quantile(0.1)),
            "score 80 or more": scores.ge(80), "score 20 or less": scores.le(20),
            "score 70 or more": scores.ge(70), "score 30 or less": scores.le(30),
            "trend up, stretched down (pullback)": trend.ge(20) & stretch.ge(4),
            "trend down, stretched up (bounce)": trend.le(-20) & stretch.le(-4),
        }
        for label, flags in rules.items():
            for h in HORIZONS:
                f = pd.DataFrame({t: fwd[t][h] for t in members}).reindex(flags.index)
                est, low, high, days = extreme_excess(flags, f, h)
                tally()
                extremes.setdefault(klass, {}).setdefault(label, {})[h] = {
                    "excess_pct": est, "band": [low, high], "days": days, "verdict": verdict(est, low, high),
                }
    report["extremes"] = extremes

    # Experiment 3: regimes. Trend and Stretch when the asset trends (ADX 25+) or ranges (under 20),
    # and when the class benchmark is above or below its 200-day average.
    regimes = {}
    for klass in ("stock", "crypto"):
        members = [t for t in dev if classes[t] == klass]
        for family in ("Trend", "Stretch", "score"):
            for h in (7, 14, 30):
                f = {t: fwd[t][h] for t in members}
                for label, mask_fn in (
                    ("asset trending (ADX 25+)", lambda d: d["x_adx"] >= 25),
                    ("asset ranging (ADX under 20)", lambda d: d["x_adx"] < 20),
                    ("benchmark above 200-day", lambda d: regime_flags(frames, d.index, klass) == 1),
                    ("benchmark below 200-day", lambda d: regime_flags(frames, d.index, klass) == 0),
                ):
                    sig, ff = panel({t: dev[t][family].where(mask_fn(dev[t])) for t in members}, f)
                    ts = pooled_rank_correlation(sig, ff, h)
                    tally()
                    regimes.setdefault(klass, {}).setdefault(family, {}).setdefault(label, {})[h] = {
                        "time_series_ic": ts, "verdict": verdict(*ts),
                    }
    report["regimes"] = regimes

    # Experiment 7: volatility. Does ATR% say how big the next moves will be, beyond trailing volatility?
    from backtest import volatility_report

    vol = {}
    for klass in ("stock", "crypto"):
        members = [t for t in dev if classes[t] == klass]
        per_h = {}
        for t in members:
            closes = development_view(frames[t][["close"]], start)["close"]
            rep = volatility_report(dev[t], closes, (1, 7, 14))
            for h, cell in rep["rows"].get("ATR %", {}).items():
                per_h.setdefault(h, []).append((cell.get("partial"), cell.get("noise_floor")))
        vol[klass] = {
            h: {
                "assets": len(cells),
                "mean_partial": float(np.nanmean([c for c, _ in cells if c is not None])) if cells else None,
                "assets_positive_beyond_noise": sum(1 for c, n in cells if c is not None and n and c > n),
            }
            for h, cells in per_h.items()
        }
    report["volatility"] = vol
    report["primary_dev"] = primary_on_development(frames, details, classes)
    return report


# ----------------------------------------------------------------------------- primary metrics (v2), development only

PRIMARY_HORIZON = 14
ATR_HORIZON = 7
MME = {"A1": 0.02, "A2": 0.02, "B": 0.50, "C1": 0.02, "C2": 0.02}
PRIMARY_DEV_RUNS = 2000


def _class_tables(frames, details, members, column):
    return pd.DataFrame({t: details[t][column] for t in members if column in details[t]})


def primary_on_development(frames: dict[str, pd.DataFrame], details: dict[str, pd.DataFrame],
                           classes: dict[str, str]) -> dict:
    """The five primary statistics of the validation spec, computed on development data only, plus the
    v1 statistic's expected small-sample bias. Assets are the hold-out list (the four already-seen assets
    are left out) so the numbers line up with what the hold-out will measure."""
    import research_stats as rst

    out = {"note": "Development data only (bars before the hold-out start). Exploratory: this is where the "
                   "claims come from, so these numbers cannot confirm anything."}
    members = {k: [t for t in details if classes[t] == k and t not in ALREADY_SEEN] for k in ("stock", "crypto")}
    closes = {k: pd.DataFrame({t: frames[t]["close"] for t in members[k]}) for k in members}

    # Claim A: stocks, relative timing (and the v1 statistic with its expected bias, for comparison)
    m, cl = members["stock"], closes["stock"]
    if m:
        a = {}
        for key, family, direction in (("A1", "Stretch", 1), ("A2", "Trend", -1)):
            sig = _class_tables(frames, details, m, family).reindex(cl.index)
            pct = pd.DataFrame({c: rst.expanding_percentile(sig[c]) for c in sig.columns})
            per_h = {}
            for h in HORIZONS:
                fwd = rst.forward_returns_table(cl, h).reindex(sig.index)
                num, den, _ = rst.relative_timing_rows(sig, fwd, percentiles=pct)
                per_h[h] = rst.studentised_test(num, den, h, rst.KAPPA["relative_timing"], direction,
                                                MME[key] if h == PRIMARY_HORIZON else None, runs=PRIMARY_DEV_RUNS)
            fwd = rst.forward_returns_table(cl, PRIMARY_HORIZON).reindex(sig.index)
            n1, d1 = rst.pooled_time_series_rows(sig, fwd)
            v1 = float(n1.sum() / d1.sum()) if d1.sum() else None
            a[key] = {"signal": family, "direction": direction, "relative_timing": per_h,
                      "v1_statistic_14d": v1,
                      "v1_expected_bias_14d": rst.rotation_null_mean(sig * direction, fwd, PRIMARY_HORIZON)}
        out["A"] = a

    # Claim B: crypto, Trend ranking spread, and the long-only portfolio gate
    m, cl = members["crypto"], closes["crypto"]
    if m:
        sig = _class_tables(frames, details, m, "Trend").reindex(cl.index)
        per_h = {}
        for h in HORIZONS:
            fwd = rst.forward_returns_table(cl, h)
            num, den, _ = rst.spread_rows(sig, fwd, MIN_PANEL)
            per_h[h] = rst.studentised_test(num, den, h, rst.KAPPA["spread"], 1,
                                            MME["B"] if h == PRIMARY_HORIZON else None, runs=PRIMARY_DEV_RUNS)
        fwd = rst.forward_returns_table(cl, PRIMARY_HORIZON)
        w = rst.spread_weights(sig.where(fwd.notna()), MIN_PANEL)
        f = fwd.fillna(0.0)
        avg = f.where(w != 0).mean(axis=1)
        top = (w.clip(lower=0) * f).sum(axis=1)
        bottom = (w.clip(upper=0).abs() * f).sum(axis=1)
        everyone = fwd.where(sig.notna()).mean(axis=1)
        live = w.abs().sum(axis=1) > 0
        decomposition = {"top_minus_all_pct": float((top - everyone)[live].mean()),
                         "all_minus_bottom_pct": float((everyone - bottom)[live].mean())}
        portfolio = {}
        for label, cost in (("base 0.20%", 0.002), ("stress 0.50%", 0.005)):
            strat = rst.long_only_portfolio(sig, cl, "third", PRIMARY_HORIZON, cost)
            bench = rst.long_only_portfolio(sig, cl, None, PRIMARY_HORIZON, cost)
            portfolio[label] = rst.portfolio_summary(strat, bench, 365, skip=PRIMARY_HORIZON + 1)
        btc = frames.get("BTC-USD")
        if btc is not None:
            r = btc["close"].reindex(cl.index).pct_change().iloc[PRIMARY_HORIZON + 2:]
            portfolio["bitcoin_buy_and_hold_pct_a_year"] = float(((1 + r).prod() ** (365 / max(1, len(r))) - 1) * 100)
        out["B"] = {"spread": per_h, "decomposition_14d": decomposition, "long_only": portfolio}

    # Claim C: ATR% against trailing volatility (primary) and stronger benchmarks (exploratory)
    c_out = {}
    for key, klass in (("C1", "stock"), ("C2", "crypto")):
        m, cl = members[klass], closes[klass]
        if not m:
            continue
        atr = _class_tables(frames, details, m, "x_atr_pct").reindex(cl.index)
        target = pd.DataFrame({c: rst.move_size(cl[c], ATR_HORIZON) for c in cl.columns})
        returns_ = cl.pct_change()
        benchmarks = {
            "trailing 14-day (primary)": pd.DataFrame({c: rst.trailing_move_size(cl[c], 14) for c in cl.columns}),
            "EWMA 0.94": np.sqrt((returns_ ** 2).ewm(alpha=0.06, adjust=False).mean()) * 100,
            "trailing 60-day": pd.DataFrame({c: rst.trailing_move_size(cl[c], 60) for c in cl.columns}),
        }
        rows = {}
        for name, bench in benchmarks.items():
            num, den = rst.forecast_gain_rows(atr, bench, target)
            rows[name] = rst.studentised_test(num, den, ATR_HORIZON, rst.KAPPA["forecast_gain"], 1,
                                              MME[key] if "primary" in name else None, runs=PRIMARY_DEV_RUNS)
        # expected-move multipliers: fitted on 2016-2021, checked on 2022 to the boundary, then refitted on all
        split = pd.Timestamp("2022-01-01")
        early_cl, early_atr = cl.loc[cl.index < split], atr.loc[atr.index < split]
        k_early = rst.fit_expected_move(early_atr, early_cl, ATR_HORIZON)
        late = cl.index >= split
        check = rst.coverage(atr.loc[late], cl.loc[late], ATR_HORIZON, k_early)
        k_all = rst.fit_expected_move(atr, cl, ATR_HORIZON)
        c_out[key] = {"class": klass, "forecast_gain": rows,
                      "expected_move": {"k_fit_2016_2021": k_early, "coverage_2022_to_boundary": check,
                                        "k_fit_all_development": k_all}}
    out["C"] = c_out
    return out


def _test_cell(t: dict, digits: int = 3) -> str:
    if not t or t.get("estimate") is None:
        return "too few"
    lo, hi = t["ci95"]
    cell = f"{_fmt(t['estimate'], digits)} [{_fmt(lo, digits)}, {_fmt(hi, digits)}] p={t['p_value']:.4f}"
    if "p_vs_mme" in t:
        cell += f", p vs minimum={t['p_vs_mme']:.3f}"
    return cell


def format_primary(primary: dict) -> str:
    lines = ["# Primary statistics on development data (method v2)", "", primary.get("note", ""), ""]
    lines.append("Cells: estimate [95% confidence interval] and one-sided p-value in the claimed direction "
                 "(studentised joint-date block bootstrap, t reference, inflation factor from the calibration study).")
    a = primary.get("A", {})
    if a:
        lines += ["", "## A. Stocks: relative timing (own-history percentile x return rank across stocks)", ""]
        lines.append("| Claim | " + " | ".join(f"{h}d" for h in HORIZONS) + " |")
        lines.append("| --- | " + " | ".join("---" for _ in HORIZONS) + " |")
        for key, cell in a.items():
            lines.append(f"| {key} {cell['signal']} ({'+' if cell['direction'] > 0 else '-'}) | " +
                         " | ".join(_test_cell(cell["relative_timing"].get(h, {})) for h in HORIZONS) + " |")
        lines += ["", "First-run statistic at 14 days, in the claimed direction, next to the value it is expected to "
                      "show with NO real effect (rotation null on the same data):", ""]
        for key, cell in a.items():
            lines.append(f"- {key}: first-run statistic {_fmt(cell['direction'] * (cell['v1_statistic_14d'] or 0))}; "
                         f"expected with no effect {_fmt(cell['v1_expected_bias_14d'])}")
    b = primary.get("B", {})
    if b:
        lines += ["", "## B. Crypto: Trend ranking, top third minus bottom third (%)", ""]
        lines.append("| Horizon | Spread |")
        lines.append("| --- | --- |")
        for h, t in b["spread"].items():
            lines.append(f"| {h}d | {_test_cell(t, 2)} |")
        d = b["decomposition_14d"]
        lines += ["", f"At 14 days the spread splits into top third minus all coins {_fmt(d['top_minus_all_pct'], 2)}% "
                      f"and all coins minus bottom third {_fmt(d['all_minus_bottom_pct'], 2)}%.", ""]
        lines.append("Long-only top third against all coins equally weighted (same schedule and costs), "
                     "14 staggered tranches as one portfolio:")
        lines.append("")
        for label, s in b["long_only"].items():
            if isinstance(s, dict):
                lo, hi = s["band95"]
                lines.append(f"- {label}: excess {s['excess_pct_a_year']:+.1f}% a year [{lo:+.1f}, {hi:+.1f}]; "
                             f"top third {s['strategy_pct_a_year']:+.1f}% a year (max drawdown "
                             f"{s['strategy_max_drawdown_pct']:.0f}%), all coins {s['benchmark_pct_a_year']:+.1f}% "
                             f"(max drawdown {s['benchmark_max_drawdown_pct']:.0f}%); traded per rebalance "
                             f"{s['strategy_traded_per_rebalance']:.2f} vs {s['benchmark_traded_per_rebalance']:.2f}")
            else:
                lines.append(f"- {label.replace('_', ' ')}: {s:+.1f}")
    c = primary.get("C", {})
    if c:
        lines += ["", "## C. ATR%: gain in rank correlation with later move size over each benchmark", ""]
        lines.append("| Claim | Benchmark | Gain |")
        lines.append("| --- | --- | --- |")
        for key, cell in c.items():
            for name, t in cell["forecast_gain"].items():
                lines.append(f"| {key} {cell['class']} | {name} | {_test_cell(t)} |")
        lines += ["", "Expected-move multipliers k (move within k x ATR% x sqrt(7) for 50% / 80% of asset-days):", ""]
        for key, cell in c.items():
            e = cell["expected_move"]
            lines.append(f"- {key} {cell['class']}: fitted 2016-2021 k50={e['k_fit_2016_2021'][0.5]:.3f}, "
                         f"k80={e['k_fit_2016_2021'][0.8]:.3f}; coverage 2022 to boundary "
                         f"{e['coverage_2022_to_boundary'][0.5]:.1%} / {e['coverage_2022_to_boundary'][0.8]:.1%}; "
                         f"fitted on all development k50={e['k_fit_all_development'][0.5]:.3f}, "
                         f"k80={e['k_fit_all_development'][0.8]:.3f}")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- report writing

def _fmt(value, digits=3):
    return "-" if value is None or (isinstance(value, float) and not math.isfinite(value)) else f"{value:+.{digits}f}"


def _band(cell, digits=3):
    est, low, high = cell
    if est is None:
        return "too few"
    if low is None:
        return _fmt(est, digits)
    return f"{_fmt(est, digits)} [{_fmt(low, digits)}, {_fmt(high, digits)}]"


def format_report(report: dict, parity: dict | None = None) -> str:
    lines = ["# Research run: development period", ""]
    lines.append(f"Generated {report['generated_at'][:16]} UTC. Hold-out starts {report['holdout_starts']} "
                 "and was NOT used. Every result below is from earlier dates only.")
    if report.get("method_version", 1) >= 2:
        lines.append("")
        lines.append("Method v2: prices on or after the hold-out start are removed before scoring, so forward-return "
                     "labels and the score histogram stop at the boundary. The first run (method v1, 31 Oct 2026) "
                     "let the last development labels use up to 31 bars of hold-out prices; its report is kept "
                     "unchanged on the reports branch.")
    lines.append("")
    lines.append(f"> {report['survivor_note']}")
    lines.append("")
    lines.append(f"Stocks ({len(report['assets']['stock'])}): {', '.join(report['assets']['stock'])}")
    lines.append(f"Crypto ({len(report['assets']['crypto'])}): {', '.join(report['assets']['crypto'])}")
    if parity:
        lines.append("")
        checks = parity.values() if "window" not in parity else [parity]
        for pc in checks:
            lines.append(f"Parity check: {pc['checked']} sampled days scored from the last {pc['window']} bars "
                         f"against all history; largest difference {pc['max_difference']:.2f} points.")
    lines.append("")
    lines.append(f"Tests counted: {report['tests_counted']}. At a 5% false-alarm rate about "
                 f"{round(report['tests_counted'] * 0.05)} would pass by luck alone.")
    lines += ["", "## 1. How often the score reaches each level", ""]
    lines.append("| Class | Days | 10th pct | Median | 90th pct | 70+ | 80+ | 30 or less | 20 or less | Min | Max |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for klass, h in report["histogram"]["per_class"].items():
        if not h.get("days"):
            continue
        lines.append(
            f"| {klass} | {h['days']} | {h['p10']:.0f} | {h['p50']:.0f} | {h['p90']:.0f} | "
            f"{h['share_at_or_above_70']:.1%} | {h['share_at_or_above_80']:.1%} | {h['share_at_or_below_30']:.1%} | "
            f"{h['share_at_or_below_20']:.1%} | {h['min']:.0f} | {h['max']:.0f} |"
        )
    lines.append("")
    lines.append("Score distribution, all assets of a class (days per 10-point band):")
    lines.append("")
    for klass, h in report["histogram"]["per_class"].items():
        if h.get("days"):
            lines.append(f"- {klass}: " + ", ".join(f"{k}: {v}" for k, v in h["bins"].items()))

    lines += ["", "## 2. Signals: score, families and single factors", ""]
    lines.append("Each cell: estimate [95% band]. Time series = each asset against its own history, pooled. "
                 "Cross-section = assets ranked against their own class each day. Ranking = top third minus "
                 "bottom third, % return. Positive means more points came before better returns.")
    for klass, names in report["signals"].items():
        lines += ["", f"### {klass}", ""]
        lines.append("| Signal | Horizon | Time series | Cross-section | Ranking (%) |")
        lines.append("| --- | --- | --- | --- | --- |")
        for name, per_h in names.items():
            for h, cell in per_h.items():
                lines.append(f"| {name} | {h}d | {_band(cell['time_series_ic'])} ({cell['time_series']}) | "
                             f"{_band(cell['cross_section_ic'])} ({cell['cross_section']}) | "
                             f"{_band(cell['top_minus_bottom_pct'], 2)} ({cell['ranking']}) |")

    lines += ["", "## 3. Extremes", ""]
    lines.append("Average forward return on those days minus the asset's own average, % [95% band], and how many days.")
    for klass, rules in report["extremes"].items():
        lines += ["", f"### {klass}", ""]
        lines.append("| Rule | " + " | ".join(f"{h}d" for h in HORIZONS) + " |")
        lines.append("| --- | " + " | ".join("---" for _ in HORIZONS) + " |")
        for label, per_h in rules.items():
            cells = []
            for h in HORIZONS:
                c = per_h.get(h, {})
                cells.append(f"{_band((c.get('excess_pct'), *c.get('band', [None, None])), 2)} n={c.get('days', 0)}")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")

    lines += ["", "## 4. Regimes", ""]
    lines.append("Pooled time-series rank correlation inside each condition [95% band].")
    for klass, fams in report["regimes"].items():
        lines += ["", f"### {klass}", ""]
        lines.append("| Signal | Condition | 7d | 14d | 30d |")
        lines.append("| --- | --- | --- | --- | --- |")
        for fam, conds in fams.items():
            for cond, per_h in conds.items():
                lines.append(f"| {fam} | {cond} | " + " | ".join(
                    f"{_band(per_h[h]['time_series_ic'])}" for h in (7, 14, 30)) + " |")

    lines += ["", "## 5. Volatility (ATR%)", ""]
    lines.append("Mean partial rank correlation of ATR% with the size of later moves, after trailing volatility; "
                 "and how many assets clear their own noise band.")
    lines.append("")
    for klass, per_h in report["volatility"].items():
        for h, cell in per_h.items():
            lines.append(f"- {klass}, {h}d: mean {_fmt(cell['mean_partial'])}, "
                         f"{cell['assets_positive_beyond_noise']} of {cell['assets']} assets clear the band")
    return "\n".join(lines) + "\n"


# ----------------------------------------------------------------------------- command line

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Research backtests for the scoring audit.")
    sub = parser.add_subparsers(dest="command", required=True)
    cache = sub.add_parser("cache", help="download the universe once")
    cache.add_argument("--out", required=True)
    cache.add_argument("--years", type=int, default=10)
    run = sub.add_parser("run", help="run the experiments on the saved prices")
    run.add_argument("--prices", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--limit", type=int, default=0, help="only this many assets per class (a quick check)")
    args = parser.parse_args(argv)

    if args.command == "cache":
        manifest = download_universe(args.out, args.years)
        print(f"Saved {len(manifest['files'])} tickers; {len(manifest['failed'])} failed: {list(manifest['failed'])}")
        return 0

    frames = load_cache(args.prices)
    if args.limit:
        keep = [t for t in UNIVERSE_STOCKS if t in frames][: args.limit] + \
               [t for t in UNIVERSE_CRYPTO if t in frames][: args.limit] + [BENCHMARKS["stock"]]
        frames = {t: frames[t] for t in keep if t in frames}
    start = checked_start(frames)
    frames = development_frames(frames, start)       # nothing on or after the hold-out start from here on
    details = score_all(frames)
    parity = {w: parity_check(frames, details, window=w) for w in PARITY_WINDOWS}
    report = run_experiments(frames, details, start)
    report["parity"] = parity
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(format_report(report, parity), encoding="utf-8")
    (out / "primary_dev.md").write_text(format_primary(report.get("primary_dev", {})), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(format_report(report, parity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
