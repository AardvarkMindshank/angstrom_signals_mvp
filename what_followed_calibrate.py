"""Calibration of the What followed tests on parts (coins, equities): do they "find" differences on random days no
more often than they should?

Random "Sets" are made that know nothing about prices: Yes runs switched on at random. On such Sets every true
difference is zero, so a sound test passes p <= 0.05 about 5% of the time (and the coins-versus-equities comparison
the same). Two kinds of random Set:

- independent: each asset gets its own random Yes days;
- shared: one random calendar of Yes days for every asset at once, like a Set pinned to Bitcoin, which is the hard
  case for dependence between assets.

The luck line is checked too: on random Sets, the assets counted as unusual should match the chance count on
average.

    python what_followed_calibrate.py <prices folder> [sets per kind] [bootstrap runs]

Uses saved prices before the hold-out only (what_followed_run.raw cuts there). Prints a table and exits 1 when a
part's false-positive rate is clearly above 5% (above the 95% upper bound of a fair 5% coin).
"""

from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd

import what_followed as wf
import what_followed_run as run

P_ON = 0.03          # chance a Yes run starts on a No day
P_OFF = 1 / 3        # chance a Yes run ends (runs of about 3 days)


def random_answers(index: pd.DatetimeIndex, rng: np.random.Generator) -> pd.Series:
    out = np.empty(len(index), dtype=object)
    on = False
    for i, u in enumerate(rng.random(len(index))):
        on = (u >= P_OFF) if on else (u < P_ON)
        out[i] = "yes" if on else "no"
    return pd.Series(out, index=index)


def load(prices: str) -> dict:
    tables = {}
    for symbol in run.symbols(prices):
        t = wf.outcomes(run.raw(prices, symbol))
        t.index = t.index.tz_localize(None).normalize()
        t = t[t.index >= pd.Timestamp(run.START)]
        if len(t):
            tables[symbol] = t
    return tables


def one_set(tables: dict, rng: np.random.Generator, shared: bool) -> tuple[pd.DataFrame, dict]:
    calendar = None
    if shared:
        days = pd.date_range(run.START, run.CUT, freq="D")
        calendar = random_answers(days, rng)
    parts, back = [], {}
    for symbol, table in tables.items():
        answers = calendar.reindex(table.index).fillna("no") if shared else random_answers(table.index, rng)
        rows = wf.differences(answers, table)
        back[symbol] = wf.daily_differences(answers, table, "first")
        if rows.empty:
            continue
        rows["asset"], rows["kind"] = symbol, run.kind_of(symbol)
        parts.append(rows)
    return (pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()), back


def calibrate(prices: str, n_sets: int = 100, runs: int = 999, seed: int = 7) -> dict:
    tables = load(prices)
    rng = np.random.default_rng(seed)
    report = {}
    for mode in ("independent", "shared"):
        hits = {k: [] for k in ("all", "coins", "equities", "compare")}
        luck_gap = []
        for i in range(n_sets):
            rows, back = one_set(tables, rng, mode == "shared")
            if rows.empty:
                continue
            for name, sub in (("all", rows), ("coins", rows[rows["kind"] == "crypto"]),
                              ("equities", rows[rows["kind"] == "equity"])):
                if wf.weeks(sub) < wf.MIN_WEEKS:
                    continue
                for m in ("first", "move"):
                    p = wf.test(sub, m, runs, seed + i).get("p_two_sided")
                    if p is not None:
                        hits[name].append(p <= 0.05)
            c = wf.compare(rows, "first", runs, seed + i)
            if c and c.get("p_two_sided") is not None:
                hits["compare"].append(c["differ"])
            lk = wf.luck(rows, back, "first", shifts=100, seed=seed + i)
            if lk:
                luck_gap.append(lk["unusual"] - lk["chance_exact"])
        report[mode] = {k: {"tests": len(v), "rate": float(np.mean(v)) if v else None} for k, v in hits.items()}
        report[mode]["luck_unusual_minus_chance"] = float(np.mean(luck_gap)) if luck_gap else None
    return report


def too_high(rate: float | None, n: int) -> bool:
    """Above the 95% upper bound of a fair 5% rate for n tests."""
    if rate is None or n == 0:
        return False
    return rate > 0.05 + 1.645 * math.sqrt(0.05 * 0.95 / n)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    prices = argv[0]
    n_sets = int(argv[1]) if len(argv) > 1 else 100
    runs = int(argv[2]) if len(argv) > 2 else 999
    report = calibrate(prices, n_sets, runs)
    print(json.dumps(report, indent=1))
    bad = [(mode, k) for mode, r in report.items() for k, v in r.items()
           if isinstance(v, dict) and too_high(v["rate"], v["tests"])]
    print("too often:", bad or "none")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
