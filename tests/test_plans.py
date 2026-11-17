"""Membership plans (18 Nov 2026): the plan is the only level; a Set's plan comes from how it is built."""

import os

import plans
import prism

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_plan_names_and_order():
    assert plans.PLANS == ("free", "plus", "pro", "elite")
    assert plans.normalise("PLUS") == "plus" and plans.normalise(None) == plans.BETA_PLAN == "pro"
    assert plans.includes("pro", "plus") and not plans.includes("plus", "pro") and plans.includes("free", "free")


def test_display_setting_defaults_to_hide():
    assert plans.display_mode({}) == "hide"
    assert plans.display_mode({"plan_display": "grey"}) == "grey"
    assert plans.display_mode({"plan_display": "??"}) == "hide"


def _set(standalone=(), groups=(), decision=None):
    return {"standalone": list(standalone), "groups": list(groups), "decision": decision or {}}


def _line(sig, tf="1D", **extra):
    return {"key": sig, "ref": {"id": sig, "timeframe": tf, "params": {}}, **extra}


def test_the_level_rule():
    assert plans.set_level(_set([_line("rsi.level")])) == "free"                       # one line, one timeframe
    assert plans.set_level(_set([_line("rsi.level"), _line("volume.relative")])) == "plus"      # two lines
    assert plans.set_level(_set([_line("rsi.level", "4h")], [{"key": "g", "snapshot": {"members": [
        {"ref": {"id": "ma.position", "timeframe": "1D"}}]}}])) == "plus"               # two timeframes
    assert plans.set_level(_set([_line("rsi.level", subject="BTC")])) == "plus"        # a fixed asset
    assert plans.set_level(_set([_line("osc.wavetrend")])) == "pro"                    # a Pro signal
    assert plans.set_level(_set([_line("rsi.level")], decision={"rule": {"sequence": []}})) == "pro"   # THEN box
    three = _set([_line("rsi.level", "1D"), _line("rsi.level", "4h"), _line("rsi.level", "1h")])
    assert plans.set_level(three) == "pro"


def test_every_provided_set_has_a_level_and_no_set_is_elite_only():
    levels = {d["name"]: plans.set_level(d) for d in prism.demo_sets().values()}
    assert set(levels.values()) <= {"free", "plus", "pro"}
    assert levels["EMA 20 above EMA 50 (daily)"] == "free"
    assert levels["Bullish divergence on 2+ timeframes"] == "pro"


def test_every_library_signal_has_a_plan():
    from signal_library.engine import REGISTRY
    import signal_library  # noqa: F401  registers the signals

    ids = {item["id"] for item in REGISTRY.catalogue()}
    assert ids <= set(plans.SIGNAL_PLAN), sorted(ids - set(plans.SIGNAL_PLAN))


def test_the_plans_table_is_read_only_for_members():
    sql = open(os.path.join(ROOT, "sql", "2026-12-04_user_plans.sql"), encoding="utf-8").read()
    assert "revoke insert, update, delete on public.user_plans from anon, authenticated" in sql
    assert "using (user_id = auth.uid())" in sql
