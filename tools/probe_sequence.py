"""One-off diagnostic (16 Nov 2026): why does a "breakout, then volume fades within 5 closes" Set read Unknown on
crypto and SIE.DE but No on US shares? Runs Prism's own live path and prints any error reading an earlier close."""

import traceback

import prism
import signal_library as sl
from signal_groups import sets
from signal_library.replay_display import display_run

base = prism.library_sets()["demo:breakout"]
doc = {**base, "name": "Breakout fading (probe)", "decision": {"version": 1, "rule": {"sequence": {
    "first": base["decision"]["rule"], "then": {"member": "volume", "lte": 1.5}, "within": 5}}}}

real_parts = sets._parts


def loud_parts(*args, **kwargs):
    try:
        return real_parts(*args, **kwargs)
    except Exception:
        print("    _parts FAILED:\n      " + traceback.format_exc().replace("\n", "\n      ")[-1800:])
        raise


sets._parts = loud_parts
real_past = sets._past


def loud_past(doc_, ctx, earlier, *a, **k):
    def wrapped(day):
        try:
            return earlier(day)
        except Exception:
            print(f"    earlier({day}) FAILED:\n      " + traceback.format_exc().replace("\n", "\n      ")[-1800:])
            raise
    out = real_past(doc_, ctx, wrapped if earlier else earlier, *a, **k)
    print("    past:", None if out is None else ["read" if x is not None else "UNREADABLE" for x in out])
    return out


sets._past = loud_past
from signal_groups import sequence as _seq
real_judge = _seq.judge


def loud_judge(spec, a, b, c):
    out = real_judge(spec, a, b, c)
    print("    judge: first at c0..c5 =", a, "| then at c0 =", b, "| cancel =", c, "->", out)
    return out


_seq.judge = loud_judge

for kind, aid in (("crypto", "bitcoin"), ("equity", "SIE.DE"), ("equity", "AAPL")):
    print(f"\n===== {kind} {aid}")
    out = prism.run_now(doc, [(kind, aid, aid)], live_context=lambda k, i: sl.DataContext(k, i),
                        earlier_run=display_run(None, max_steps=prism.steps_needed(doc), shortcut=True))
    print("RUN NOW:", out[0].get("answer"), "|", out[0].get("reason"))
