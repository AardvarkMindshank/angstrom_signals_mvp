"""The provided library (Stage A of the agreed plan): Sets built only from existing signals and Groups."""

import pandas as pd

import group_readings as gr
import prism
import signal_groups as sg
from signal_library import certify as cf
from signal_library import engine
from tests.replay_helpers import full_indicators

LIBRARY = ("demo:alignment", "demo:breakout", "demo:squeeze", "demo:range_low", "demo:near_support",
           "demo:btc_filter", "demo:overextended")


def test_every_provided_set_is_valid_and_explains_itself():
    docs = prism.demo_sets()
    for key in LIBRARY + ("demo:pullback", "demo:rally", "demo:agree", "demo:entry"):
        assert sg.validate_set(docs[key]) == [], key
        assert len(docs[key]["purpose"]) > 40, key
    assert sg.validate_group(prism._breakout_group()) == []


def test_the_library_answers_on_stored_daily_bars():
    seen = {k: set() for k in LIBRARY}
    for seed in (3, 11):
        frame = full_indicators(cf.synthetic_crypto(days=420, seed=seed).histories["1D"].raw)
        for pos in range(200, 420, 10):
            engine.clear_cache()
            window = frame.iloc[:pos]
            ctx, _ = gr.stored_context(window, "crypto", window.index[-1] + pd.Timedelta(days=3))
            for key in LIBRARY:
                result = sg.evaluate_set(prism.library_sets()[key], ctx, subject_context=lambda k, i: ctx)
                seen[key].add(prism.row("x", result, "")["answer"])
    for key in ("demo:squeeze", "demo:range_low", "demo:btc_filter", "demo:overextended", "demo:near_support"):
        assert {"yes", "no"} <= seen[key], (key, seen[key])
    assert "no" in seen["demo:breakout"]          # made-up volume never spikes 1.5x; the parts are tested below
    assert seen["demo:alignment"] <= {"yes", "no", "unknown"}   # weekly bars are not stored: Unknown on this path


def test_no_support_zone_below_answers_no_not_unknown():
    doc = prism.library_sets()["demo:near_support"]
    rule = doc["decision"]["rule"]["all"]
    assert {"member": "zones", "field": "support.0.touches", "exists": True} in rule


def test_the_breakout_group_sees_recent_upward_breaks():
    frame = full_indicators(cf.synthetic_crypto(days=420, seed=11).histories["1D"].raw)
    met = 0
    for pos in range(200, 420, 2):
        window = frame.iloc[:pos]
        ctx, _ = gr.stored_context(window, "crypto", window.index[-1] + pd.Timedelta(days=3))
        result = sg.evaluate_group(prism._breakout_group(), ctx)
        met += any(c["key"] == "recent_up" and c["state"] == "met" for c in result.get("conditions") or [])
    assert met > 0


def test_provided_sets_can_be_table_columns():
    import table_columns as tc

    _, sets = tc.options([], "me")
    assert "demo:breakout" in sets and "demo:agree" not in sets          # the "(demo)" teaching Sets stay in Prism
    chosen = tc.chosen({"table_columns": {"groups": [], "sets": ["demo:squeeze", "demo:nope"]}})
    assert chosen["sets"] == ["demo:squeeze"]
    spec = tc.resolve(chosen, [])[0]
    assert spec["name"] == "Volatility squeeze" and spec["doc"]["decision"]
    assert tc._pick(spec, None) == "lattice|sets|demo:squeeze"
