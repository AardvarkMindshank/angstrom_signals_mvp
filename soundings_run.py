"""
Run Soundings on the saved daily prices (reports branch, data/prices), before the protected hold-out.

  python soundings_run.py table <prices> <out> [--shard i/n] [--coins BTC-USD,ETH-USD]
      the readings table for each coin: out/readings/<coin>.csv.gz (every reading at every daily close)
  python soundings_run.py grid <prices> <out>
      the chart's data from the readings and the results: out/soundings_grid.json.gz
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
    per, tide_cache = {}, {}
    for f in sorted((Path(out) / "readings").glob("*.csv.gz")):
        sym = f.name[:-7]
        table = pd.read_csv(f, index_col="date", parse_dates=["date"])
        if table.index.tz is None:
            table.index = table.index.tz_localize("UTC")
        table = so.with_tides(table, "crypto", tide_cache)
        per[sym] = (table, so.moves(wr.raw(prices, sym)))
    return per


def _short(r: dict) -> dict:
    keep = ("condition", "kind", "days", "coins", "rate", "usual", "lift", "p", "coins_up", "coins_read",
            "fdr_pass", "search_pass")
    return {k: r.get(k) for k in keep}


def mine_step(args) -> int:
    per = _load(args.prices, args.out)
    report = {"settings": {"rise": f"+{so.UP_ATR} typical moves within {so.WINDOW} daily candles, before -{so.STOP_ATR}",
                           "search": f"to {so.SEARCH_END.date()}", "confirm": f"{(so.SEARCH_END + pd.Timedelta(days=1)).date()} to {so.CUT.date()}",
                           "coins": sorted(per), "fdr": so.FDR, "min_lift": so.MIN_LIFT, "min_days": so.MIN_DAYS,
                           "min_coins": so.MIN_COINS,
                           "universe": "wide" if Path(args.prices, "manifest.json").exists() and json.loads(
                               Path(args.prices, "manifest.json").read_text()).get("source", "").startswith(
                               "data.binance.vision") else "research"},
              "targets": {}}
    lines = []
    confirm_panels = {k: so.panel(per, k, start=so.SEARCH_END + pd.Timedelta(days=1)) for k in ("rise", "fall")}
    whole_panels = {k: so.panel(per, k) for k in ("rise", "fall")}
    for target in ("rise", "fall"):
        t0 = time.time()
        search_p = so.panel(per, target, end=so.SEARCH_END)
        confirm_p = confirm_panels[target]
        found = so.search(search_p, target, runs=args.runs, pairs=not args.singles)
        survivors = sorted([r for r in found if r["search_pass"]], key=lambda r: -(r.get("lift") or 0))
        leads = so.themes(survivors)
        checked = so.confirm(confirm_p, leads, target)
        so.opposite(confirm_panels["fall" if target == "rise" else "rise"], checked, "fall" if target == "rise" else "rise")
        so.tide_split(whole_panels[target], checked, target)
        tested = len([r for r in found if not r.get("screened_out")])
        tides_base = {st: {"days": int((whole_panels[target].get(f"Tide: {st}", pd.Series(dtype=float)) == 1).sum()),
                           "rate": float(whole_panels[target].loc[whole_panels[target][f"Tide: {st}"] == 1, target].mean())
                           if f"Tide: {st}" in whole_panels[target] else None}
                      for st in so.TIDE_STATES}
        report["targets"][target] = {
            "tide_base": tides_base,
            "base_rate_search": float(search_p[target].mean()), "base_rate_confirm": float(confirm_p[target].mean()),
            "days_search": int(len(search_p)), "days_confirm": int(len(confirm_p)),
            "looked_at": len(found), "tested": tested, "search_survivors": len(survivors), "themes": len(leads),
            "results": [{**_short(r), "confirm": r["confirm"], "opposite": r.get("opposite"), "confirmed": r["confirmed"],
                         "verdict": r["verdict"], "theme": r.get("theme", [])[:12], "theme_size": len(r.get("theme", [])),
                         "tide_split": r.get("tide_split")}
                        for r in checked],
            "top_search": [_short(r) for r in sorted(found, key=lambda r: -(r.get("lift") or 0))
                           if not r.get("screened_out") and r.get("days", 0) >= so.MIN_DAYS][:40],
        }
        lines.append(f"\n{target.upper()}S: usual rate {search_p[target].mean():.1%} (search), "
                     f"{confirm_p[target].mean():.1%} (confirm); looked at {len(found)}, tested {tested}, "
                     f"{len(survivors)} passed the search, in {len(leads)} themes ({time.time() - t0:.0f}s)")
        for r in sorted(checked, key=lambda r: (r["verdict"] != "survivor", -((r["confirm"].get("lift")) or 0))):
            c = r["confirm"]
            lines.append(f"  {r['verdict']:<13} {' + '.join(r['condition'])}: lift {r['lift']:.2f} on {r['days']} days "
                         f"-> {c.get('lift') or 0:.2f} on {c.get('days', 0)} days (p {c.get('p') or 1:.3f}, "
                         f"{c.get('coins_up', 0)}/{c.get('coins_read', 0)} coins)")
    Path(args.out, "soundings.json").write_text(json.dumps(report, indent=1, default=str))
    print("\n".join(lines))
    return 0


def grid_step(args) -> int:
    """The chart's data (soundings_view: price on top, a row per result below): for each coin, every daily close to
    the cut with its price, whether a rise or fall followed, and each condition named in the results (1, 0, or . when
    the reading was missing). Written to out/soundings_grid.json.gz."""
    import gzip

    report = json.loads(Path(args.out, "soundings.json").read_text())
    names = set()
    for part in (report.get("targets") or {}).values():
        for r in part.get("results") or []:
            names.update(r["condition"])
    names.update(f"Tide: {st}" for st in so.TIDE_STATES)
    names = sorted(names)
    coins = {}
    tide_cache = {}
    for f in sorted((Path(args.out) / "readings").glob("*.csv.gz")):
        sym = f.name[:-7]
        table = pd.read_csv(f, index_col="date", parse_dates=["date"])
        if table.index.tz is None:
            table.index = table.index.tz_localize("UTC")
        table = so.with_tides(table, "crypto", tide_cache)
        raw = wr.raw(args.prices, sym)
        mv = so.moves(raw)
        conds = so.conditions(table)
        days = table.index[table.index <= so.CUT.tz_localize("UTC") if so.CUT.tzinfo is None else so.CUT]
        close = raw["close"].reindex(days)
        mv = mv.reindex(days)

        def code(series):
            v = series.reindex(days)
            return "".join("." if pd.isna(x) else ("1" if x == 1 else "0") for x in v)

        coins[sym] = {
            "start": days[0].strftime("%Y-%m-%d"), "days": len(days),
            # stopped trading before the cut: kept in the testing (no survivorship bias), left out of the chart
            "stopped": bool(raw.index[-1].tz_localize(None) < so.CUT - pd.Timedelta(days=5)),
            "close": [None if pd.isna(x) else float(f"{x:.6g}") for x in close],
            "rise": code(mv["rise"]), "fall": code(mv["fall"]),
            "rows": {n: code(conds[n]) for n in names if n in conds},
        }
        print(f"{sym}: {len(days)} days, {len(coins[sym]['rows'])} rows", flush=True)
    with gzip.open(Path(args.out, "soundings_grid.json.gz"), "wt") as fh:
        json.dump({"cut": str(so.CUT.date()), "coins": coins}, fh, separators=(",", ":"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["table", "mine", "grid"])
    ap.add_argument("prices")
    ap.add_argument("out")
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--coins", default="")
    ap.add_argument("--runs", type=int, default=so.RUNS_SEARCH)
    ap.add_argument("--singles", action="store_true", help="single conditions only (no pairs)")
    args = ap.parse_args()
    return {"table": table_step, "mine": mine_step, "grid": grid_step}[args.step](args)


if __name__ == "__main__":
    sys.exit(main())
