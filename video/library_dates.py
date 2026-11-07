"""
Real-price check of the provided library (agreed plan, Stage A): run every provided Set on the demo watchlist at past
moments before the protected hold-out (which starts 30 Oct 2024), from the saved daily prices, through the same
replay Prism's "Run at a past moment" uses. Prints one line per date and a summary per Set, so a person can see that
each Set says Yes sometimes, No mostly, and rarely Unknown.

Usage: python video/library_dates.py <prices folder> <first date> <last date> <days between>
"""
import os
import sys
from collections import Counter
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent)]
os.environ["DEMO_PRICES"] = sys.argv[1]
import pandas as pd  # noqa: E402

import prism  # noqa: E402
from saved_prices import CRYPTO, EQUITIES, candles  # noqa: E402
from signal_library.replay import DISPLAY, ReplayRun  # noqa: E402

LIBRARY = ["demo:pullback", "demo:rally", "demo:alignment", "demo:breakout", "demo:squeeze", "demo:range_low",
           "demo:near_support", "demo:btc_filter", "demo:overextended"]
docs = prism.demo_sets()
assets = [("crypto", a, a) for a in CRYPTO] + [("equity", s, s) for s in EQUITIES]
totals = {k: Counter() for k in LIBRARY}
examples = {k: [] for k in LIBRARY}
unknown_reasons = {k: Counter() for k in LIBRARY}
start, end, step = sys.argv[2], sys.argv[3], int(sys.argv[4])
for day in pd.date_range(start, end, freq=f"{step}D"):
    as_of = pd.Timestamp(day.date().isoformat() + " 00:05", tz="UTC")
    assert as_of < pd.Timestamp("2024-10-30", tz="UTC")
    run = ReplayRun(DISPLAY, candles, flows=None, sentiment=None, max_steps=1, shortcut=True, reuse_frames=True)
    line = []
    for key in LIBRARY:
        rows = prism.run_now(docs[key], assets, live_context=None, replay=(run, as_of))
        count = Counter(r["answer"] for r in rows)
        totals[key].update(count)
        yes = [r["asset"] for r in rows if r["answer"] == "yes"]
        if yes and len(examples[key]) < 6:
            examples[key].append(f"{day.date()}: {', '.join(yes)}")
        for r in rows:
            if r["answer"] == "unknown":
                unknown_reasons[key][r["reason"][:90]] += 1
        line.append(f"{key[5:]}:{count['yes']}/{count['no']}/{count['unknown']}")
    print(day.date(), " ".join(line), flush=True)

print("\n## Summary (yes / no / unknown over all dates and assets)")
for key in LIBRARY:
    t = totals[key]
    n = sum(t.values()) or 1
    print(f"\n{docs[key]['name']}: yes {t['yes']} ({100 * t['yes'] / n:.1f}%), no {t['no']}, unknown {t['unknown']}")
    for e in examples[key]:
        print("   e.g.", e)
    for reason, c in unknown_reasons[key].most_common(2):
        print(f"   unknown x{c}: {reason}")
