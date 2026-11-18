"""
Run Soundings on the saved daily prices (reports branch, data/prices), before the protected hold-out.

  python soundings_run.py table <prices> <out> [--shard i/n] [--coins BTC-USD,ETH-USD]
      the readings table for each coin: out/readings/<coin>.csv.gz (every reading at every daily close)
  python soundings_run.py mine <prices> <out>
      moves, the search (to the end of 2022) and the confirmation (2023 to 29 Oct 2024): out/soundings.json and a
      plain summary on stdout
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import soundings as so  # noqa: E402
import what_followed_run as wr  # noqa: E402


def coins(prices: str, only: str = "") -> list[str]:
    found = [s for s in wr.symbols(prices) if s.endswith("-USD")]
    return [s for s in found if not only or s in only.split(",")]


def table_step(args) -> int:
    from scoring import calculate_indicators

    i, n = (int(x) for x in args.shard.split("/"))
    mine = [s for j, s in enumerate(coins(args.prices, args.coins)) if j % n == i]
    folder = Path(args.out) / "readings"
    folder.mkdir(parents=True, exist_ok=True)
    for sym in mine:
        t0 = time.time()
        frame = calculate_indicators(wr.raw(args.prices, sym))
        table = so.readings_table(frame, "crypto", sym)
        table.to_csv(folder / f"{sym}.csv.gz", index_label="date")
        print(f"{sym}: {len(table)} days in {time.time() - t0:.0f}s", flush=True)
    return 0


def _load(prices: str, out: str) -> dict:
    per = {}
    for f in sorted((Path(out) / "readings").glob("*.csv.gz")):
        sym = f.name[:-7]
        table = pd.read_csv(f, index_col="date", parse_dates=["date"])
        if table.index.tz is None:
            table.index = table.index.tz_localize("UTC")
        per[sym] = (table, so.moves(wr.raw(prices, sym)))
    return per


def _short(r: dict) -> dict:
    keep = ("condition", "kind", "days", "coins", "rate", "usual", "lift", "p", "coins_up", "coins_read",
            "fdr_pass", "search_pass")
    return {k: r.get(k) for k in keep}


def mine_step(args) -> int:
    per = _load(args.prices, args.out)
    report = {"settings": {"rise": f"+{so.UP_ATR} typical moves within {so.WINDOW} daily candles, before -{so.STOP_ATR}",
                           "search": f"to {so.SEARCH_END.date()}", "confirm": f"{so.SEARCH_END.date()} to {so.CUT.date()}",
                           "coins": sorted(per), "fdr": so.FDR, "min_lift": so.MIN_LIFT, "min_days": so.MIN_DAYS,
                           "min_coins": so.MIN_COINS},
              "targets": {}}
    lines = []
    for target in ("rise", "fall"):
        t0 = time.time()
        search_p = so.panel(per, target, end=so.SEARCH_END)
        confirm_p = so.panel(per, target, start=so.SEARCH_END + pd.Timedelta(days=1))
        found = so.search(search_p, target, runs=args.runs, pairs=not args.singles)
        survivors = sorted([r for r in found if r["search_pass"]], key=lambda r: -(r.get("lift") or 0))
        checked = so.confirm(confirm_p, survivors, target)
        tested = len([r for r in found if not r.get("screened_out")])
        report["targets"][target] = {
            "base_rate_search": float(search_p[target].mean()), "base_rate_confirm": float(confirm_p[target].mean()),
            "days_search": int(len(search_p)), "days_confirm": int(len(confirm_p)),
            "looked_at": len(found), "tested": tested, "search_survivors": len(survivors),
            "results": [{**_short(r), "confirm": r["confirm"], "confirmed": r["confirmed"], "verdict": r["verdict"]}
                        for r in checked],
            "top_search": [_short(r) for r in sorted(found, key=lambda r: -(r.get("lift") or 0))
                           if not r.get("screened_out") and r.get("days", 0) >= so.MIN_DAYS][:40],
        }
        lines.append(f"\n{target.upper()}S: usual rate {search_p[target].mean():.1%} (search), "
                     f"{confirm_p[target].mean():.1%} (confirm); looked at {len(found)}, tested {tested}, "
                     f"{len(survivors)} passed the search ({time.time() - t0:.0f}s)")
        for r in checked:
            c = r["confirm"]
            lines.append(f"  {r['verdict']:<13} {' + '.join(r['condition'])}: lift {r['lift']:.2f} on {r['days']} days "
                         f"-> {c.get('lift') or 0:.2f} on {c.get('days', 0)} days (p {c.get('p') or 1:.3f}, "
                         f"{c.get('coins_up', 0)}/{c.get('coins_read', 0)} coins)")
    Path(args.out, "soundings.json").write_text(json.dumps(report, indent=1, default=str))
    print("\n".join(lines))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["table", "mine"])
    ap.add_argument("prices")
    ap.add_argument("out")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--coins", default="")
    ap.add_argument("--runs", type=int, default=so.RUNS_SEARCH)
    ap.add_argument("--singles", action="store_true", help="single conditions only (no pairs)")
    args = ap.parse_args()
    return table_step(args) if args.step == "table" else mine_step(args)


if __name__ == "__main__":
    sys.exit(main())
