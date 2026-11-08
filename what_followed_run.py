"""
Run "What followed" for the provided Sets on the saved daily prices (reports branch, data/prices), before the
protected hold-out. Two steps, so the slow part can be split across machines:

  python what_followed_run.py answers <prices> <out> --shard i/n [--sets k1,k2] [--limit N]
      the daily Yes / No / Unknown of each Set on each asset (out/answers/<set>/<asset>.json)
  python what_followed_run.py study <prices> <out>
      outcomes, comparable days and the tests (out/what_followed.json), plus a plain summary on stdout
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import what_followed as wf  # noqa: E402

START = "2014-09-17"           # the first day Yahoo has Bitcoin: every asset is studied over the same years
CUT = pd.Timestamp("2024-10-29")
LIBRARY = ["demo:pullback", "demo:rally", "demo:alignment", "demo:breakout", "demo:squeeze", "demo:range_low",
           "demo:near_support", "demo:overextended", "demo:btc_filter"]


def symbols(prices: str) -> list[str]:
    return sorted(p.name[:-7] for p in Path(prices).glob("*.csv.gz"))


def kind_of(symbol: str) -> str:
    return "crypto" if symbol.endswith("-USD") else "equity"


def raw(prices: str, symbol: str) -> pd.DataFrame:
    d = pd.read_csv(f"{prices}/{symbol}.csv.gz", parse_dates=["date"])
    d = d[d["date"] <= CUT]                         # nothing from the hold-out is kept past this line
    d = d.set_index(pd.DatetimeIndex(d["date"]).tz_localize("UTC"))[["open", "high", "low", "close", "volume"]]
    return d[~d.index.duplicated(keep="last")].sort_index()


def answers_step(args) -> int:
    import prism
    import set_history as sh
    from scoring import calculate_indicators

    docs = prism.demo_sets()
    keys = [k for k in (args.sets.split(",") if args.sets else LIBRARY) if wf.set_type(k) != "filter"]
    i, n = (int(x) for x in args.shard.split("/"))
    mine = [s for j, s in enumerate(symbols(args.prices)) if j % n == i]
    if args.limit:
        mine = mine[: args.limit]
    for symbol in mine:
        t0 = time.time()
        frame = calculate_indicators(raw(args.prices, symbol))
        for key in keys:
            out = Path(args.out) / "answers" / key.replace(":", "_") / f"{symbol}.json"
            if out.exists():
                continue
            t1 = time.time()
            days = sh.daily_answers(docs[key], frame, kind_of(symbol), symbol, start=START)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"set": key, "hash": _hash(docs[key]), "symbol": symbol,
                                       "spans": sh.spans(days)}))
            print(f"{symbol} {key}: {len(days)} days in {time.time() - t1:.0f}s", flush=True)
        print(f"{symbol} done in {time.time() - t0:.0f}s", flush=True)
    return 0


def _hash(doc: dict) -> str:
    from column_answers import def_hash

    return def_hash(doc)


def _answers_series(spans: list) -> pd.Series:
    parts = [pd.Series(a, index=pd.date_range(f, l, freq="D")) for f, l, a in spans]
    return pd.concat(parts) if parts else pd.Series(dtype=object)


def study_step(args) -> int:
    import prism

    docs = prism.demo_sets()
    tables, per_set, hashes = {}, {}, {}
    for key in LIBRARY:
        folder = Path(args.out) / "answers" / key.replace(":", "_")
        parts = []
        for f in sorted(folder.glob("*.json")) if folder.exists() else []:
            rec = json.loads(f.read_text())
            symbol = rec["symbol"]
            hashes[key] = rec["hash"]
            if symbol not in tables:
                t = wf.outcomes(raw(args.prices, symbol))
                t.index = t.index.tz_localize(None).normalize()
                tables[symbol] = t
            answers = _answers_series(rec["spans"])
            answers.index = answers.index.normalize()
            rows = wf.differences(answers, tables[symbol])
            if rows.empty:
                continue
            rows["asset"], rows["kind"] = symbol, kind_of(symbol)
            parts.append(rows)
        per_set[key] = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    result = wf.study(per_set, {k: wf.set_type(k) for k in LIBRARY})
    for key, s in result["sets"].items():
        s["name"] = docs[key]["name"]
        s["hash"] = hashes.get(key, _hash(docs[key]))
    result["through"] = "2024-10-29"
    result["start"] = START
    Path(args.out, "what_followed.json").write_text(json.dumps(result, indent=1, default=float))
    for key, s in result["sets"].items():
        print(f"\n{s['name']}: {s['verdict'] or s.get('note')}")
        if s.get("episodes"):
            print(f"  {s['episodes']} episodes in {s['weeks']} weeks, {s['assets']} assets "
                  f"({s['coins']} coin, {s['shares']} share episodes); top {s['top_assets']}")
            print("  " + ", ".join(f"{k} {v:.3f}" for k, v in s["plain"].items()))
            for m, t in s["tests"].items():
                print(f"  {m}: estimate {t['estimate']}, 95% {t['ci95']}, p {t['p_two_sided']}, Holm "
                      f"{t['holm_passed']}, consistency {t['consistency']}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["answers", "study"])
    p.add_argument("prices")
    p.add_argument("out")
    p.add_argument("--shard", default="0/1")
    p.add_argument("--sets", default="")
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args(argv)
    return answers_step(args) if args.step == "answers" else study_step(args)


if __name__ == "__main__":
    raise SystemExit(main())
