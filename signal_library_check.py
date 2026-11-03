"""
Descriptive check of the new Signal Library calculations (development data only, CI).

Not a performance test: no forward returns are used. Daily price files are cut at the hold-out start
as they are read (research.load_cache), as in the other development checks.

It reports, pooled over the assets of each class:
- how often trend direction, momentum direction and swing structure agree (when neither is mixed);
- how the efficiency ratio relates to ADX and to the existing Trend reading (Spearman, within asset);
- how often each divergence type is confirmed per 1,000 candles, and the share later invalidated;
- how many support/resistance zones are found and how wide they are;
- the time each calculation takes on a year of daily candles.
CMF, ATR% and band width were already covered by the technical coverage audit and are not repeated.

    python signal_library_check.py --prices prices --out out
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import regime as regime_rules
import research as rs
from scoring import calculate_indicators
from signal_library import swings as sw
from signal_library.signals_ta import efficiency_ratio
from ta_coverage_check import candidates

STEP = 5  # sample every 5th candle for the state comparisons


def _momentum(row) -> str:
    h, r = row.get("MACDh_12_26_9"), row.get("rsi")
    if h is None or r is None or pd.isna(h) or pd.isna(r):
        return "mixed"
    return "up" if h > 0 and r > 50 else "down" if h < 0 and r < 50 else "mixed"


def per_asset(ind: pd.DataFrame) -> dict:
    high, low, close = ind["high"].to_numpy(), ind["low"].to_numpy(), ind["close"].to_numpy()
    swings_all = sw.pivots(high, low, 5, 5)
    rows = []
    for t in range(260, len(ind), STEP):
        known = [p for p in swings_all if p["confirmed_index"] <= t]
        row = ind.iloc[t]
        rows.append({
            "trend": regime_rules._direction(row["close"], row.get("sma_50"), row.get("sma_200")),
            "momentum": _momentum(row),
            "structure": sw.structure_state(sw.label_swings(known)),
            "er": efficiency_ratio(ind["close"].iloc[:t + 1], 20),
            "adx": row.get("adx"),
        })
    states = pd.DataFrame(rows)
    div = {"rsi": sw.divergences(high, low, close, ind["rsi"].to_numpy())["events"]}
    hist = next((c for c in ind.columns if str(c).startswith("MACDh_")), None)
    if hist:
        div["macd"] = sw.divergences(high, low, close, ind[hist].to_numpy())["events"]
    zones = sw.zones(high, low, close, float(ind["atr"].iloc[-1]))
    return {"states": states, "div": div, "zones": zones, "bars": len(ind)}


def agreement(states: pd.DataFrame, a: str, b: str) -> dict:
    both = states[(states[a] != "mixed") & (states[b] != "mixed") & (states[a] != "unknown") & (states[b] != "unknown")]
    return {"share_both_directional": round(len(both) / max(1, len(states)), 3),
            "agree_when_both_directional": None if both.empty else round(float((both[a] == both[b]).mean()), 3)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    start = rs.checked_start_from_manifest(args.prices)
    frames = rs.load_cache(args.prices, before=start)
    assert all(f.index.max() < start for f in frames.values())
    report = {"before": str(start.date()), "classes": {}}
    md = [f"# Signal Library descriptive check (development data only, before {start.date()})", "",
          "No forward returns. Agreement is measured on every 5th daily candle after a 260-candle warm-up.", ""]
    timings = {}
    for klass in ("stock", "crypto"):
        results, er_rows = [], []
        for ticker, frame in frames.items():
            if ticker == rs.BENCHMARKS["stock"] or rs.asset_class(ticker) != klass or len(frame) < 400:
                continue
            ind = calculate_indicators(frame)
            res = per_asset(ind)
            results.append(res)
            trend_cluster = candidates(ind, None)["trend"].reindex(ind.index)
            sample = pd.DataFrame({"er": [efficiency_ratio(ind["close"].iloc[:t + 1], 20) for t in range(260, len(ind), STEP)],
                                   "adx": ind["adx"].to_numpy()[260::STEP],
                                   "trend_reading": trend_cluster.abs().to_numpy()[260::STEP]})
            er_rows.append(sample.rank(pct=True))
        if not results:
            continue
        states = pd.concat([r["states"] for r in results], ignore_index=True)
        bars = sum(r["bars"] for r in results)
        er = pd.concat(er_rows).corr()
        divs = {}
        for osc in ("rsi", "macd"):
            events = [e for r in results for e in r["div"].get(osc, [])]
            for kind in (sw.REGULAR_BULL, sw.HIDDEN_BULL, sw.REGULAR_BEAR, sw.HIDDEN_BEAR):
                picked = [e for e in events if e["type"] == kind]
                divs[f"{osc} {kind}"] = {
                    "per_1000_candles": round(len(picked) / bars * 1000, 2),
                    "share_invalidated": None if not picked else round(sum(e["status"] == "invalidated" for e in picked) / len(picked), 3),
                    "share_expired": None if not picked else round(sum(e["status"] == "expired" for e in picked) / len(picked), 3),
                }
        zone_counts = [len(r["zones"]["support"]) + len(r["zones"]["resistance"]) for r in results]
        widths = [(z["high"] - z["low"]) / z["mid"] * 100 for r in results for side in ("support", "resistance")
                  for z in r["zones"][side] if z["mid"]]
        out = {
            "assets": len(results), "candles": bars,
            "trend_vs_momentum": agreement(states, "trend", "momentum"),
            "trend_vs_structure": agreement(states, "trend", "structure"),
            "momentum_vs_structure": agreement(states, "momentum", "structure"),
            "spearman_er_vs_adx": round(float(er.loc["er", "adx"]), 3),
            "spearman_er_vs_abs_trend_reading": round(float(er.loc["er", "trend_reading"]), 3),
            "divergences": divs,
            "zones_per_asset_median": float(np.median(zone_counts)),
            "zone_width_pct_median": None if not widths else round(float(np.median(widths)), 3),
        }
        report["classes"][klass] = out
        md += [f"## {klass} ({len(results)} assets, {bars} candles)", "",
               "| Pair | both directional | agree when both directional |", "|---|---|---|"]
        for key in ("trend_vs_momentum", "trend_vs_structure", "momentum_vs_structure"):
            md.append(f"| {key.replace('_', ' ')} | {out[key]['share_both_directional']} | {out[key]['agree_when_both_directional']} |")
        md += ["", f"- Efficiency ratio vs ADX (Spearman, within asset): {out['spearman_er_vs_adx']}",
               f"- Efficiency ratio vs strength of the Trend reading: {out['spearman_er_vs_abs_trend_reading']}",
               f"- Zones kept per asset (median): {out['zones_per_asset_median']}; zone width median "
               f"{out['zone_width_pct_median']}% of price", "", "| Divergence | per 1,000 candles | invalidated within 30 candles | expired untouched |",
               "|---|---|---|---|"]
        md += [f"| {k} | {v['per_1000_candles']} | {v['share_invalidated']} | {v['share_expired']} |" for k, v in divs.items()]
        md.append("")
        # Timing on one year of candles of the first asset.
        sample_frame = calculate_indicators(next(f for t, f in frames.items() if rs.asset_class(t) == klass).iloc[-365:])
        h, l, c = sample_frame["high"].to_numpy(), sample_frame["low"].to_numpy(), sample_frame["close"].to_numpy()
        for name, fn in (("pivots", lambda: sw.pivots(h, l)),
                         ("divergences (RSI)", lambda: sw.divergences(h, l, c, sample_frame["rsi"].to_numpy())),
                         ("structure breaks", lambda: sw.structure_breaks(h, l, c)),
                         ("zones", lambda: sw.zones(h, l, c, float(sample_frame["atr"].iloc[-1])))):
            t0 = time.perf_counter()
            for _ in range(5):
                fn()
            timings[f"{klass}: {name}"] = round((time.perf_counter() - t0) / 5 * 1000, 2)
    report["timing_ms_per_year_of_daily_candles"] = timings
    md += ["## Calculation time (ms, one year of daily candles)", ""] + [f"- {k}: {v}" for k, v in timings.items()]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "signal_library_check.json").write_text(json.dumps(report, indent=1))
    Path(args.out, "signal_library_check.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
