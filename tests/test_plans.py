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


def test_set_cards_merge_twins_and_keep_every_provided_set():
    import prism_board as pb
    import set_cards

    listed = pb.set_list(pb.set_choices([], "me"), "pro", "hide")
    ideas = listed["cards"]["ideas"]
    assert [i["title"] for i in ideas][:2] == ["Follow the trend", "Buy the dip / sell the rally"]
    cards = [c for i in ideas for c in i["cards"]]
    keys = {m["key"] for c in cards for m in c["members"]}
    assert keys == set_cards.placed_keys()                         # every provided Set is reachable from a card
    ema = next(c for c in cards if c["id"] == "ema")
    assert ema["dirs"] == ["long", "short"] and ema["tfs"] == ["1w", "1d", "12h", "4h"] and len(ema["members"]) == 8


def test_cards_follow_the_plan_and_the_display_setting():
    import prism_board as pb

    choices = pb.set_choices([], "me")
    hidden = pb.set_list(choices, "free", "hide")["cards"]["ideas"]
    assert all(not c["locked"] for i in hidden for c in i["cards"])         # Hide: only what Free includes
    grey = [c for i in pb.set_list(choices, "free", "grey")["cards"]["ideas"] for c in i["cards"]]
    locked = [c for c in grey if c["locked"]]
    assert locked and all(c["tag"] in ("Plus", "Pro") for c in locked)
    assert all(c["tag"] == "" for c in grey if not c["locked"])               # no label on what you can use
