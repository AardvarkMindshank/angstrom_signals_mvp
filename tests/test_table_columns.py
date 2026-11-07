"""Reading columns in the asset tables: choosing, resolving, working out and drawing Groups and Sets."""

import pandas as pd

import group_readings as gr
import lattice_editor as le
import lattice_sets as ls
import table_columns as tc
from signal_library import certify as cf
from signal_library import engine
from tests.replay_helpers import full_indicators


def _saved():
    import sys
    sys.path.insert(0, "video")
    import seed

    return seed.configs({"pullback"})


def test_default_is_the_dashboard_readings_and_bad_choices_are_dropped():
    assert tc.chosen({}) == {"groups": ["starter:trend", "starter:stretch", "starter:flow"], "sets": []}
    got = tc.chosen({"table_columns": {"groups": ["starter:flow", "nope", "saved:x", "saved:x"],
                                       "sets": ["starter:trend", "saved:y"]}})
    assert got == {"groups": ["starter:flow", "saved:x"], "sets": ["saved:y"]}


def test_options_and_resolve_use_the_newest_version():
    saved = _saved()
    groups, sets = tc.options(saved, "demo")
    assert "saved:cfg-my-trend" in groups and "starter:trend" in groups
    assert list(sets) == ["saved:cfg-pullback"]
    specs = tc.resolve({"groups": ["starter:trend", "saved:cfg-my-trend", "saved:gone"],
                        "sets": ["saved:cfg-pullback"]}, saved)
    assert [(s["key"], s["part"], s["cluster"]) for s in specs] == [
        ("starter:trend", "groups", "trend"), ("saved:cfg-my-trend", "groups", None),
        ("saved:cfg-pullback", "sets", None)]
    assert tc.fingerprint(specs) != tc.fingerprint(specs[:2])


def test_columns_work_out_on_the_stored_bars():
    saved = _saved()
    specs = tc.resolve({"groups": ["saved:cfg-my-trend"], "sets": ["saved:cfg-pullback"]}, saved)
    frame = full_indicators(cf.synthetic_crypto(days=420, seed=11).histories["1D"].raw)
    engine.clear_cache()
    ctx, _ = gr.stored_context(frame, "crypto", frame.index[-1] + pd.Timedelta(days=3), asset_id="x")
    cells = tc.evaluate(specs, ctx)
    group = cells["saved:cfg-my-trend"]
    assert group.get("value") is None or -100 <= group["value"] <= 100
    assert group.get("label") in ("Bullish", "Bearish", "Neutral", "Vetoed", None)
    assert cells["saved:cfg-pullback"]["answer"] in ("yes", "no", "unknown")


def test_cells_explain_on_hover_and_open_lattice_on_click():
    spec_g = {"key": "saved:g1", "part": "groups", "name": "My Trend", "config": "g1", "version": 2, "cluster": None}
    spec_s = {"key": "saved:s1", "part": "sets", "name": "Pullback", "config": "s1", "version": 1, "cluster": None}
    g = tc.group_cell(spec_g, {"value": 42.0, "label": "Bullish"})
    assert "data-pick='lattice|groups|g1'" in g and "My Trend: +42 · Bullish" in g and "data-sec='g'" in g
    s = tc.set_cell(spec_s, {"answer": "yes", "why": "every line holds"})
    assert "data-pick='lattice|sets|s1'" in s and "Pullback: Yes · every line holds" in s and "✓" in s
    assert "data-sort='0'" in tc.set_cell(spec_s, {"answer": "no"})
    assert "Unknown" in tc.set_cell(spec_s, {"error": "boom"})
    assert "2 of 3 Sets say Yes" in tc.folded_cell("sets", [{"answer": "yes"}, {"answer": "yes"}, {"answer": "no"}])


def test_daily_only():
    assert tc.daily_only(None)
    doc = {"members": [{"ref": {"timeframe": "1D"}}, {"ref": {"timeframe": "4h"}}]}
    assert not tc.daily_only(doc)


def test_a_cell_in_a_row_opens_that_assets_why_block():
    spec_g = {"key": "saved:g1", "part": "groups", "name": "My Trend", "config": "g1", "version": 2, "cluster": None}
    assert "data-pick='Crypto|bitcoin|breakdown|saved:g1'" in tc.group_cell(spec_g, {"value": 5.0}, "Crypto|bitcoin")
