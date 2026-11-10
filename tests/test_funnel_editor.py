"""🔻 Funnels editor helpers (funnel_editor.py): provenance, upgrades, the change summary and what is saved."""

import copy

import funnel_editor as fe
import prism


def test_provenance_and_upgrade():
    lib = prism.demo_sets()
    f = fe.template("crypto", "long")
    assert fe.provenance(f, lib) == "Provided by Angstrom"
    old = copy.deepcopy(f)
    old["stages"][1]["set_body"]["decision"]["rule"]["eq"] = "fast_below"    # an older provided version
    assert fe.provenance(old, lib) == "Customised"
    text, body, src = fe.upgrade_for(old["stages"][1], lib, {})
    assert "Upgrade" in text and body == lib[src["provided"]]
    assert fe.upgrade_for(f["stages"][1], lib, {}) is None
    mine = {"c1": {"name": "Mine", "versions": [{"version": 1, "body": {}}, {"version": 3, "body": {"x": 1}}]}}
    stage = {"set_body": {}, "set_source": {"config_id": "c1", "version": 1}}
    text, body, src = fe.upgrade_for(stage, lib, mine)
    assert text == "⬆ Upgrade to version 3" and src == {"config_id": "c1", "version": 3}
    own = {**f, "stages": [{**s, "set_source": {"config_id": "c1", "version": 1}} for s in f["stages"]]}
    own["stages"][0]["set_body"] = {"changed": True}
    assert fe.provenance(own, lib) == "My funnel"


def test_change_summary_says_when_places_reset():
    f = fe.template("crypto", "short")
    f["id"] = "x"
    renamed = {**copy.deepcopy(f), "name": "Shorts"}
    what, reset = fe.changes(f, renamed)
    assert what == ["Names changed."] and not reset
    moved = copy.deepcopy(f)
    moved["stages"][0], moved["stages"][1] = moved["stages"][1], moved["stages"][0]
    assert fe.changes(f, moved)[1]
    pooled = {**copy.deepcopy(f), "pool": {"top": 100}}
    assert fe.changes(f, pooled) == (["The pool changed."], True)
    assert fe.changes(None, f)[1] is False


def test_save_arguments():
    f = fe.template("crypto", "long")
    assert "p_market" not in fe.save_args(f) and "p_pool" not in fe.save_args(f)
    eq = fe.template("equity", "short")
    assert fe.save_args(eq)["p_market"] == "equity"
    assert fe.save_args({**f, "pool": {"top": 50}})["p_pool"] == {"top": 50}
