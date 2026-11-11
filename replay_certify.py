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
    out += cf.synthetic_sentiment(seed=9)
    out += cf.synthetic_options(seed=11)
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
        if _compared(committed) != _compared(record):
            print("The committed certification record differs from this run: re-certify and commit "
                  "signal_library/certification.json (out/certification.json).")
            return 1
        print("Committed certification record matches this run.")
    return 0


INFORMATIONAL = ("slice_reason",)   # explanations for people: which field failed first can differ by machine


def _compared(record: dict) -> dict:
    """What --check compares (point_in_time.md §13): the record without its informational fields."""
    out = {k: record.get(k) for k in COMPARED}
    out["signals"] = {key: {tf: {f: v for f, v in entry.items() if f not in INFORMATIONAL}
                            for tf, entry in (tfs or {}).items()}
                      for key, tfs in (out.get("signals") or {}).items()}
    return out


def report(record: dict, seconds: float) -> str:
    lines = [f"# Replay certification (suite v{record['suite_version']})", "",
             f"Code hash {record['code_sha256'][:12]}; {len(record['datasets'])} datasets; at least "
             f"{record['cutoffs_per_dataset_minimum']} cutoffs per dataset; {seconds / 60:.1f} minutes.", "",
             "| Signal | Timeframe | Algorithm | Slice shortcut | Cutoffs | Checks (reference/poison/cache/timestamps) | Readings | Reason |",
             "|---|---|---|---|---|---|---|---|"]
    certified = total = 0
    for key, tfs in sorted(record["signals"].items()):
        for tf, e in sorted(tfs.items(), key=lambda x: ["15m", "30m", "1h", "4h", "12h", "1D", "1W"].index(x[0])):
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
    # Stage 3: the example Set replayed at consecutive daily cutoffs (two Groups, standalone items, live-only market
    # item skipped), exact path.
    import signal_groups as sg
    import signal_groups_inspector as gi

    set_rows = []
    ds = data[0]
    doc = gi.example_set()
    for steps in (30, 90):
        cutoffs = [pd.Timestamp(int(x), tz="UTC") for x in ds.histories["1D"].ends[-steps - 1:-1]]
        engine.clear_cache()
        gc.collect()
        before = rss_mb()
        tracemalloc.start()
        t0 = time.perf_counter()
        run = ReplayRun(CERTIFICATION, ds.candles, indicators=cf._INDICATORS["fn"])
        labels = {}
        for t in cutoffs:
            r = sg.evaluate_set(doc, run.context(ds.kind, ds.asset_id, t), data_mode="point_in_time",
                                market_context=lambda scope, t=t: run.context("market", scope.split(":")[1], t))
            labels[r["completeness"]["label"]] = labels.get(r["completeness"]["label"], 0) + 1
        secs = time.perf_counter() - t0
        peak = tracemalloc.get_traced_memory()[1] / 2**20
        tracemalloc.stop()
        del run
        gc.collect()
        set_rows.append({"dataset": ds.name, "steps": steps, "seconds": round(secs, 2),
                         "seconds_per_step": round(secs / steps, 3), "python_peak_MB": round(peak, 1),
                         "rss_growth_MB": round(rss_mb() - before, 1), "completeness": labels})
    out = {"set_rows": set_rows, "signals_per_step": len(refs), "note": "Every 1D candle signal incl. multi-timeframe alignment, per step; "
           "certification mode (no certification lookup), real indicators.", "rows": rows,
           "rss_end_MB": round(rss_mb(), 1)}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "replay_benchmark.json").write_text(json.dumps(out, indent=1))
    md = ["# Replay benchmark", "", out["note"], "",
          "| Dataset | Steps | Path | Seconds | s/step | RSS growth MB | Python peak MB |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['dataset']} | {r['steps']} | {r['path']} | {r['seconds']} | {r['seconds_per_step']} | "
                  f"{r['rss_growth_MB']} | {r.get('python_peak_MB', '')} |")
    md += ["", "## Multi-Timeframe Analysis Set at consecutive daily cutoffs (exact path, allocation traced)", "",
           "| Dataset | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Completeness |",
           "|---|---|---|---|---|---|---|"]
    for r in set_rows:
        md.append(f"| {r['dataset']} | {r['steps']} | {r['seconds']} | {r['seconds_per_step']} | {r['python_peak_MB']} | "
                  f"{r['rss_growth_MB']} | {r['completeness']} |")
    Path(args.out, "replay_benchmark.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


def optimise(args) -> int:
    """Stage 5: the example Set at consecutive daily cutoffs with (A) the exact path, (B) reuse of unchanged
    timeframe frames, (C) the slice shortcut for slice-certified signals only, (D) both. Every step of B, C and D is
    compared with A (whole Set result, administrative fields left out)."""
    import pandas as pd

    import signal_groups as sg
    import signal_groups_inspector as gi
    from signal_library import certify as cf, engine
    from signal_library.replay import CERTIFICATION, ReplayRun

    cf._INDICATORS.update(path=INDICATORS, fn=cf._indicators(INDICATORS))
    committed = json.loads(RECORD.read_text()) if RECORD.exists() else {"signals": {}}
    allow = {(k, tf) for k, tfs in committed["signals"].items() for tf, e in tfs.items() if e.get("slice_equivalent")}
    doc = gi.example_set()
    data = [cf.synthetic_crypto(days=args.days, seed=11), cf.synthetic_equity(days=args.days, seed=23)]
    if args.prices and Path(args.prices, "manifest.json").exists():
        data += cf.development_datasets(args.prices, tickers=("BTC-USD",))
    admin = {"evaluated_at", "computed_at"}

    def strip(v):
        if isinstance(v, dict):
            return {k: strip(x) for k, x in v.items() if k not in admin}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v

    variants = {"A exact": {}, "B reuse frames": {"reuse_frames": True},
                "C certified slicing": {"shortcut": True, "slice_allow": allow},
                "D slicing + reuse": {"shortcut": True, "slice_allow": allow, "reuse_frames": True}}
    rows = []
    for ds in data:
        steps = args.steps
        cutoffs = [pd.Timestamp(int(x), tz="UTC") for x in ds.histories["1D"].ends[-steps - 1:-1]]
        reference = None
        for name, options in variants.items():
            engine.clear_cache()
            gc.collect()
            before = rss_mb()
            tracemalloc.start()
            t0 = time.perf_counter()
            run = ReplayRun(CERTIFICATION, ds.candles, indicators=cf._INDICATORS["fn"], **options)
            out = []
            for t in cutoffs:
                r = sg.evaluate_set(doc, run.context(ds.kind, ds.asset_id, t), data_mode="point_in_time",
                                    market_context=lambda scope, t=t: run.context("market", scope.split(":")[1], t))
                out.append(json.dumps(strip(r), sort_keys=True, default=str))
            secs = time.perf_counter() - t0
            peak = tracemalloc.get_traced_memory()[1] / 2**20
            tracemalloc.stop()
            if reference is None:
                reference = out
            diffs = [cutoffs[i].isoformat() for i, (a, b) in enumerate(zip(reference, out)) if a != b]
            rows.append({"dataset": ds.name, "variant": name, "steps": steps, "seconds": round(secs, 1),
                         "seconds_per_step": round(secs / steps, 3), "python_peak_MB": round(peak, 1),
                         "rss_growth_MB": round(rss_mb() - before, 1), "frame_reuses": run.frame_reuses,
                         "steps_differing_from_exact": len(diffs), "first_difference": diffs[:1]})
            del run
            gc.collect()
    result = {"slice_allowed_pairs": len(allow), "rows": rows,
              "note": "Example Set at consecutive daily cutoffs; every variant compared step by step with the exact path."}
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "replay_optimise.json").write_text(json.dumps(result, indent=1))
    md = ["# Replay optimisation (stage 5)", "", result["note"], f"Slice shortcut allowed for {len(allow)} certified "
          "signal/timeframe pairs (from the committed certification record).", "",
          "| Dataset | Variant | Steps | Seconds | s/step | Python peak MB | RSS growth MB | Frames reused | "
          "Steps differing from exact |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['dataset']} | {r['variant']} | {r['steps']} | {r['seconds']} | {r['seconds_per_step']} | "
                  f"{r['python_peak_MB']} | {r['rss_growth_MB']} | {r['frame_reuses']} | "
                  f"{r['steps_differing_from_exact']} {' '.join(r['first_difference'])} |")
    Path(args.out, "replay_optimise.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 1 if any(r["steps_differing_from_exact"] for r in rows) else 0


def parity(args) -> int:
    """Library completion: the Trend/Stretch/Flow starter Groups against signals_v2 on identical inputs (real
    indicators, synthetic and frozen development data), at many cutoffs. Fails on any difference."""
    import pandas as pd

    import signal_groups as sg
    import signals_v2 as v2
    from scoring import calculate_indicators
    from signal_library import DataContext, certify as cf, engine

    data = [("synthetic-crypto", "crypto", cf.synthetic_crypto(days=args.days, seed=11).histories["1D"].raw),
            ("synthetic-share", "equity", cf.synthetic_equity(days=args.days, seed=23).histories["1D"].raw)]
    if args.prices and Path(args.prices, "manifest.json").exists():
        for ds in cf.development_datasets(args.prices):
            data.append((ds.name, ds.kind, ds.histories["1D"].raw))
    starters = {"trend": "starter:trend", "stretch": "starter:stretch", "flow": "starter:flow"}
    rows, failures = [], []
    for name, kind, raw in data:
        frame = calculate_indicators(raw.copy())
        positions = sorted(set(list(range(15, len(frame), max(1, len(frame) // 60))) + [len(frame)]))
        checked = 0
        for pos in positions:
            f = frame.iloc[:pos]
            legacy = v2.score(f, "crypto" if kind == "crypto" else "stock", f.index[-1] + pd.Timedelta(days=3))
            engine.clear_cache()
            loaded = {"frame": f.assign(forming=False), "session": None, "source": "parity"}
            ctx = DataContext(kind, "x", candle_loader=lambda k, a, tf, loaded=loaded: loaded,
                              now=f.index[-1] + pd.Timedelta(days=3))
            for cluster, alias in starters.items():
                r = sg.evaluate_group(sg.starter(alias), ctx)
                value = (r["score"] or {}).get("value")
                observed = sum(1 for m in r["members"] if m.get("state") == "observed")
                if legacy["status"] != "ok":
                    ok = value is None
                else:
                    c = legacy["clusters"][cluster]
                    ok = ([observed, len(r["members"])] == c["coverage"] and (value is None) == (c["value"] is None)
                          and (value is None or (abs(value - c["value"]) < 1e-9 and v2.percent(value) == c["percent"])))
                checked += 1
                if not ok:
                    failures.append(f"{name} bar {pos} {cluster}: group {value} vs v2 "
                                    f"{legacy.get('clusters', {}).get(cluster)}")
        rows.append((name, len(positions), checked))
    md = ["# Trend / Stretch / Flow as Groups: parity with signals_v2 (identical inputs, real indicators)", "",
          "| Data | Cutoffs | Comparisons |", "|---|---|---|"] + [f"| {a} | {b} | {c} |" for a, b, c in rows]
    md += ["", f"Differences: {len(failures)} (tolerance 1e-9, identical displayed percent and coverage)"]
    md += [f"- {x}" for x in failures[:20]]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "parity.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 1 if failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", default=None, help="frozen research price cache (development rows are used)")
    parser.add_argument("--out", default="out")
    parser.add_argument("--cutoffs", type=int, default=50)
    parser.add_argument("--days", type=int, default=500)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--optimise", action="store_true", help="stage 5: shortcuts compared with the exact path")
    parser.add_argument("--parity", action="store_true", help="Trend/Stretch/Flow Groups vs signals_v2")
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--indicators", default=None, help=argparse.SUPPRESS)   # tests: a pure-pandas stand-in
    args = parser.parse_args(argv)
    if args.indicators:
        global INDICATORS
        INDICATORS = args.indicators
    if args.benchmark:
        return benchmark(args)
    if args.optimise:
        return optimise(args)
    if args.parity:
        return parity(args)
    return certify(args)


if __name__ == "__main__":
    sys.exit(main())
