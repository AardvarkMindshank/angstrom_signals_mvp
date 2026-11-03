"""Exploratory overlap check for candidate technical additions (development data only).

Question: would a candidate add information the current readings (Trend, Stretch, Flow, ATR% context)
do not already carry? Descriptive only: no forward returns, nothing about predicting prices.

Every price file is cut at the hold-out start as it is read (research.load_cache, as in v2_overlap.py).

Two kinds of overlap:
- within-asset: rank each series inside its own history, pool the assets, Spearman correlation
  ("does this move with Trend over time?");
- cross-sectional: on each date rank the assets, correlate, average over dates
  ("does this order the assets differently from Trend on the same day?").

    python ta_coverage_check.py --prices prices --out out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import research as rs
import signals_v2 as v2
from scoring import calculate_indicators
from v2_overlap import component_table, md_table

WARMUP = 260


def candidates(ind: pd.DataFrame, bench: pd.Series | None) -> pd.DataFrame:
    close, high, low, vol = ind["close"], ind["high"], ind["low"], ind["volume"].fillna(0)
    out = pd.DataFrame(index=ind.index)
    comps = component_table(ind)
    for key, spec in v2.CLUSTERS.items():
        out[key] = comps[spec["components"]].mean(axis=1, skipna=True)
    out["obv_comp"], out["heavy_comp"], out["momentum_comp"] = comps["obv"], comps["heavy_volume"], comps["momentum"]
    # OBV with every day's volume set to 1: the same sum of up and down days, without the volume.
    unit = np.sign(close.diff()).fillna(0).cumsum()
    out["obv_vs_avg"] = (ind["obv"] - ind["obv_sma_20"]) / ind["vol_sma_20"].replace(0, np.nan)
    out["obv_no_volume"] = unit - unit.rolling(20).mean()
    span = (high - low).replace(0, np.nan)
    mfv = ((close - low) - (high - close)) / span * vol
    out["cmf_20"] = mfv.rolling(20).sum() / vol.rolling(20).sum().replace(0, np.nan)
    if bench is not None:
        b = bench.reindex(ind.index).ffill()
        for n in (21, 63, 126):
            out[f"rs_{n}"] = np.log(close / close.shift(n)) - np.log(b / b.shift(n))
    out["dist_high_252"] = close / high.rolling(252).max() - 1
    out["dist_low_252"] = close / low.rolling(252).min() - 1
    lo55, hi55 = low.rolling(55).min(), high.rolling(55).max()
    out["range_pos_55"] = (close - lo55) / (hi55 - lo55).replace(0, np.nan)
    out["atr_pct"] = ind["atr"] / close
    upper, lower = ind[v2._col(ind, "BBU_")], ind[v2._col(ind, "BBL_")]
    out["bb_width"] = (upper - lower) / ((upper + lower) / 2)
    out["realised_vol_20"] = np.log(close).diff().rolling(20).std()
    out["atr_pct_rank_252"] = out["atr_pct"].rolling(252).rank(pct=True)
    out["bb_width_rank_252"] = out["bb_width"].rolling(252).rank(pct=True)
    dollar = (close * vol).replace(0, np.nan)
    out["traded_value_20"] = np.log(dollar.rolling(20).mean())
    out["amihud_20"] = np.log((np.log(close).diff().abs() / dollar).rolling(20).mean())
    out["volume_cv_20"] = vol.rolling(20).std() / vol.rolling(20).mean().replace(0, np.nan)
    out["adx"] = ind["adx"]
    return out.iloc[WARMUP:].replace([np.inf, -np.inf], np.nan)


def pooled(tables: list[pd.DataFrame], cols: list[str]) -> pd.DataFrame:
    ranked = [t[cols].rank(pct=True) for t in tables if len(t)]
    return pd.concat(ranked).corr(method="pearson")


def cross_sectional(tables: dict[str, pd.DataFrame], a: str, b: str, min_assets: int = 8) -> float | None:
    left = pd.DataFrame({k: t[a] for k, t in tables.items() if a in t})
    right = pd.DataFrame({k: t[b] for k, t in tables.items() if b in t})
    vals = []
    for day in left.index.intersection(right.index):
        x, y = left.loc[day], right.loc[day]
        ok = x.notna() & y.notna()
        if ok.sum() >= min_assets:
            vals.append(x[ok].rank().corr(y[ok].rank()))
    return float(np.nanmean(vals)) if vals else None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    start = rs.checked_start_from_manifest(args.prices)
    frames = rs.load_cache(args.prices, before=start)
    assert all(f.index.max() < start for f in frames.values())
    out = {"version": v2.VERSION, "fingerprint": v2.FINGERPRINT, "before": str(start.date()), "classes": {}}
    md = [f"# Technical coverage overlap check (development data only, before {start.date()})", "",
          "Descriptive overlap, no forward returns. Within-asset = pooled Spearman of each asset's own ranks; "
          "cross-sectional = Spearman across assets on the same day, averaged over days.", ""]
    for klass in ("stock", "crypto"):
        bench_key = rs.BENCHMARKS[klass]
        bench = frames[bench_key]["close"] if bench_key in frames else None
        tables, zero_volume = {}, []
        for ticker, frame in frames.items():
            if ticker == rs.BENCHMARKS["stock"] or rs.asset_class(ticker) != klass:
                continue
            ind = calculate_indicators(frame)
            zero_volume.append(float((frame["volume"].fillna(0) <= 0).mean()))
            tables[ticker] = candidates(ind, None if ticker == bench_key else bench)
        cols = ["trend", "stretch", "flow", "obv_comp", "heavy_comp", "momentum_comp", "obv_vs_avg", "obv_no_volume",
                "cmf_20", "rs_21", "rs_63", "rs_126", "dist_high_252", "dist_low_252", "range_pos_55", "atr_pct",
                "atr_pct_rank_252", "bb_width", "bb_width_rank_252", "realised_vol_20", "traded_value_20", "amihud_20",
                "volume_cv_20", "adx"]
        rows = [t.reindex(columns=cols) for t in tables.values()]
        corr = pooled(rows, cols)
        focus = corr.loc[cols, ["trend", "stretch", "flow", "atr_pct"]]
        xs = {f"{a} vs {b}": cross_sectional(tables, a, b) for a, b in (
            ("rs_63", "trend"), ("rs_126", "trend"), ("rs_21", "stretch"), ("dist_high_252", "trend"),
            ("range_pos_55", "stretch"), ("traded_value_20", "atr_pct"), ("amihud_20", "atr_pct"),
            ("bb_width", "atr_pct"), ("cmf_20", "flow"), ("flow", "stretch"))}
        pairs = {
            "OBV vs OBV without volume (within-asset)": corr.loc["obv_vs_avg", "obv_no_volume"],
            "Flow vs Stretch": corr.loc["flow", "stretch"],
            "OBV part vs 7-day move part": corr.loc["obv_comp", "momentum_comp"],
            "Heavy-volume part vs Stretch": corr.loc["heavy_comp", "stretch"],
            "CMF vs Flow": corr.loc["cmf_20", "flow"],
            "CMF vs Stretch": corr.loc["cmf_20", "stretch"],
            "BB width rank vs ATR% rank": corr.loc["bb_width_rank_252", "atr_pct_rank_252"],
            "Realised vol vs ATR%": corr.loc["realised_vol_20", "atr_pct"],
            "RS 63d vs Trend": corr.loc["rs_63", "trend"],
            "Distance from 1-year high vs Trend": corr.loc["dist_high_252", "trend"],
            "55-day range position vs Stretch": corr.loc["range_pos_55", "stretch"],
            "Traded value vs ATR%": corr.loc["traded_value_20", "atr_pct"],
        }
        out["classes"][klass] = {
            "assets": len(tables), "rows": int(sum(len(t) for t in rows)),
            "zero_volume_share_median": float(np.median(zero_volume)) if zero_volume else None,
            "focus": focus.round(3).to_dict(), "pairs": {k: round(float(v), 3) for k, v in pairs.items()},
            "cross_sectional": {k: (None if v is None else round(v, 3)) for k, v in xs.items()},
        }
        md += [f"## {klass} ({len(tables)} assets, {sum(len(t) for t in rows)} asset-days)", "",
               f"Median share of zero-volume days: {out['classes'][klass]['zero_volume_share_median']:.1%}", "",
               "### Key pairs (within-asset)", "", "| Pair | Spearman |", "|---|---|"]
        md += [f"| {k} | {v:.2f} |" for k, v in pairs.items()]
        md += ["", "### Cross-sectional (same day, across assets)", "", "| Pair | Spearman |", "|---|---|"]
        md += [f"| {k} | {'n/a' if v is None else f'{v:.2f}'} |" for k, v in xs.items()]
        md += ["", "### Every candidate against Trend, Stretch, Flow and ATR% (within-asset)", "", md_table(focus), ""]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "ta_coverage.json").write_text(json.dumps(out, indent=1, default=str))
    (Path(args.out) / "ta_coverage.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
