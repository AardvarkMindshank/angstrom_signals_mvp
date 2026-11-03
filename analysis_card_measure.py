"""
Memory and time for the selected-asset Analysis card (CI; nothing is stored).

Runs the real card evaluation (analysis_card.evaluate: the Multi-Timeframe Analysis Set through the real
Groups/Sets evaluator, with the real candle loader and indicators) on live Yahoo candles, one asset at a time,
the way the card runs in the app. No database: stored-data readings (Bitcoin ETF flows, derivatives) show as
missing, so this measures the candle-based work, which is nearly all of it.

Reports, per step: wall time, process memory (RSS) before and after, Python's peak allocation during the step,
and the size of the result the card keeps in the session.

    python analysis_card_measure.py --out out            # live Yahoo candles
    python analysis_card_measure.py --out out --synthetic  # made-up candles of production size (no network)
"""

from __future__ import annotations

import argparse
import gc
import json
import time
import tracemalloc
from pathlib import Path


def rss_mb() -> float:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class NoDb:
    def table(self, name):
        raise RuntimeError("no database in this measurement")


SIZES = {"15m": ("15min", 2900), "1h": ("1h", 8760), "4h": ("4h", 2190), "1D": ("1D", 365), "1W": ("7D", 600)}


def synthetic_load_candles(kind, asset, tf, rng=None, **_):
    import numpy as np
    import pandas as pd

    freq, n = SIZES[tf]
    gen = np.random.default_rng(abs(hash((asset, tf))) % 2**32)
    close = 100 * np.exp(np.cumsum(gen.normal(0, 0.01, n)))
    index = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("15min"), periods=n, freq=freq)
    df = pd.DataFrame({"open": close * (1 + gen.normal(0, .002, n)), "high": close * 1.01, "low": close * .99,
                       "close": close, "volume": gen.integers(100, 10000, n).astype(float)}, index=index)
    df["forming"] = False
    df.iloc[-1, df.columns.get_loc("forming")] = True
    return {"candles": df, "session": None, "source": "synthetic"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out")
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args(argv)

    start = rss_mb()
    import pandas  # noqa: F401  (the app has these loaded already)
    import chart_data
    import scoring
    modules_only = rss_mb()
    if args.synthetic:
        chart_data.load_candles = synthetic_load_candles
    # What the dashboard has already done before anyone presses Analyse: the indicator library and the Yahoo
    # client are loaded and in use, and the chart has loaded daily candles for the selected asset.
    try:
        import data_fetchers  # noqa: F401
        daily = chart_data.load_candles("crypto", "bitcoin", "1D", "1Y")
        if daily.get("candles") is not None:
            scoring.calculate_indicators(daily["candles"][["open", "high", "low", "close", "volume"]])
    except Exception as exc:
        print("warm-up skipped:", exc)
    chart_data.CACHE.clear()
    gc.collect()
    app_base = rss_mb()
    import analysis_card as ac
    from signal_library import engine

    after_import = rss_mb()
    doc = ac.example_set()
    steps = []

    def step(label, kind, asset, peak=False):
        gc.collect()
        before = rss_mb()
        if peak:
            tracemalloc.start()
        t0 = time.perf_counter()
        result = ac.evaluate(doc, kind, asset, NoDb())
        secs = time.perf_counter() - t0
        peak_mb = None
        if peak:
            peak_mb = tracemalloc.get_traced_memory()[1] / 2**20
            tracemalloc.stop()
        gc.collect()
        groups = {g["key"]: g["result"]["status"] for g in result["groups"]}
        unavailable = sorted({k for g in result["groups"] for k in (g["result"].get("diagnostics") or {})
                              .get("timing", {}).get("unavailable", [])})
        steps.append({"step": label, "asset": f"{kind}:{asset}", "seconds": round(secs, 2),
                      "rss_before_MB": round(before, 1), "rss_after_MB": round(rss_mb(), 1),
                      "rss_change_MB": round(rss_mb() - before, 1),
                      "python_peak_MB": None if peak_mb is None else round(peak_mb, 1),
                      "kept_result_KB": round(len(json.dumps(result, default=str)) / 1024, 1),
                      "groups": groups, "unavailable": unavailable})

    step("first evaluation (cold: candles fetched)", "crypto", "bitcoin")
    step("same asset again (cached)", "crypto", "bitcoin")
    step("second coin (cold)", "crypto", "ethereum")
    step("a share (cold)", "equity", "AAPL")
    step("third coin (cold)", "crypto", "solana")
    # Peak Python allocation for one cold evaluation (tracemalloc slows it down, so timed separately above).
    engine.clear_cache()
    chart_data.CACHE.clear()
    step("cold again with allocation tracing", "crypto", "bitcoin", peak=True)

    summary = {
        "source": "synthetic candles (production sizes)" if args.synthetic else "live Yahoo candles",
        "rss_at_start_MB": round(start, 1),
        "rss_with_pandas_and_app_modules_MB": round(modules_only, 1),
        "rss_like_the_running_dashboard_MB": round(app_base, 1),
        "dashboard_warm_up_MB": round(app_base - modules_only, 1),
        "rss_after_importing_card_MB": round(after_import, 1),
        "import_cost_MB": round(after_import - app_base, 1),
        "rss_after_all_steps_MB": round(rss_mb(), 1),
        "growth_over_all_steps_MB": round(rss_mb() - after_import, 1),
        "engine_cache_entries": len(engine._CACHE),
        "engine_cache_limit": engine.CACHE_SIZE,
        "candle_cache_entries": len(chart_data.CACHE.items),
        "candle_cache_limit": chart_data.CACHE.size,
        "steps": steps,
    }
    md = [f"# Analysis card: memory and time ({summary['source']})", "",
          f"- Process memory with pandas and the app's data modules loaded: {summary['rss_with_pandas_and_app_modules_MB']} MB",
          f"- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's "
          f"daily candles): +{summary['dashboard_warm_up_MB']} MB, giving {summary['rss_like_the_running_dashboard_MB']} MB",
          f"- Importing the card and the Groups/Sets code adds: {summary['import_cost_MB']} MB",
          f"- Growth over all {len(steps)} evaluations below: {summary['growth_over_all_steps_MB']} MB "
          f"(caches are bounded: signal results {summary['engine_cache_entries']}/{summary['engine_cache_limit']}, "
          f"candle sets {summary['candle_cache_entries']}/{summary['candle_cache_limit']})", "",
          "| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |",
          "|---|---|---|---|---|---|---|---|"]
    for s in steps:
        md.append(f"| {s['step']} | {s['asset']} | {s['seconds']} | {s['rss_change_MB']} | {s['python_peak_MB'] or ''} | "
                  f"{s['kept_result_KB']} | {', '.join(f'{k}: {v}' for k, v in s['groups'].items())} | "
                  f"{', '.join(s['unavailable'])} |")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    name = "analysis_card_measure" + ("_synthetic" if args.synthetic else "")
    Path(args.out, f"{name}.json").write_text(json.dumps(summary, indent=1))
    Path(args.out, f"{name}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
