"""
Find past moments for the training videos: dates before the protected hold-out (which starts 30 Oct 2024) when the
video Sets give some Yes answers on the demo watchlist. Reads only the saved daily prices (reports branch,
data/prices), cut at 29 Oct 2024 as each file is loaded, through the same display replay Prism's "Run at a past
moment" uses. Prints one line per date.

Usage: python video/find_dates.py <prices folder> <sets, comma separated> <first date> <last date> <days between>
"""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent)]
import pandas as pd
import prism  # noqa: E402
import seed  # noqa: E402
import lattice_sets as ls  # noqa: E402
import os  # noqa: E402
os.environ["DEMO_PRICES"] = sys.argv[1]
from signal_library.replay import DISPLAY, ReplayRun  # noqa: E402
from saved_prices import CRYPTO, EQUITIES as EQ, candles  # noqa: E402

saved = seed.configs({"pullback"})
ch = ls.group_choices(saved, seed.USER)
pull = seed.pullback_model(ch)
def doc(model): return ls.to_document(ls.clean_model(model, ch), ch)
def mk(name, groups, standalone, lines):
    return doc({"name": name, "purpose": "", "groups": groups, "standalone": standalone, "lines": lines})
T = {"key": "my_trend", "source": f"saved:{seed.MY_TREND}:1"}
BTC = {"key": "my_trend_2", "source": f"saved:{seed.MY_TREND}:1", "subject": {"kind": "crypto", "id": "bitcoin"}}
RSI = {"key": "level_1d", "id": "rsi.level", "version": 1, "timeframe": "1D", "role": "condition"}
bull = {"target": "outcome", "group": "my_trend", "op": "is", "value": "bullish"}
sets = {
 "pull_v1": (mk("p1", [T], [RSI], [bull, {"target": "member", "member": "level_1d", "field": "rsi", "op": "lte", "value": "40"}]), "crypto"),
 "pull_v2": (mk("p2", [T, BTC], [RSI], [bull, {"target": "member", "member": "level_1d", "field": "rsi", "op": "lte", "value": "40"},
                                         {"target": "outcome", "group": "my_trend_2", "op": "is", "value": "bullish"}]), "crypto"),
 "w1": (mk("w1", [T, {"key": "flow", "source": "saved:cfg-flow:1"}], [], [bull, {"target": "score", "group": "flow", "op": "gte", "value": "+30"}]), "crypto"),
 "w2": (mk("w2", [T], [RSI], [bull, {"target": "member", "member": "level_1d", "field": "rsi", "op": "gte", "value": "75"}]), "crypto"),
 "w3": (mk("w3", [], [{"key": "swings_1d", "id": "structure.swings", "version": 1, "timeframe": "1D", "role": "condition"},
                      {"key": "position_1d", "id": "bollinger.position", "version": 1, "timeframe": "1D", "role": "condition"},
                      {"key": "heavy_candle_1d", "id": "volume.heavy_candle", "version": 1, "timeframe": "1D", "role": "condition"}],
           [{"target": "member", "member": "swings_1d", "field": "structure", "op": "is", "value": "up"},
            {"target": "member", "member": "position_1d", "field": "position", "op": "gte", "value": "1"},
            {"target": "member", "member": "heavy_candle_1d", "field": "volume_ratio", "op": "gte", "value": "2"}]), "equity"),
}
def dip(name, sid, field, op, value):
    member = {"key": "dip_1d", "id": sid, "version": 1, "timeframe": "1D", "role": "condition"}
    return (mk(name, [T], [member], [bull, {"target": "member", "member": "dip_1d", "field": field, "op": op, "value": value}]),
            "crypto")


sets.update({
    "trend": (mk("t", [T], [], [bull]), "crypto"),
    "rsi45": dip("rsi45", "rsi.level", "rsi", "lte", "45"),
    "rsi50": dip("rsi50", "rsi.level", "rsi", "lte", "50"),
    "stoch20": dip("stoch20", "stochastic.level", "stoch_k", "lte", "20"),
    "stoch30": dip("stoch30", "stochastic.level", "stoch_k", "lte", "30"),
    "move5": dip("move5", "move.seven_day", "change_7d_pct", "lte", "-5"),
    "eq_rsi40": (dip("eq_rsi40", "rsi.level", "rsi", "lte", "40")[0], "equity"),
    "eq_stoch20": (dip("eq_stoch20", "stochastic.level", "stoch_k", "lte", "20")[0], "equity"),
})
which = sys.argv[2].split(",")
start, end, step = sys.argv[3], sys.argv[4], int(sys.argv[5])
for day in pd.date_range(start, end, freq=f"{step}D"):
    as_of = pd.Timestamp(day.date().isoformat() + " 00:05", tz="UTC")
    assert as_of < pd.Timestamp("2024-10-30", tz="UTC")
    out = []
    run = ReplayRun(DISPLAY, candles, flows=None, sentiment=None, max_steps=1, shortcut=True, reuse_frames=True)
    for name in which:
        d, market = sets[name]
        picked = [("crypto", a, a) for a in CRYPTO] if market == "crypto" else [("equity", s, s) for s in EQ]
        rows = prism.run_now(d, picked, live_context=None, replay=(run, as_of))
        yes = [r["asset"] for r in rows if r["answer"] == "yes"]
        unk = sum(r["answer"] == "unknown" for r in rows)
        out.append(f"{name}:{len(yes)}{'?' + str(unk) if unk else ''}[{','.join(yes)}]")
    print(day.date(), " ".join(out), flush=True)
