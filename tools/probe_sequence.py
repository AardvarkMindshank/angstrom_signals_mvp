"""One-off diagnostic (16 Nov 2026): why does a "breakout, then volume fades within 5 closes" Set read Unknown on
crypto and SIE.DE but No on US shares? Prints, per asset, each earlier close the sequence reads and what failed."""

import traceback

import pandas as pd

import prism
import signal_groups as sg
import signal_library as sl
from signal_groups import sequence
from signal_library.replay_display import display_run

base = prism.library_sets()["demo:breakout"]
first = base["decision"]["rule"]
doc = {**base, "name": "Breakout fading (probe)", "decision": {"version": 1, "rule": {"sequence": {
    "first": first, "then": {"member": "volume", "lte": 1.5}, "within": 5}}}}
print("valid:", sg.validate_set(doc) or "yes", "| steps:", prism.steps_needed(doc))

for kind, aid in (("crypto", "bitcoin"), ("crypto", "ripple"), ("equity", "SIE.DE"), ("equity", "AAPL")):
    print(f"\n===== {kind} {aid}")
    ctx = sl.DataContext(kind, aid)
    live = ctx.candles("1D")
    if live.get("error"):
        print("live candles error:", live["error"])
        continue
    lf = live["frame"]
    print("live source:", live.get("source"), "| last index:", list(lf.index[-3:]), "| forming:", list(lf["forming"].tail(3)))
    run = display_run(None, max_steps=prism.steps_needed(doc), shortcut=True)
    hist = run.history(kind, aid, "1D")
    if isinstance(hist, dict):
        print("earlier-run history error:", hist)
        continue
    print("run source:", hist.source.get("provider"), "| last index:", list(hist.raw.index[-3:]))
    days = sequence.closes(ctx, 5)
    print("closes read:", [str(d) for d in days])
    earlier = prism.earlier_from(run, kind, aid)
    for day in days[1:]:
        try:
            pctx, psub = earlier(day)
            res = sg.evaluate_set(base, pctx, data_mode="point_in_time", subject_context=psub)
            parts = {k: res.get(k) for k in ("status", "outcome", "decision") if k in res}
            lines = (res.get("decision") or {}).get("lines") if isinstance(res.get("decision"), dict) else None
            print(f"  {day}: status={res.get('status')} answer={(res.get('decision') or {}).get('value') if isinstance(res.get('decision'), dict) else res.get('decision')}")
            for l in lines or []:
                print("     ", l.get("text"), "->", l.get("value"), "|", l.get("reading"))
            for s in res.get("standalone") or []:
                sig = s.get("signal") or {}
                print("      member", s["key"], sig.get("status"), sig.get("value"), sig.get("notes"))
            for g in res.get("groups") or []:
                r = g.get("result") or {}
                print("      group", g.get("key"), r.get("status"), r.get("score"), (r.get("conditions") or r.get("reason")))
        except Exception:
            print(f"  {day}: FAILED")
            print("    " + traceback.format_exc().replace("\n", "\n    ")[-1500:])
    out = prism.run_now(doc, [(kind, aid, aid)], live_context=lambda k, i: sl.DataContext(k, i),
                        earlier_run=display_run(None, max_steps=prism.steps_needed(doc), shortcut=True))
    print("RUN NOW:", {k: out[0].get(k) for k in ("Answer", "Deciding line") if k in out[0]} or out[0])
