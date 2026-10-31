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
HORIZONS = (1, 3, 7, 14, 30)
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
    bottom-third return. Assets are only ever ranked against their own class."""
    rows = []
    for klass in sorted(set(classes.values())):
        members = [c for c in sig.columns if classes.get(c) == klass]
        if len(members) < MIN_PANEL:
            continue
        s_all, f_all = sig[members], fwd[members]
        for date in s_all.index:
            s, f = s_all.loc[date], f_all.loc[date]
            keep = s.notna() & f.notna()
            if keep.sum() < MIN_PANEL or s[keep].nunique() < 2:
                continue
            s, f = s[keep], f[keep]
            ic = s.rank().corr(f.rank())
            third = max(1, len(s) // 3)
            order = s.sort_values(kind="mergesort")
            spread = f[order.index[-third:]].mean() - f[order.index[:third]].mean()
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


def run_experiments(frames: dict[str, pd.DataFrame], details: dict[str, pd.DataFrame]) -> dict:
    start = holdout_start(frames)
    classes = {t: asset_class(t) for t in details}
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "holdout_starts": str(start)[:10],
        "assets": {k: sorted(t for t in details if classes[t] == k) for k in ("stock", "crypto")},
        "survivor_note": SURVIVOR_NOTE,
        "tests_counted": 0,
    }

    # Point 1: how often the score reaches each level (all dates; no returns involved).
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
    return report


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
    lines.append("")
    lines.append(f"> {report['survivor_note']}")
    lines.append("")
    lines.append(f"Stocks ({len(report['assets']['stock'])}): {', '.join(report['assets']['stock'])}")
    lines.append(f"Crypto ({len(report['assets']['crypto'])}): {', '.join(report['assets']['crypto'])}")
    if parity:
        lines.append("")
        lines.append(f"Parity check: {parity['checked']} sampled days scored from the last {parity['window']} bars "
                     f"against all history; largest difference {parity['max_difference']:.2f} points.")
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
    details = score_all(frames)
    parity = parity_check(frames, details)
    report = run_experiments(frames, details)
    report["parity"] = parity
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(format_report(report, parity), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(format_report(report, parity))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
