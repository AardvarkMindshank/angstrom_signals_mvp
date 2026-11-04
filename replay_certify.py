"""
Replay certification suite and benchmarks (CI). Design: docs/design/point_in_time.md, sections 4 and 8.

    python replay_certify.py --prices prices --out out --check     certify; fail if the committed record differs
    python replay_certify.py --prices prices --out out --write     certify and update signal_library/certification.json
    python replay_certify.py --prices prices --out out --benchmark time and memory of 30- and 365-step replays

Data: synthetic datasets, plus frozen development daily data from the research price cache (rows dated on or
after 2024-10-30 are filtered out right after each file is parsed, so they never reach evaluation).
Indicators: the real ones (scoring.calculate_indicators), so this needs pandas_ta (CI).
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

INDICATORS = "scoring:calculate_indicators"
RECORD = Path(__file__).resolve().parent / "signal_library" / "certification.json"
COMPARED = ("suite_version", "code_sha256", "signals")


def datasets(prices: str | None, days: int):
    from signal_library import certify as cf

    out = [cf.synthetic_crypto(days=days, seed=11), cf.synthetic_equity(days=days, seed=23)]
    out += cf.synthetic_flows(seed=5)
    if prices and Path(prices, "manifest.json").exists():
        out += cf.development_datasets(prices)
    return out


def certify(args) -> int:
    from signal_library import certification, certify as cf

    started = time.time()
    data = datasets(args.prices, args.days)
    for ds in data:
        print(f"dataset {ds.name}: {ds.description}")
    signals = cf.run_suite(data, indicators=INDICATORS, cutoffs=args.cutoffs)
    record = {
        "suite_version": certification.SUITE_VERSION,
        "code_sha256": certification.code_hash(),
        "generated_by": {"git_commit": os.environ.get("GITHUB_SHA"), "run_id": os.environ.get("GITHUB_RUN_ID"),
                         "note": "administrative; not compared"},
        "datasets": [{"name": d.name, "description": d.description} for d in data],
        "cutoffs_per_dataset_minimum": args.cutoffs,
        "signals": signals,
    }
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "certification.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    md = report(record, time.time() - started)
    Path(args.out, "certification.md").write_text(md)
    print(md)
    if args.write:
        RECORD.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
        print(f"updated {RECORD}")
    if args.check:
        committed = json.loads(RECORD.read_text()) if RECORD.exists() else {}
        if {k: committed.get(k) for k in COMPARED} != {k: record[k] for k in COMPARED}:
            print("The committed certification record differs from this run: re-certify and commit "
                  "signal_library/certification.json (out/certification.json).")
            return 1
        print("Committed certification record matches this run.")
    return 0


def report(record: dict, seconds: float) -> str:
    lines = [f"# Replay certification (suite v{record['suite_version']})", "",
             f"Code hash {record['code_sha256'][:12]}; {len(record['datasets'])} datasets; at least "
             f"{record['cutoffs_per_dataset_minimum']} cutoffs per dataset; {seconds / 60:.1f} minutes.", "",
             "| Signal | Timeframe | Algorithm | Slice shortcut | Cutoffs | Checks (reference/poison/cache/timestamps) | Readings | Reason |",
             "|---|---|---|---|---|---|---|---|"]
    certified = total = 0
    for key, tfs in sorted(record["signals"].items()):
        for tf, e in sorted(tfs.items(), key=lambda x: ["15m", "1h", "4h", "1D", "1W"].index(x[0])):
            total += 1
            certified += e["algorithm"] == "certified"
            c = e.get("checks") or {}
            checks = "/".join(str(c.get(k, 0)) for k in ("reference", "poison", "cache", "timestamps"))
            reason = (e.get("reason") or (e.get("slice_reason") if not e.get("slice_equivalent") else "") or "")
            lines.append(f"| {key} | {tf} | {e['algorithm']} | {'yes' if e.get('slice_equivalent') else 'no'} | "
                         f"{e.get('cutoffs', 0)} | {checks} | {e.get('result_statuses')} | {str(reason)[:160].replace('|', '/')} |")
    lines += ["", f"Certified: {certified} of {total} signal/timeframe pairs.", ""]
    for d in record["datasets"]:
        lines.append(f"- {d['name']}: {d['description']}")
    return "\n".join(lines) + "\n"


def rss_mb() -> float:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def benchmark(args) -> int:
    import pandas as pd

    from signal_library import REGISTRY, SignalRef, certify as cf, engine
    from signal_library.replay import CERTIFICATION, ReplayRun

    cf._INDICATORS.update(path=INDICATORS, fn=cf._indicators(INDICATORS))
    data = [cf.synthetic_crypto(days=args.days, seed=11)]
    if args.prices and Path(args.prices, "manifest.json").exists():
        data += [d for d in cf.development_datasets(args.prices, tickers=("BTC-USD", "AAPL"))]
    refs = [SignalRef.make(d, "1D") for d in REGISTRY.latest()
            if "candles" in d.requires and "1D" in d.timeframes and not d.id.startswith("test.")]
    rows = []
    for ds in data:
        ends = ds.histories["1D"].ends
        for steps in (30, 365):
            cutoffs = [pd.Timestamp(int(x), tz="UTC") for x in ends[-steps - 1:-1]]
            for shortcut in (False, True):
                for traced in (False, True):
                    engine.clear_cache()
                    gc.collect()
                    before = rss_mb()
                    if traced:
                        tracemalloc.start()
                    t0 = time.perf_counter()
                    run = ReplayRun(CERTIFICATION, ds.candles, indicators=cf._INDICATORS["fn"], shortcut=shortcut)
                    statuses = {}
                    for t in cutoffs:
                        for r in engine.evaluate(refs, run.context(ds.kind, ds.asset_id, t)).values():
                            statuses[r.status] = statuses.get(r.status, 0) + 1
                    secs = time.perf_counter() - t0
                    peak = None
                    if traced:
                        peak = tracemalloc.get_traced_memory()[1] / 2**20
                        tracemalloc.stop()
                    del run
                    gc.collect()
                    if not traced:
                        rows.append({"dataset": ds.name, "steps": steps, "path": "slice shortcut" if shortcut else "exact",
                                     "seconds": round(secs, 2), "seconds_per_step": round(secs / steps, 3),
                                     "rss_growth_MB": round(rss_mb() - before, 1), "statuses": statuses})
                    else:
                        rows[-1]["python_peak_MB"] = round(peak, 1)
    out = {"signals_per_step": len(refs), "note": "Every 1D candle signal incl. multi-timeframe alignment, per step; "
           "certification mode (no certification lookup), real indicators.", "rows": rows,
           "rss_end_MB": round(rss_mb(), 1)}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "replay_benchmark.json").write_text(json.dumps(out, indent=1))
    md = ["# Replay benchmark", "", out["note"], "",
          "| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['dataset']} | {r['steps']} | {r['path']} | {r['seconds']} | {r['seconds_per_step']} | "
                  f"{r['rss_growth_MB']} | {r.get('python_peak_MB', '')} |")
    Path(args.out, "replay_benchmark.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", default=None, help="frozen research price cache (development rows are used)")
    parser.add_argument("--out", default="out")
    parser.add_argument("--cutoffs", type=int, default=50)
    parser.add_argument("--days", type=int, default=500)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--indicators", default=None, help=argparse.SUPPRESS)   # tests: a pure-pandas stand-in
    args = parser.parse_args(argv)
    if args.indicators:
        global INDICATORS
        INDICATORS = args.indicators
    if args.benchmark:
        return benchmark(args)
    return certify(args)


if __name__ == "__main__":
    sys.exit(main())
