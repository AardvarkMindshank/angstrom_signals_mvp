"""
Live run of every candle-based Signal Library signal on real Yahoo candles (CI; nothing is stored).
Exits non-zero if any signal errors. Stored-data signals (flows, derivatives) need Supabase and are
covered by unit tests instead.

    python signal_library_live.py --out out
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import signal_inspector
import signal_library as sl

ASSETS = (("crypto", "bitcoin"), ("crypto", "ethereum"), ("equity", "AAPL"), ("equity", "SPY"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)
    md = ["# Signal Library live run (Yahoo candles)", ""]
    record, errors = {}, 0
    for kind, asset in ASSETS:
        ctx = sl.DataContext(kind, asset)
        md += [f"## {asset}", "", "| Signal | TF | Status | Reading | Available |", "|---|---|---|---|---|"]
        for tf in ("15m", "1h", "4h", "1D", "1W"):
            refs = [r for r in signal_inspector.asset_refs(kind, tf) if r.timeframe == tf and not r.id.startswith("positioning.")]
            t0 = time.perf_counter()
            results = sl.evaluate(refs, ctx)
            took = time.perf_counter() - t0
            for r in results.values():
                errors += r.status == "error"
                md.append(f"| {r.ref['id']} | {tf} | {r.status} | {signal_inspector.summary(r)[:140]} | {r.available_at or ''} |")
                record[f"{asset}|{tf}|{r.ref['id']}"] = r.as_dict()
            md.append(f"| _{len(results)} signals in {took:.2f}s (includes candle fetch)_ | | | | |")
        md.append("")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    Path(args.out, "signal_library_live.json").write_text(json.dumps(record, indent=1, default=str))
    Path(args.out, "signal_library_live.md").write_text("\n".join(md) + f"\nErrors: {errors}\n")
    print("\n".join(md), f"\nErrors: {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
