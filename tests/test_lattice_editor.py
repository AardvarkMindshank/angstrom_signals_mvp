"""Lattice Group editor (docs/design/lattice_prism.md §7, build stage 4). Synthetic data only."""

from __future__ import annotations

import pandas as pd
import pytest

import lattice_component_check as harness
import lattice_editor as le
import prism
import signal_groups as sg
from signal_library import DataContext, engine
from signal_library import certify as cf
from tests.replay_helpers import full_indicators


def setup_function(_):
    engine.clear_cache()


def _m(key, sid, role, tf="1D"):
    return {"key": key, "id": sid, "version": 1, "timeframe": tf, "role": role}


def _model(members, rules=()):
    return {"name": "Test", "question": "", "members": list(members), "rules": list(rules),
            "otherwise": {"id": "neutral", "label": "Neutral"}}


def _rule(label, *clauses, joiner="all"):
    return {"id": le.re.sub(r"[^a-z0-9]+", "_", label.lower()), "label": label, "joiner": joiner, "clauses": list(clauses)}


def _c(operand, op, value=""):
    return {"operand": operand, "op": op, "value": value}


def test_catalogue_offers_described_asset_signals_and_knows_which_can_score():
    cat = {s["id"]: s for s in le.catalogue()}
    assert "sentiment.market" not in cat and "flows.btc_etf" not in cat        # market context, not members
    assert cat["rsi.level"]["can_score"] and cat["trend.direction"]["can_score"]
    assert not cat["ta.divergence.rsi"]["can_score"] and not cat["sentiment.asset"]["can_score"]
    assert cat["sentiment.asset"]["badge"] == "History from Nov 2026"
    rsi = {o["field"]: o for o in cat["rsi.level"]["operands"]}
    assert rsi["rsi"]["scale"] == "RSI (14), 0 to 100" and rsi["standard_score"]["scale"] == "standard score, -1 to 1"


@pytest.mark.parametrize("alias", ["starter:trend", "starter:stretch", "starter:flow"])
def test_starters_round_trip_through_the_editor(alias):
    for doc in (sg.starter(alias), prism.labelled_starter(alias)):
        model, why = le.from_document(doc)
        assert why is None
        back = le.to_document(model)
        assert sg.validate_group(back) == []
        assert [(m["ref"], m["role"], m.get("transform")) for m in back["members"]] == \
            [(m["ref"], m["role"], m.get("transform")) for m in doc["members"]]
        assert back.get("outcomes") == doc.get("outcomes")


def test_groups_the_editor_cannot_show_yet_are_refused_with_a_reason():
    model, why = le.from_document(sg.starter("starter:trend-confirmation"))
    assert model is None and "confirmations or vetoes" in why


def test_the_screen_can_only_hand_back_what_the_editor_offers():
    raw = {"name": "x" * 200, "members": [_m("bad key!", "rsi.level", "boss", "9y"), {"id": "evil.signal"}],
           "rules": [{"label": "Bullish!", "clauses": [_c("score", "gte", "+30"), {"op": "drop table"}]}] * 20,
           "otherwise": {"label": "3 way"}}
    model = le.clean_model(raw)
    assert len(model["name"]) == 80 and len(model["rules"]) == le.MAX_RULES
    assert model["members"] == [_m("rsi_level_1d", "rsi.level", "score")]
    assert model["rules"][0]["clauses"] == [_c("score", "gte", "+30")] and model["rules"][0]["id"] == "bullish"
    assert model["otherwise"] == {"id": "l_3_way", "label": "3 way"}


def _blocks(model):
    return " | ".join(le.checks(model)["blocks"])


def _warns(model):
    return " | ".join(le.checks(model)["warnings"])


def test_blocks_stop_saving_with_plain_reasons():
    assert "Add at least one signal" in _blocks(_model([]))
    assert "no standard score" in _blocks(_model([_m("div", "ta.divergence.rsi", "score")]))
    rsi = _m("rsi", "rsi.level", "score")
    assert "outside the Group score scale, −100 to +100" in _blocks(_model([rsi], [_rule("Hot", _c("score", "gte", "130"))]))
    assert "'abc' is not a number" in _blocks(_model([rsi], [_rule("Hot", _c("score", "gte", "abc"))]))
    assert "RSI (14) (1D) standard score runs standard score, -1 to 1; 70 is outside" in \
        _blocks(_model([rsi], [_rule("Hot", _c("rsi:standard_score", "gte", "70"))]))
    obv = _m("obv", "obv.balance", "condition")
    assert "yes/no reading" in _blocks(_model([rsi, obv], [_rule("Hot", _c("obv:has_volume", "gte", "1"))]))
    ctx = _m("ctx", "volume.cmf", "context")
    assert "marked Context" in _blocks(_model([rsi, ctx], [_rule("Hot", _c("ctx:", "gte", "0"))]))
    assert "no longer in the Group" in _blocks(_model([rsi], [_rule("Hot", _c("gone:rsi", "gte", "1"))]))
    assert "same label" in _blocks(_model([rsi], [_rule("Hot", _c("score", "gte", "+30")), _rule("Hot", _c("score", "lte", "-30"))]))


def test_warnings_explain_without_blocking():
    ma, ich = _m("ma", "ma.position", "score"), _m("ich", "ichimoku.position", "score")
    macd, rsi = _m("macd", "macd.level", "score"), _m("rsi", "rsi.level", "condition")
    assert "all measure trend" in _warns(_model([ma, ich, macd]))
    assert "price and volume alone" in _warns(_model([ma, ich, macd]))
    assert "no rule uses it" in _warns(_model([ma, rsi]))
    assert "tested again in rule 1" in _warns(_model([ma], [_rule("Up", _c("ma:standard_score", "gte", "0"))]))
    assert "different timeframes (1D, 4h)" in _warns(_model([ma, _m("ma4", "ma.position", "score", "4h")]))
    assert "sentiment history starts" in _warns(_model([ma, _m("mood", "sentiment.asset", "condition")]))
    overlap = _model([ma], [_rule("Up", _c("score", "gte", "+30"), _c("score", "gte", "+10"), joiner="any"),
                            _rule("Down", _c("score", "lte", "-30"))])
    assert "uses OR" in _warns(overlap) and not _blocks(overlap)


def test_what_the_editor_saves_evaluates_and_can_be_scanned():
    ma, rsi = _m("ma", "ma.position", "score"), _m("rsi", "rsi.level", "condition")
    model = _model([ma, rsi], [_rule("Bullish", _c("score", "gte", "+30"), _c("rsi:rsi", "lte", "70")),
                               _rule("Bearish", _c("score", "lte", "−30"))])
    assert le.checks(model)["blocks"] == []
    doc = le.to_document(model)
    assert doc["outcomes"]["rules"][0]["when"] == {"all": [{"score": {"gte": 0.3}}, {"member": "rsi", "field": "rsi", "lte": 70.0}]}
    frame = full_indicators(cf.synthetic_crypto(days=420, seed=3).histories["1D"].raw)
    data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
    ctx = DataContext("crypto", "x", candle_loader=lambda k, a, tf: data, now=frame.index[-1] + pd.Timedelta(days=1))
    result = sg.evaluate_group(doc, ctx)
    assert result["status"] == "ok" and result["outcome"]["id"] in ("bullish", "bearish", "neutral")
    as_set = {"schema": "angstrom.set/1", "name": "From the editor", "lineage_version": 3, "score": None,
              "groups": [{"key": "g", "snapshot": doc}], "standalone": [], "market_context": [],
              "decision": {"version": 1, "rule": {"group": "g", "outcome": {"eq": "bullish"}}}}
    assert sg.validate_set(as_set) == [] and sg.scannable(as_set)


def test_description_and_member_tags():
    model = _model([_m("ma", "ma.position", "score"), _m("mood", "sentiment.asset", "condition")],
                   [_rule("Bullish", _c("score", "gte", "+30"), _c("mood:score", "gte", "-20"))])
    text = le.describe(model)
    assert text.startswith("Test averages 1 reading (Moving averages (50, 200) (1D))")
    assert "Rule 1: Bullish when the Group score is at least +30 and Asset headline sentiment (1D) score is at least -20." in text
    tags = le.state_for_screen(model)["member_tags"]
    assert tags == {"ma": "1D · last closed candle", "mood": "Latest score at the time"}


def test_the_browser_harness_is_built_from_the_real_component():
    page = harness.page(harness.harness_model())
    assert "window.renderLattice = function(component)" in page and "export default" not in page
    assert '"catalogue"' in page and "innerHTML" not in page.split("<script>", 1)[1]


def test_lattice_tab_renders_inside_streamlit():
    testing = pytest.importorskip("streamlit.testing.v1")
    from tests.test_prism import _app

    app = testing.AppTest.from_function(_app, default_timeout=120)
    app.run()
    assert not app.exception


# ----------------------------------------------------------------------------------------------- Set editor

import lattice_sets as ls  # noqa: E402


def _saved():
    return [{"id": "11111111-1111-1111-1111-111111111111", "kind": "group", "name": "Trend (with labels)", "owner_id": "me",
             "starter_alias": None, "current_version": 1,
             "versions": [{"version": 1, "body": prism.labelled_starter("starter:trend")}]},
            {"id": "22222222-2222-2222-2222-222222222222", "kind": "group", "name": "Flow", "owner_id": None,
             "starter_alias": "starter:flow", "current_version": 1,
             "versions": [{"version": 1, "body": sg.starter("starter:flow")}]}]


def _set_model(lines, standalone=()):
    choices = ls.group_choices(_saved(), "me")
    raw = {"name": "Daily check", "groups": [{"source": k} for k in choices], "standalone": list(standalone),
           "lines": lines}
    return ls.clean_model(raw, choices), choices


def test_set_groups_are_embedded_exactly_with_their_provenance():
    model, choices = _set_model([{"target": "outcome", "group": "trend_with_labels", "op": "is", "value": "bullish"}])
    doc = ls.to_document(model, choices)
    assert [g["key"] for g in doc["groups"]] == ["trend_with_labels", "flow"]
    assert doc["groups"][0]["snapshot"] == prism.labelled_starter("starter:trend")
    assert doc["groups"][1]["provenance"] == {"source_config": "starter:flow", "source_version": 1}
    assert sg.validate_set(doc) == [] and sg.scannable(doc)


def test_set_decisions_with_any_boxes_not_and_scores_round_trip():
    lines = [{"target": "outcome", "group": "trend_with_labels", "op": "is_not", "value": "bearish"},
             {"any": [{"target": "score", "group": "flow", "op": "gte", "value": "+10"},
                      {"target": "member", "member": "score_1d", "field": "score", "op": "gte", "value": "-20"}]}]
    model, choices = _set_model(lines, [{"key": "score_1d", "id": "sentiment.asset", "role": "condition"}])
    doc = ls.to_document(model, choices)
    assert doc["decision"]["rule"] == {"all": [
        {"not": {"group": "trend_with_labels", "outcome": {"eq": "bearish"}}},
        {"any": [{"group": "flow", "score": {"gte": 0.1}}, {"member": "score_1d", "field": "score", "gte": -20.0}]}]}
    back, why = ls.from_document(doc, choices)
    assert why is None and back == model
    assert "says Yes when Trend (with labels) v1 label is not Bearish, and any of (Flow v1 score is at least +10" in \
        ls.describe(model, choices)


def test_set_checks():
    model, choices = _set_model([])
    assert "no decision yet, so Prism cannot scan it" in " ".join(ls.checks(model, choices)["warnings"])
    bad, choices = _set_model([{"target": "score", "group": "flow", "op": "gte", "value": "130"}])
    assert "outside the Group score scale, −100 to +100" in " ".join(ls.checks(bad, choices)["blocks"])
    nan, choices = _set_model([{"target": "score", "group": "flow", "op": "gte", "value": "lots"}])
    assert "is not a number" in " ".join(ls.checks(nan, choices)["blocks"])
    ctx, choices = _set_model([{"target": "member", "member": "rsi_1d", "field": "rsi", "op": "gte", "value": "50"}],
                              [{"key": "rsi_1d", "id": "rsi.level", "role": "context"}])
    assert "Context item" in " ".join(ls.checks(ctx, choices)["blocks"])
    unused, choices = _set_model([{"target": "status", "group": "flow", "op": "is", "value": "ok"}],
                                 [{"key": "rsi_1d", "id": "rsi.level", "role": "condition"}])
    assert "no line uses it" in " ".join(ls.checks(unused, choices)["warnings"])
    assert ls.checks(ls.clean_model(_set_model([])[0], {}), {})["blocks"] == ["Add at least one Group or signal."]
    orphan, _ = _set_model([{"target": "status", "group": "flow", "op": "is", "value": "ok"}])
    assert "can no longer be read" in " ".join(ls.checks(orphan, {})["blocks"])        # never a crash
    assert ls.state_for_screen(orphan, {})["can_save"] is False


def test_set_screen_input_is_cleaned():
    choices = ls.group_choices(_saved(), "me")
    raw = {"groups": [{"source": "saved:not-mine:1"}, {"source": next(iter(choices)), "key": "bad key"}],
           "standalone": [{"id": "evil"}], "lines": [{"target": "drop"}, {"any": [{"target": "outcome", "group": "nope"}]}]}
    model = ls.clean_model(raw, choices)
    assert [g["key"] for g in model["groups"]] == ["trend_with_labels"] and model["standalone"] == [] and model["lines"] == []
