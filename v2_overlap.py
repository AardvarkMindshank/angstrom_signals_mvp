"""Lightweight overlap check for signals v2 (development data only).

How much do the ten indicator readings, and the v2 components, move together? How often do Trend and
Stretch disagree? Are any components saturated at +-1 (scale too tight) or stuck near 0 (too loose)?
Descriptive only: no forward returns are computed and no predictive claim is tested.

Every price file is cut at the hold-out start (30 Oct 2024) as it is read, using research.load_cache.

    python v2_overlap.py --prices prices --out out
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

READINGS = {
    "RSI": lambda f: f["rsi"],
    "Stochastic": lambda f: f["stoch_k"],
    "Bollinger pos": lambda f: (f["close"] - f[v2._col(f, "BBL_")]) / (f[v2._col(f, "BBU_")] - f[v2._col(f, "BBL_")]),
    "vs SMA20": lambda f: f["close"] / f["sma_20"] - 1,
    "vs SMA50": lambda f: f["close"] / f["sma_50"] - 1,
    "vs SMA200": lambda f: f["close"] / f["sma_200"] - 1,
    "MACD/close": lambda f: f[v2._col(f, "MACD_")] / f["close"],
    "MACD hist/close": lambda f: f[v2._col(f, "MACDh_")] / f["close"],
    "Ichimoku vs cloud": lambda f: f["close"] / ((f["ichi_span_a"] + f["ichi_span_b"]) / 2) - 1,
    "ADX": lambda f: f["adx"],
    "7d change": lambda f: f["change_7d"],
    "OBV vs avg": lambda f: (f["obv"] - f["obv_sma_20"]) / f["vol_sma_20"],
    "Volume ratio": lambda f: f["volume_ratio"],
    "ATR%": lambda f: f["atr"] / f["close"],
}


def md_table(frame: pd.DataFrame) -> str:
    cols = [str(c) for c in frame.columns]
    lines = ["| | " + " | ".join(cols) + " |", "| --- | " + " | ".join("---" for _ in cols) + " |"]
    for idx, row in frame.iterrows():
        lines.append(f"| {idx} | " + " | ".join("" if pd.isna(v) else f"{v:.2f}" for v in row.values) + " |")
    return "\n".join(lines)


def component_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for i in range(len(frame)):
        comps, _ = v2._components(frame.iloc[i], frame)
        rows[frame.index[i]] = comps
    return pd.DataFrame.from_dict(rows, orient="index")


def pooled_spearman(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Rank within each asset (so levels don't mix across assets), then correlate the pooled ranks."""
    ranked = [t.rank(pct=True) for t in tables if len(t)]
    return pd.concat(ranked).corr(method="pearson")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    start = rs.checked_start_from_manifest(args.prices)
    frames = rs.load_cache(args.prices, before=start)        # development rows only
    assert all(f.index.max() < start for f in frames.values())
    out = {"version": v2.VERSION, "fingerprint": v2.FINGERPRINT, "classes": {}}
    md = [f"# Signals v2 overlap check (development data only, before {start.date()})", "",
          f"Signals {v2.VERSION}, fingerprint {v2.FINGERPRINT}. Descriptive: no returns, no predictive test.", ""]
    for klass in ("stock", "crypto"):
        readings, comps = [], []
        for ticker, frame in frames.items():
            if ticker == rs.BENCHMARKS["stock"] or rs.asset_class(ticker) != klass:
                continue
            ind = calculate_indicators(frame).iloc[250:]          # skip warm-up
            readings.append(pd.DataFrame({k: fn(ind) for k, fn in READINGS.items()}).replace([np.inf, -np.inf], np.nan))
            comps.append(component_table(ind))
        r_corr = pooled_spearman(readings)
        c_all = pd.concat(comps)
        c_corr = pooled_spearman(comps)
        clusters = pd.DataFrame({
            key: c_all[spec["components"]].mean(axis=1, skipna=True) for key, spec in v2.CLUSTERS.items()
        })
        lvl = v2.DEFINITIONS["against_trend_level"]
        t, s = clusters["trend"], clusters["stretch"]
        disagree = ((t.abs() >= lvl) & (s.abs() >= lvl) & ((t > 0) != (s > 0))).mean()
        sat = (c_all.abs() >= 0.95).mean()
        near0 = (c_all.abs() <= 0.05).mean()
        eig = np.sort(np.linalg.eigvalsh(c_corr.fillna(0).values))[::-1]
        share = np.cumsum(eig) / eig.sum()
        out["classes"][klass] = {
            "reading_correlations": r_corr.round(3).to_dict(),
            "component_correlations": c_corr.round(3).to_dict(),
            "cluster_correlations": clusters.corr(method="spearman").round(3).to_dict(),
            "trend_stretch_disagree_share": float(disagree),
            "component_saturated_share": sat.round(3).to_dict(),
            "component_near_zero_share": near0.round(3).to_dict(),
            "component_quantiles": c_all.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(3).to_dict(),
            "cluster_quantiles": clusters.quantile([0.05, 0.25, 0.5, 0.75, 0.95]).round(3).to_dict(),
            "eigen_share": [round(float(x), 3) for x in share],
            "rows": int(len(c_all)),
        }
        md += [f"## {klass} ({len(c_all)} asset-days)", "", "### Component correlations (within-asset ranks)", "",
               md_table(c_corr), "", "### Cluster correlations", "",
               md_table(clusters.corr(method="spearman")), "",
               f"Trend and Stretch disagree (both at least {lvl} and opposite signs) on {disagree:.1%} of days.", "",
               "Independent dimensions (cumulative variance share of the 9 components): "
               + ", ".join(f"{x:.0%}" for x in share), "",
               "### Component spread", "", md_table(pd.DataFrame({"saturated |v|>=0.95": sat, "near zero |v|<=0.05": near0,
                                                         "5%": c_all.quantile(0.05), "median": c_all.median(),
                                                         "95%": c_all.quantile(0.95)})), "",
               "### Reading correlations (within-asset ranks)", "", md_table(r_corr), ""]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "overlap.json").write_text(json.dumps(out, indent=1, default=str))
    (Path(args.out) / "overlap.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
