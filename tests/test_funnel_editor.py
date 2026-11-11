"""🔻 Funnels editor helpers (funnel_editor.py): provenance, upgrades, the change summary and what is saved."""

import copy

import funnel_editor as fe
import prism


def test_provenance_and_upgrade():
    lib = prism.demo_sets()
    f = fe.template("crypto", "long")
    assert fe.provenance(f, lib) == "Your copy of a provided funnel"
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


def _editor_app():
    """Lattice → 🔻 Funnels with one saved crypto funnel and no real database."""
    import streamlit as st

    import funnel_editor
    import lattice_panel

    saved = {**funnel_editor.template("crypto", "short"), "id": "f1", "owner_id": "test", "stages_version": 1}

    class Q:
        def __init__(self, rows):
            self.rows = rows

        def __getattr__(self, name):
            return lambda *a, **k: self

        @property
        def data(self):
            return self.rows

    class Db:
        def table(self, name):
            return Q([saved] if name == "funnels" else [])

        def rpc(self, *a, **k):
            return Q("f2")

    st.session_state.setdefault("lattice_open", True)
    st.session_state.setdefault("lattice_section", "funnels")
    lattice_panel.render(st, Db(), [("crypto", "bitcoin", "Bitcoin")], "test")


def test_funnels_tab_runs_inside_streamlit():
    import pytest

    testing = pytest.importorskip("streamlit.testing.v1")
    app = testing.AppTest.from_function(_editor_app, default_timeout=120)
    app.run()
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Save and activate" in labels and "Duplicate" in labels
    save = next(b for b in app.button if b.label == "Save and activate")
    assert save.disabled                                       # nothing changed yet
    app.text_input(key="fe_name_f1").set_value("Shorts").run()
    assert not app.exception
    assert not next(b for b in app.button if b.label == "Save and activate").disabled
    app.selectbox(key="funnel_edit").set_value("new:equity:long").run()
    labels = [b.label for b in app.button]
    assert not app.exception and "Make my own copy" in labels and "Delete" not in labels


def test_first_funnels_legacy_keys_name_the_library_sets():
    assert fe.provided_key({"provided": "funnel:trend:12h:short"}) == "demo:ema_down_12h"
    assert fe.provided_key({"provided": "funnel:entry:long"}) == "demo:entry_long_1h"
    lib = prism.demo_sets()
    old = fe.template("crypto", "long")
    old["stages"][0]["set_source"] = {"provided": "funnel:trend:1D:long"}
    old["stages"][0]["set_body"] = lib["demo:ema_up_1d"]
    assert fe.upgrade_for(old["stages"][0], lib, {}) is None                  # the same Set as today: nothing to do
    choices = fe._set_choices(lib, {})
    assert fe._choice_of(old["stages"][0], choices) == "provided:demo:ema_up_1d"   # found in the list


def test_an_untouched_copy_of_an_older_provided_funnel_is_recognised():
    lib = prism.demo_sets()
    old = fe.template("crypto", "long")
    old["stages"][0]["set_body"] = lib["demo:turn_up_1d"]                    # the Stochastic daily stage of 10 Nov
    old["stages"][0]["set_source"] = {"provided": "demo:turn_up_1d"}
    assert fe.provenance(old, lib) == "Your copy of an earlier version of a provided funnel"
