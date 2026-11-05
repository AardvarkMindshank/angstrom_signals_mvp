"""Lattice stage 5: confirmations and vetoes in the editor, fixed subjects in Sets (E4). Synthetic data only."""

from __future__ import annotations

import copy

import pandas as pd

import lattice_editor as le
import lattice_sets as ls
import prism
import signal_groups as sg
from signal_library import DataContext, engine
from signal_library import certify as cf
from tests.replay_helpers import full_indicators


def setup_function(_):
    engine.clear_cache()


def _ctx(kind, asset, seed):
    frame = full_indicators(cf.synthetic_crypto(days=420, seed=seed).histories["1D"].raw)
    data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
    return DataContext(kind, asset, candle_loader=lambda k, a, tf: data, now=frame.index[-1] + pd.Timedelta(days=1))


# ----------------------------------------------------------------------------------------------- confirmations and vetoes

def test_trend_confirmation_now_opens_in_the_editor_and_saves_back_exactly():
    doc = sg.starter("starter:trend-confirmation")
    model, why = le.from_document(doc)
    assert why is None and [c["kind"] for c in model["conditions"]] == ["confirmation", "confirmation", "veto"]
    back = le.to_document(model)
    assert sg.validate_group(back) == []
    assert back["conditions"] == doc["conditions"]
    assert [(m["ref"], m["role"], m.get("transform"), m.get("weight")) for m in back["members"]] == \
        [(m["ref"], m["role"], m.get("transform"), m.get("weight")) for m in doc["members"]]
    assert le.clean_model(model) == model
    assert "custom settings" in le.member_tag(next(m for m in model["members"] if m.get("params")))
    assert 'Veto “Daily regime is ranging' in le.describe(model)


def test_reversal_evidence_is_still_refused_with_a_reason():
    model, why = le.from_document(sg.starter("starter:reversal-evidence"))
    assert model is None and "more complex than the editor can show yet" in why


def test_condition_checks():
    rsi = {"key": "rsi", "id": "rsi.level", "version": 1, "timeframe": "1D", "role": "condition"}
    ma = {"key": "ma", "id": "ma.position", "version": 1, "timeframe": "1D", "role": "score"}
    veto = {"key": "hot", "label": "RSI very high", "kind": "veto", "joiner": "all",
            "clauses": [{"operand": "rsi:rsi", "op": "gte", "value": "80"}]}
    model = {"name": "T", "members": [ma, rsi], "rules": [{"id": "up", "label": "Up", "joiner": "all",
             "clauses": [{"operand": "score", "op": "gte", "value": "+30"}]}], "conditions": [veto],
             "otherwise": {"id": "neutral", "label": "Neutral"}}
    found = le.checks(model)
    assert found["blocks"] == []
    assert not any("no rule uses it" in w for w in found["warnings"])          # used by the veto
    assert any("every label becomes Vetoed" in w for w in found["warnings"])
    empty = copy.deepcopy(model)
    empty["conditions"][0]["clauses"] = []
    assert any("has no condition yet" in b for b in le.checks(empty)["blocks"])
    twice = copy.deepcopy(model)
    twice["conditions"].append(copy.deepcopy(veto))
    keys = [c["key"] for c in le.clean_model(twice)["conditions"]]
    assert len(set(keys)) == 2 and keys[0] == "hot"                          # cleaned to stay distinct
    doc = le.to_document(model)
    assert doc["conditions"] == [{"key": "hot", "label": "RSI very high", "kind": "veto",
                                  "rule": {"member": "rsi", "field": "rsi", "gte": 80.0}}]


def _saved_with_confirmation():
    return [{"id": "33333333-3333-3333-3333-333333333333", "kind": "group", "name": "Trend Confirmation",
             "owner_id": None, "starter_alias": "starter:trend-confirmation", "current_version": 1,
             "versions": [{"version": 1, "body": sg.starter("starter:trend-confirmation")}]}]


def test_sets_can_test_a_confirmation_or_veto_state():
    choices = ls.group_choices(_saved_with_confirmation(), "me")
    model = ls.clean_model({"name": "S", "groups": [{"source": next(iter(choices))}], "lines": [
        {"target": "condition", "group": "trend_confirmation", "condition": "bullish_confirmed", "op": "is", "value": "met"},
        {"target": "condition", "group": "trend_confirmation", "condition": "ranging_veto", "op": "is_not", "value": "active"}]},
        choices)
    targets = {t["key"] for t in ls.targets(model, choices)}
    assert "condition:trend_confirmation:ranging_veto" in targets
    doc = ls.to_document(model, choices)
    assert doc["decision"]["rule"]["all"][1] == {"not": {"group": "trend_confirmation", "condition": "ranging_veto",
                                                         "state": {"eq": "active"}}}
    assert sg.validate_set(doc) == [] and ls.checks(model, choices)["blocks"] == []
    assert ls.from_document(doc, choices) == (model, None)
    assert "veto “Daily regime is ranging" in ls.describe(model, choices)


# ----------------------------------------------------------------------------------------------- E4: fixed subjects

def _trend_set(subject=None, standalone_subject=None):
    body = prism.labelled_starter("starter:trend")
    group = {"key": "lead", "snapshot": body}
    if subject:
        group["subject"] = subject
    item = {"key": "rsi_lead", "label": "RSI", "role": "condition",
            "ref": {"id": "rsi.level", "version": 1, "timeframe": "1D", "params": {}}}
    if standalone_subject:
        item["subject"] = standalone_subject
    return {"schema": "angstrom.set/1", "name": "COIN leads", "lineage_version": 3, "score": None,
            "groups": [group], "standalone": [item], "market_context": [],
            "decision": {"version": 1, "rule": {"all": [{"group": "lead", "outcome": {"eq": "bullish"}},
                                                        {"member": "rsi_lead", "field": "rsi", "lte": 100}]}}}


def test_fixed_subjects_are_validated():
    assert sg.validate_set(_trend_set({"kind": "equity", "id": "COIN"}, {"kind": "equity", "id": "COIN"})) == []
    for bad in ({"kind": "stock", "id": "COIN"}, {"kind": "equity", "id": "C O I N"}, {"kind": "equity"}, "COIN"):
        assert sg.validate_set(_trend_set(bad)), bad


def test_a_fixed_subject_is_read_on_its_own_data_at_the_same_moment():
    contexts = {("crypto", "bitcoin"): _ctx("crypto", "bitcoin", 1), ("equity", "COIN"): _ctx("equity", "COIN", 4)}
    asked = []

    def subject_context(kind, asset):
        asked.append((kind, asset))
        return contexts[(kind, asset)]
    doc = _trend_set({"kind": "equity", "id": "COIN"}, {"kind": "equity", "id": "COIN"})
    out = sg.evaluate_set(doc, contexts[("crypto", "bitcoin")], subject_context=subject_context)
    direct = sg.evaluate_group(doc["groups"][0]["snapshot"], contexts[("equity", "COIN")])
    group = out["groups"][0]
    assert group["subject"] == {"kind": "equity", "id": "COIN"}
    assert group["result"]["score"]["value"] == direct["score"]["value"]
    assert out["standalone"][0]["signal"]["subject"] == "equity:COIN"
    assert asked == [("equity", "COIN")]                                     # one context, shared by both items
    plain = sg.evaluate_group(doc["groups"][0]["snapshot"], contexts[("crypto", "bitcoin")])
    assert plain["score"]["value"] != direct["score"]["value"]               # really a different asset's data


def test_without_a_source_for_the_fixed_subject_the_answer_is_unknown_never_a_guess():
    doc = _trend_set({"kind": "equity", "id": "COIN"})
    out = sg.evaluate_set(doc, _ctx("crypto", "bitcoin", 1))
    assert out["groups"][0]["result"]["status"] == "unsupported"
    assert out["decision"]["answer"] in ("unknown", "no")
    assert any(d["text"].startswith("lead outcome") for d in out["decision"]["decisive"]) or out["decision"]["answer"] == "no"


def test_prism_reads_fixed_subjects_live_and_at_the_replay_moment():
    contexts = {("crypto", "bitcoin"): _ctx("crypto", "bitcoin", 1), ("equity", "COIN"): _ctx("equity", "COIN", 4)}
    doc = _trend_set({"kind": "equity", "id": "COIN"})
    rows = prism.run_now(doc, [("crypto", "bitcoin", "Bitcoin")], live_context=lambda k, i: contexts[(k, i)])
    assert rows[0]["lines"]["decision.rule.all[0]"][0] in "✓✗"            # decided from COIN's data, not missing

    seen = []

    class Run:
        def context(self, kind, asset, as_of):
            seen.append((kind, asset, as_of))
            raise RuntimeError("no candles before that date")
    when = pd.Timestamp("2024-06-01", tz="UTC")
    prism.run_now(doc, [("crypto", "bitcoin", "Bitcoin")], live_context=None, replay=(Run(), when))
    assert seen[0] == ("crypto", "bitcoin", when)


def test_set_editor_round_trips_fixed_subjects_and_names_them():
    choices = ls.group_choices(_saved_with_confirmation(), "me")
    raw = {"name": "COIN leads", "groups": [{"source": next(iter(choices)), "subject": {"kind": "equity", "id": "coin"}}],
           "standalone": [{"id": "rsi.level", "subject": {"kind": "crypto", "id": "Bitcoin"}}],
           "lines": [{"target": "score", "group": "trend_confirmation", "op": "gte", "value": "+30"}]}
    model = ls.clean_model(raw, choices)
    assert model["groups"][0]["subject"] == {"kind": "equity", "id": "COIN"}
    assert model["standalone"][0]["subject"] == {"kind": "crypto", "id": "bitcoin"}
    doc = ls.to_document(model, choices)
    assert doc["groups"][0]["subject"] == {"kind": "equity", "id": "COIN"} and sg.validate_set(doc) == []
    assert ls.from_document(doc, choices) == (model, None)
    assert "Trend Confirmation v1 on COIN score is at least +30" in ls.describe(model, choices)
    assert any("same moment" in w for w in ls.checks(model, choices)["warnings"])
    bad = ls.clean_model({**raw, "groups": [{"source": next(iter(choices)), "subject": {"kind": "equity", "id": "bad id!"}}]},
                         choices)
    assert "subject" not in bad["groups"][0]


# ----------------------------------------------------------------------------------------------- open to everyone

def test_the_panel_is_for_every_account_and_loads_nothing_until_switched_on():
    from pathlib import Path

    app = Path(__file__).resolve().parent.parent.joinpath("app.py").read_text()
    panel = app.index('st.expander("Angstrom Lattice", icon=":material/hub:"')
    admin = app.index('if str((load_profile() or {}).get("role") or "") == "admin":\n    admin_panel()')
    assert panel < admin                                            # outside the admin-only block
    inspector = Path(__file__).resolve().parent.parent.joinpath("signal_inspector.py").read_text()
    assert "lattice_view" not in inspector and "prism_view" not in inspector

    import lattice_panel

    class St:
        def caption(self, *a, **k):
            pass

        def html(self, *a, **k):
            pass

        def toggle(self, *a, **k):
            return False

        def tabs(self, *a, **k):
            raise AssertionError("nothing renders while the panel is off")
    lattice_panel.render(St(), None, [], "u")


def test_the_open_to_all_sql_only_drops_the_admin_check():
    from pathlib import Path

    sql_dir = Path(__file__).resolve().parent.parent / "sql"
    opened = (sql_dir / "2026-11-07_prism_open_to_all.sql").read_text()
    original = (sql_dir / "2026-11-06_prism_scans.sql").read_text()
    assert "is_admin" not in opened and "prism_preview_admins_only" not in opened
    for rule in ("too_many_active_scans", "set_not_scannable", "bad_schedule", "not_owner", "security definer",
                 "if active >= 5"):
        assert rule in opened and rule in original
