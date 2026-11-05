"""Lattice stage 1: Group outcomes (E1), Set decisions (E2), field descriptions and ranges (E3), compatibility.

The numbered tests are the fixtures in docs/design/lattice_prism.md §6. Synthetic data and the frozen pre-hold-out
cache only; nothing here reads data from 30 October 2024 onwards.
"""

from __future__ import annotations

import copy
import json

import pandas as pd
import pytest

import signal_groups as sg
from signal_groups import decision, outcomes, rules
from signal_groups.transforms import UNKNOWN
from signal_groups.units import score_from_display, score_to_display
from signal_library import REGISTRY, DataContext, SignalRef, certification, engine, evaluate, fields
from signal_library import certify as cf
from tests import lattice_compat
from tests.replay_helpers import full_indicators


def setup_function(_):
    engine.clear_cache()


# ----------------------------------------------------------------------------- helpers

def _rctx(score=0.5, **members):
    """A rules.Context with plain members: name=value, or name=None for an unavailable member."""
    table = {k: {"available": v is not None, "value": v, "instance": f"{k}@1", "roots": {"price"}}
             for k, v in members.items()}
    return rules.Context(table, score, set(), {}, lambda key, event: None)


def _spec(*rules_, otherwise=("neutral", "Neutral")):
    return {"version": 1, "rules": [{"id": i, "label": label, "when": when} for i, label, when in rules_],
            "otherwise": {"id": otherwise[0], "label": otherwise[1]}}


BULL = ("bullish", "Bullish", {"score": {"gte": 0.3}})
BEAR = ("bearish", "Bearish", {"score": {"lte": -0.3}})


def _rsi_group(outcome_spec=None, conditions=None):
    doc = {
        "schema": "angstrom.group/1", "name": "Test momentum", "lineage_version": 3,
        "score": {"method": "weighted_mean", "range": [-1, 1], "meaning": "test", "min_coverage": {"num": 1, "den": 2}},
        "members": [
            {"key": "ma_1d", "ref": {"id": "ma.position", "version": 1, "timeframe": "1D", "params": {}},
             "role": "score", "weight": 1, "when_unavailable": "exclude",
             "transform": {"kind": "clip", "version": 1, "field": "standard_score", "low": -1, "high": 1}},
            {"key": "macd_1d", "ref": {"id": "macd.level", "version": 1, "timeframe": "1D", "params": {}},
             "role": "score", "weight": 1, "when_unavailable": "exclude",
             "transform": {"kind": "clip", "version": 1, "field": "standard_score", "low": -1, "high": 1}},
            {"key": "rsi_1d", "ref": {"id": "rsi.level", "version": 1, "timeframe": "1D", "params": {}},
             "role": "condition"},
        ],
        "conditions": conditions or [],
    }
    if outcome_spec is not None:
        doc["outcomes"] = outcome_spec
    return doc


def _with(doc, **changes):
    out = copy.deepcopy(doc)
    out.update(changes)
    return out


def _group_result(outcome_id="bullish", raw=None, status="ok", qualified=None, score=0.5, conditions=()):
    raw = raw or outcome_id
    if qualified is None:
        qualified = status == "veto_unknown" and raw != "unknown"
    return {"status": status, "score": {"value": score}, "conditions": list(conditions),
            "outcome": {"id": outcome_id, "label": outcome_id.title(), "qualified": qualified, "status": status,
                        "raw": {"id": raw, "label": raw.title(), "rule": 0}}}


def _decide(rule, groups, **members):
    return decision.evaluate({"version": 1, "rule": rule}, groups, _rctx(None, **members))


def _set(groups: dict, standalone=(), decision_rule=None):
    doc = {"schema": "angstrom.set/1", "name": "Test set", "lineage_version": 3, "score": None,
           "groups": [{"key": k, "snapshot": g} for k, g in groups.items()], "standalone": list(standalone),
           "market_context": []}
    if decision_rule is not None:
        doc["decision"] = {"version": 1, "rule": decision_rule}
    return doc


def _frame_ctx(seed=1, days=420):
    frame = full_indicators(cf.synthetic_crypto(days=days, seed=seed).histories["1D"].raw)
    data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
    return DataContext("crypto", "x", candle_loader=lambda k, a, tf: data, now=frame.index[-1] + pd.Timedelta(days=1))


# ----------------------------------------------------------------------------- E1: outcomes

def test_01_first_true_rule_wins_and_otherwise_when_all_false():
    spec = _spec(BULL, BEAR)
    assert outcomes.raw_outcome(spec, _rctx(0.5))[:2] == ("bullish", "Bullish")
    assert outcomes.raw_outcome(spec, _rctx(-0.5))[:2] == ("bearish", "Bearish")
    assert outcomes.raw_outcome(spec, _rctx(0.1))[:2] == ("neutral", "Neutral")


def test_02_an_unknown_rule_stops_evaluation_before_a_later_true_rule():
    spec = _spec(("first", "First", {"member": "rsi", "lte": 70}), ("second", "Second", {"score": {"gte": 0}}))
    assert outcomes.raw_outcome(spec, _rctx(0.5, rsi=None))[0] == "unknown"
    assert outcomes.raw_outcome(spec, _rctx(0.5, rsi=40))[0] == "first"


def test_03_a_rule_false_on_one_all_line_falls_through_even_if_another_line_is_unknown():
    first = ("first", "First", {"all": [{"score": {"gte": 0.9}}, {"member": "rsi", "lte": 70}]})
    spec = _spec(first, ("second", "Second", {"score": {"gte": 0}}))
    assert outcomes.raw_outcome(spec, _rctx(0.5, rsi=None))[0] == "second"


def test_04_rule_order_is_the_priority_where_rules_overlap():
    wide = ("wide", "Wide", {"score": {"gte": 0}})
    narrow = ("narrow", "Narrow", {"score": {"gte": 0.4}})
    assert outcomes.raw_outcome(_spec(wide, narrow), _rctx(0.5))[0] == "wide"
    assert outcomes.raw_outcome(_spec(narrow, wide), _rctx(0.5))[0] == "narrow"


@pytest.mark.parametrize("status,expected,qualified", [
    ("ok", "bullish", False), ("vetoed", "vetoed", False), ("insufficient", "unknown", False),
    ("veto_unknown", "bullish", True)])
def test_05_group_status_gates_the_published_outcome(status, expected, qualified):
    out = outcomes.publish(_spec(BULL, BEAR), _rctx(0.5), status)
    assert (out["id"], out["qualified"], out["raw"]["id"], out["status"]) == (expected, qualified, "bullish", status)


def test_05b_outcomes_through_the_real_evaluator_follow_the_group_status():
    veto = [{"key": "rsi_high", "kind": "veto", "label": "RSI very high", "rule": {"member": "rsi_1d", "field": "rsi", "gte": 0}}]
    ctx = _frame_ctx()
    ok = sg.evaluate_group(_rsi_group(_spec(BULL, BEAR, ("always", "Always", {"score": {"gte": -1}}))), ctx)
    assert ok["status"] == "ok" and ok["outcome"]["id"] in ("bullish", "bearish", "always")
    vetoed = sg.evaluate_group(_rsi_group(_spec(BULL), conditions=veto), ctx)
    assert vetoed["status"] == "vetoed" and vetoed["outcome"]["id"] == "vetoed"


def test_06_reserved_and_duplicate_ids_are_refused_and_labels_can_be_renamed():
    for bad in (_spec(("unknown", "Unknown", {"score": {"gte": 0}})), _spec(("vetoed", "Vetoed", {"score": {"gte": 0}})),
                _spec(BULL, ("bullish", "Again", {"score": {"lte": 0}})), _spec(BULL, otherwise=("bullish", "N")),
                _spec(("Bull", "Bull", {"score": {"gte": 0}}))):
        assert sg.validate_group(_rsi_group(bad)), bad
    assert not sg.validate_group(_rsi_group(_spec(BULL, BEAR)))
    groups_a = {"g": _group_result("bullish")}
    renamed = copy.deepcopy(groups_a)
    renamed["g"]["outcome"]["label"] = "Strongly up"
    rule = {"group": "g", "outcome": {"eq": "bullish"}}
    assert _decide(rule, groups_a)["answer"] == _decide(rule, renamed)["answer"] == "yes"


# ----------------------------------------------------------------------------- E2: Set decisions

def test_07_qualified_outcomes_are_unknown_only_where_the_veto_could_change_the_answer():
    groups = {"g": _group_result("bullish", status="veto_unknown")}
    assert _decide({"group": "g", "outcome": {"eq": "bullish"}}, groups)["answer"] == "unknown"
    assert _decide({"group": "g", "outcome": {"eq": "bearish"}}, groups)["answer"] == "no"
    assert _decide({"group": "g", "outcome": {"in": ["bullish", "vetoed"]}}, groups)["answer"] == "yes"


def test_08_an_active_veto_makes_a_directional_outcome_false():
    groups = {"g": _group_result("vetoed", raw="bullish", status="vetoed")}
    assert _decide({"group": "g", "outcome": {"eq": "bullish"}}, groups)["answer"] == "no"


def test_09_not_of_unknown_stays_unknown_and_an_unknown_outcome_is_unknown():
    groups = {"g": _group_result("unknown", status="insufficient", score=None)}
    assert _decide({"group": "g", "outcome": {"eq": "bullish"}}, groups)["answer"] == "unknown"
    assert _decide({"not": {"group": "g", "outcome": {"eq": "bearish"}}}, groups)["answer"] == "unknown"
    assert _decide({"group": "g", "score": {"gte": 0}}, groups)["answer"] == "unknown"


def test_10_definite_no_with_a_missing_input_names_the_false_line():
    groups = {"trend": _group_result("neutral")}
    rule = {"all": [{"group": "trend", "outcome": {"eq": "bullish"}}, {"member": "sentiment", "gte": -20}]}
    out = _decide(rule, groups, sentiment=None)
    assert out["answer"] == "no"
    assert [d["text"] for d in out["decisive"]] == ["trend outcome is bullish"]
    assert out["decisive"][0]["reading"] == "neutral"


def test_11_unknown_names_the_missing_line_that_could_change_the_answer():
    groups = {"trend": _group_result("bullish")}
    rule = {"all": [{"group": "trend", "outcome": {"eq": "bullish"}}, {"member": "sentiment", "gte": -20}]}
    out = _decide(rule, groups, sentiment=None)
    assert out["answer"] == "unknown"
    assert [d["text"] for d in out["decisive"]] == ["sentiment ≥ -20"]


def test_12_any_groups_are_three_valued():
    groups = {"a": _group_result("bullish"), "b": _group_result("neutral"), "c": _group_result("unknown", score=None)}
    yes = {"group": "a", "outcome": {"eq": "bullish"}}
    no = {"group": "b", "outcome": {"eq": "bullish"}}
    unknown = {"group": "c", "outcome": {"eq": "bullish"}}
    assert _decide({"any": [no, yes, unknown]}, groups)["answer"] == "yes"
    assert _decide({"any": [no, no]}, groups)["answer"] == "no"
    out = _decide({"any": [no, unknown]}, groups)
    assert out["answer"] == "unknown" and [d["text"] for d in out["decisive"]] == ["c outcome is bullish"]


def _standalone(key, role, signal="sentiment.asset"):
    return {"key": key, "label": key, "role": role, "ref": {"id": signal, "version": 1, "timeframe": "1D", "params": {}}}


def test_13_context_items_are_refused_in_a_decision_and_condition_items_accepted():
    group = _rsi_group(_spec(BULL, BEAR))
    rule = {"all": [{"group": "g", "outcome": {"eq": "bullish"}}, {"member": "mood", "field": "score", "gte": -20}]}
    assert not sg.validate_set(_set({"g": group}, [_standalone("mood", "condition")], rule))
    errors = sg.validate_set(_set({"g": group}, [_standalone("mood", "context")], rule))
    assert any("role context" in e for e in errors), errors


def test_14_a_set_without_a_decision_is_not_scannable_and_gains_no_decision_key():
    plain = _set({"g": _rsi_group(_spec(BULL))})
    assert not sg.scannable(plain) and not sg.validate_set(plain)
    assert "decision" not in sg.evaluate_set(plain, _frame_ctx())
    assert sg.scannable(_set({"g": _rsi_group(_spec(BULL))}, decision_rule={"group": "g", "outcome": {"eq": "bullish"}}))


def test_15_outcome_predicates_need_an_embedded_version_with_outcomes():
    errors = sg.validate_set(_set({"g": _rsi_group()}, decision_rule={"group": "g", "outcome": {"eq": "bullish"}}))
    assert any("has no outcomes; embed a newer version" in e for e in errors), errors


def test_15b_unknown_cannot_be_tested_and_conditions_and_status_are_checked():
    veto = [{"key": "hot", "kind": "veto", "label": "hot", "rule": {"member": "rsi_1d", "field": "rsi", "gte": 80}}]
    g = _rsi_group(_spec(BULL, BEAR), conditions=veto)
    bad = [
        {"group": "g", "outcome": {"eq": "unknown"}},
        {"group": "g", "outcome": {"eq": "sideways"}},
        {"group": "g", "condition": "hot", "state": {"eq": "met"}},
        {"group": "g", "condition": "cold", "state": {"eq": "active"}},
        {"group": "g", "status": {"eq": "fine"}},
        {"group": "g", "score": {"gte": 30}},
        {"group": "nope", "status": {"eq": "ok"}},
        {"count_at_least": 1, "of": [{"group": "g", "status": {"eq": "ok"}}]},
    ]
    div = {"key": "div", "label": "div", "role": "condition",
           "ref": {"id": "ta.divergence.rsi", "version": 1, "timeframe": "1D", "params": {}}}
    errors = sg.validate_set(_set({"g": g}, [div], {"member": "div", "events": {"within_candles": 3}}))
    assert any("within_candles is not available" in e for e in errors), errors
    assert not sg.validate_set(_set({"g": g}, [div], {"member": "div", "events": {"direction": "bullish"}}))
    for rule in bad:
        assert sg.validate_set(_set({"g": g}, decision_rule=rule)), rule
    good = {"all": [{"group": "g", "condition": "hot", "state": {"eq": "clear"}}, {"group": "g", "status": {"in": ["ok"]}},
                    {"group": "g", "score": {"gte": 0.3}}, {"not": {"group": "g", "outcome": {"eq": "vetoed"}}}]}
    assert not sg.validate_set(_set({"g": g}, decision_rule=good))


def test_15c_a_set_decision_evaluates_end_to_end():
    g = _rsi_group(_spec(BULL, BEAR))
    rule = {"all": [{"group": "g", "status": {"eq": "ok"}}, {"not": {"group": "g", "outcome": {"eq": "vetoed"}}}]}
    out = sg.evaluate_set(_set({"g": g}, decision_rule=rule), _frame_ctx())
    group = out["groups"][0]["result"]
    assert out["decision"]["answer"] == ("yes" if group["status"] == "ok" else "no")
    assert {line["path"] for line in out["decision"]["lines"]} == {"decision.rule.all[0]", "decision.rule.all[1].not"}


# ----------------------------------------------------------------------------- E3: fields and scales

def _members_in_documents():
    keys = set()
    for doc in lattice_compat.documents().values():
        for g in [doc] if "members" in doc else [x["snapshot"] for x in doc.get("groups") or []]:
            keys |= {f"{m['ref']['id']}@{m['ref']['version']}" for m in g["members"]}
        keys |= {f"{i['ref']['id']}@{i['ref']['version']}" for i in doc.get("standalone") or []}
    return keys


def _numbers(value, desc_of, prefix=""):
    """(path, number) for every described numeric field in a value."""
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            out += _numbers(v, desc_of, f"{prefix}{k}.")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += _numbers(v, desc_of, f"{prefix}{i}.")
    else:
        path = prefix.rstrip(".")
        d = desc_of(path)
        if d and d["type"] == fields.NUMBER and isinstance(value, (int, float)) and not isinstance(value, bool):
            out.append((path, value, d))
    return out


def test_16_starter_and_example_members_are_described_and_real_values_sit_in_range():
    undescribed = {k for k in _members_in_documents() if not fields.described(k)}
    assert not undescribed, undescribed
    checked = 0
    for seed in (1, 2, 3):
        for days in (260, 420):
            ctx = _frame_ctx(seed, days)
            for key in fields.FIELDS:
                definition = REGISTRY.get(*key.split("@")[0:1], int(key.split("@")[1]))
                if not definition.scope == "asset" or "sentiment" in definition.requires:
                    continue
                ref = SignalRef.make(definition, "1D")
                res = evaluate([ref], ctx)[ref.instance_key]
                if res.status != "ok":
                    continue
                for path, value, desc in _numbers(res.value, lambda p, k=key: fields.field(k, p)):
                    assert fields.in_range(desc, value), (key, path, value, desc)
                    checked += 1
    assert checked > 200


def _fixed_range_cases():
    for key, table in fields.FIELDS.items():
        definition = REGISTRY.get(key.split("@")[0], int(key.split("@")[1]))
        if definition.scope != "asset":
            continue  # market-scope signals belong in a Set's market_context and are not usable in rules yet
        for path, desc in table.items():
            if desc["type"] == fields.NUMBER and desc["range"] != [None, None]:
                yield key, path.replace("*", "0"), desc


def _group_with(key, rule_field, rule):
    sid, version = key.split("@")
    doc = _rsi_group()
    doc["members"].append({"key": "probe", "ref": {"id": sid, "version": int(version), "timeframe": "1D", "params": {}},
                           "role": "condition"})
    doc["conditions"] = [{"key": "probe_rule", "kind": "confirmation", "label": "probe",
                          "rule": {"member": "probe", **({"field": rule_field} if rule_field else {}), **rule}}]
    return doc


@pytest.mark.parametrize("key,path,desc", list(_fixed_range_cases()))
def test_17_a_threshold_outside_each_fixed_range_is_refused(key, path, desc):
    low, high = desc["range"]
    outside = (high + 1) if high is not None else (low - 1)
    errors = sg.validate_group(_group_with(key, path or None, {"gte": outside}))
    assert any("outside that scale" in e for e in errors), (key, path, errors)
    inside = high if high is not None else low
    assert not sg.validate_group(_group_with(key, path or None, {"gte": inside})), (key, path)


def test_17b_a_standard_score_threshold_of_70_blocks_saving():
    errors = sg.validate_group(_group_with("ma.position@1", "standard_score", {"gte": 70}))
    assert any("standard score, -1 to 1; 70 is outside" in e for e in errors), errors


def test_18_type_mismatches_and_missing_fields_are_refused():
    cases = [
        ("volume.heavy_candle@1", "standard_score", {"eq": True}, "is a number"),
        ("obv.balance@1", "has_volume", {"gte": 1}, "yes/no reading"),
        ("ichimoku.position@1", "cloud", {"gte": 0}, "label reading"),
        ("ichimoku.position@1", "cloud", {"eq": "over"}, "is one of"),
        ("trend.direction@1", None, {"eq": "sideways"}, "is one of"),
        ("rsi.level@1", "rsi_value", {"gte": 50}, "not a readable field"),
        ("rsi.level@1", None, {"gte": 50}, "name a field"),
        ("ta.divergence.rsi@1", None, {"eq": "x"}, "use an events filter"),
        ("rsi.level@1", "rsi", {"events": {"direction": "bullish"}}, "not a list of events"),
    ]
    for key, path, rule, words in cases:
        errors = sg.validate_group(_group_with(key, path, rule))
        assert any(words in e for e in errors), (key, path, rule, errors)
    assert not sg.validate_group(_group_with("obv.balance@1", "has_volume", {"eq": True}))
    assert not sg.validate_group(_group_with("ichimoku.position@1", "cloud", {"in": ["above", "inside"]}))


def test_19_display_thresholds_convert_exactly_and_out_of_scale_scores_are_refused():
    assert score_from_display("+30") == 0.3 and score_from_display("−30") == -0.3 and score_from_display(100) == 1.0
    assert score_to_display(0.3) == "+30" and score_to_display(-0.3) == "−30"
    for bad in ("+130", "abc", ""):
        with pytest.raises(ValueError):
            score_from_display(bad)
    errors = sg.validate_group(_rsi_group(_spec(("hot", "Hot", {"score": {"gte": 30}}))))
    assert any("outside the Group score range" in e for e in errors), errors
    assert not sg.validate_group(_rsi_group(_spec(("hot", "Hot", {"score": {"gte": score_from_display("+30")}}))))


# ----------------------------------------------------------------------------- compatibility

def test_20_documents_without_the_new_keys_hash_validate_and_evaluate_exactly_as_before():
    recorded = json.loads(lattice_compat.FIXTURE.read_text(encoding="utf-8"))
    now = json.loads(json.dumps(lattice_compat.snapshot(), sort_keys=True))
    assert now["hashes"] == recorded["hashes"] and now["valid"] == recorded["valid"]   # exact
    assert lattice_compat.differences(now, recorded) == []      # scores within 1e-9, everything else exact


def test_21_no_certified_calculation_changed():
    record = certification.load()
    assert record["code_sha256"] == certification.code_hash()
    assert "signal_library/fields.py" not in certification.CODE_FILES


def test_live_results_gain_keys_only_for_documents_that_define_them():
    ctx = _frame_ctx()
    plain = sg.evaluate_group(_rsi_group(), ctx)
    assert "outcome" not in plain
    with_outcomes = sg.evaluate_group(_rsi_group(_spec(BULL, BEAR)), ctx)
    assert set(with_outcomes) - set(plain) == {"outcome"}
    assert {k: v for k, v in with_outcomes.items() if k not in ("outcome", "evaluated_at", "as_of")} == \
        {k: v for k, v in plain.items() if k not in ("evaluated_at", "as_of")}
