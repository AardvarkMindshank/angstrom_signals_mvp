import copy
import json
import pathlib

import numpy as np
import pandas as pd
import pytest

import signal_groups as sg
import signal_library as sl
from signal_groups import rules, transforms
from signal_groups.transforms import UNKNOWN
from signal_library import DataContext, SignalResult, engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "docs" / "design" / "examples"


def setup_function(_):
    engine.clear_cache()


def ex(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- starters

@pytest.mark.parametrize("alias", ["starter:reversal-evidence", "starter:trend-confirmation"])
def test_starters_are_valid_and_match_the_design(alias):
    doc = sg.starter(alias)
    assert sg.validate_group(doc) == []
    design = {"starter:trend-confirmation": "group_trend_confirmation.json",
              "starter:reversal-evidence": "group_reversal_evidence.json"}[alias]
    assert doc == ex(design)


def test_lineage_package_copy_matches_design():
    assert json.loads((ROOT / "signal_groups" / "lineage_v2.json").read_text()) == ex("lineage.json")


# ----------------------------------------------------------------------------- design fixtures, executed

@pytest.mark.parametrize("case", ex("transform_fixtures.json")["cases"], ids=lambda c: f"{c['kind']}:{c['input']}")
def test_transform_fixtures(case):
    t = {"kind": case["kind"], "version": 1, **case["params"]}
    if case["expected"] == "invalid_config":
        assert transforms.config_errors(t)
        return
    assert transforms.config_errors(t) == []
    value = float("nan") if case["input"] == "NaN" else case["input"]
    out, flags = transforms.apply(t, value)
    assert out == (UNKNOWN if case["expected"] == "unknown" else pytest.approx(case["expected"]))
    if case.get("flag"):
        assert case["flag"] in flags


@pytest.mark.parametrize("case", ex("rule_fixtures.json")["cases"], ids=lambda c: c["name"])
def test_counting_fixtures(case):
    items = [(UNKNOWN if i["value"] == "unknown" else i["value"], set(i["support"]), set(i["roots"]))
             for i in case["items"]]
    expected = UNKNOWN if case["expected"] == "unknown" else case["expected"]
    assert rules.count(case["op"], case["k"], items) == expected


# ----------------------------------------------------------------------------- validator refusals

def _trend():
    return sg.starter("starter:trend-confirmation")


def _rev():
    return sg.starter("starter:reversal-evidence")


def _errors(doc):
    return " | ".join(sg.validate_group(doc))


def test_refuses_context_member_in_a_rule():
    doc = _rev()
    doc["conditions"][0]["rule"]["of"].append({"member": "cmf_4h", "gte": 0})
    assert "role context" in _errors(doc)


def test_refuses_k_above_items_and_unsatisfiable_source_counts():
    doc = _rev()
    doc["conditions"][0]["rule"]["count_at_least"] = 4
    assert "k must be" in _errors(doc)
    doc = _rev()
    rule = doc["conditions"][0]["rule"]
    rule["count_distinct_sources_at_least"] = rule.pop("count_at_least")
    assert "unsatisfiable" in _errors(doc)


def test_refuses_bad_transforms_weights_and_coverage():
    doc = _trend()
    doc["members"][0]["transform"] = {"kind": "bands", "version": 1, "bands": [{"from": None, "to": 0, "value": -1},
                                                                             {"from": 1, "to": None, "value": 1}]}
    assert "gap or overlap" in _errors(doc)
    doc = _trend()
    doc["members"][0]["weight"] = -1
    assert "weight" in _errors(doc)
    doc = _trend()
    doc["score"]["min_coverage"] = {"num": 3, "den": 2}
    assert "min_coverage" in _errors(doc)
    doc = _trend()
    for m in doc["members"]:
        if m["role"] == "score":
            m["weight"] = 0
    assert "weight above 0" in _errors(doc)


def test_refuses_unknown_signals_market_signals_and_fixed_policies():
    doc = _trend()
    doc["members"][0]["ref"]["id"] = "no.such.signal"
    assert "unknown signal" in _errors(doc)
    doc = _trend()
    doc["members"][3]["ref"] = {"id": "flows.btc_etf", "version": 1, "timeframe": "1D", "params": {}}
    assert "market context" in _errors(doc)
    doc = _trend()
    doc["members"][3]["when_unavailable"] = "exclude"
    assert "fixed" in _errors(doc)


def test_refuses_deep_rules_and_score_predicates_without_a_score():
    doc = _rev()
    rule = {"member": "breaks_4h", "events": {"direction": "bullish"}}
    for _ in range(7):
        rule = {"not": rule}
    doc["conditions"][0]["rule"] = rule
    assert "deeper" in _errors(doc)
    doc = _rev()
    doc["conditions"][0]["rule"] = {"score": {"gte": 0.5}}
    assert "without a score" in _errors(doc)


# ----------------------------------------------------------------------------- evaluator on hand-made results

def _frame(n=80):
    index = pd.date_range(end="2026-11-03 08:00", periods=n, freq="4h", tz="UTC")
    close = np.linspace(100, 120, n)
    df = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1.0}, index=index)
    df["forming"] = False
    return df


def _ctx():
    frame = _frame()
    return DataContext("crypto", "bitcoin", candle_loader=lambda k, a, tf: {"frame": frame, "session": None, "source": "t"})


def _result(value, status="ok"):
    return SignalResult(ref={}, subject="crypto:bitcoin", status=status, value=value, confirmation="confirmed",
                        observed_at="2026-11-03T04:00:00+00:00", available_at="2026-11-03T08:00:00+00:00")


def _results(doc, values: dict):
    out = {}
    for m in doc["members"]:
        r = m["ref"]
        ref = sl.SignalRef.make(sl.REGISTRY.get(r["id"], r["version"]), r["timeframe"], **r["params"])
        v = values.get(m["key"], "MISSING")
        out[ref.instance_key] = _result(None, "missing_data") if v == "MISSING" else _result(v)
    return out


TREND_OK = {"trend_1d": "up", "trend_4h": "up", "structure_1d": {"structure": "down"}, "momentum_4h": "up",
            "regime_1d": {"state": "trending"}}


def _eval(doc, values, **kw):
    return sg.evaluate_group(doc, _ctx(), results=_results(doc, values), **kw)


def test_coverage_worked_cases():
    doc = _trend()
    r = _eval(doc, TREND_OK)
    assert r["score"]["value"] == pytest.approx(1 / 3) and r["status"] == "ok"
    two = {**TREND_OK, "structure_1d": "MISSING", "trend_4h": "mixed"}
    r = _eval(doc, two)
    assert r["score"]["value"] == pytest.approx(0.5)
    assert r["score"]["observed_coverage"] == pytest.approx(2 / 3)
    one = {**TREND_OK, "structure_1d": "MISSING", "trend_4h": "MISSING"}
    r = _eval(doc, one)
    assert r["score"]["value"] is None and r["score"]["withheld"] == "below_min_coverage" and r["status"] == "insufficient"
    neutral = copy.deepcopy(doc)
    neutral["members"][2]["when_unavailable"] = "neutral"
    r = _eval(neutral, {**TREND_OK, "structure_1d": "MISSING"})
    assert r["score"]["value"] == pytest.approx(2 / 3)
    assert r["score"]["weights"] == {"enabled": 3.0, "observed": 2.0, "imputed": 1.0}


def test_transform_unknown_follows_the_member_policy():
    doc = _trend()
    doc["members"][2]["when_unavailable"] = "neutral"
    r = _eval(doc, {**TREND_OK, "structure_1d": {"structure": "unknown"}})  # maps to null -> unknown
    row = next(m for m in r["members"] if m["key"] == "structure_1d")
    assert row["state"] == "imputed" and row["unobserved_reason"] == "transform_unknown"


def test_missing_regime_makes_the_veto_unknown():
    r = _eval(_trend(), {**TREND_OK, "structure_1d": {"structure": "up"}, "regime_1d": "MISSING"})
    states = {c["key"]: c["state"] for c in r["conditions"]}
    assert states == {"bullish_confirmed": "met", "bearish_confirmed": "not_met", "ranging_veto": "unknown"}
    assert r["status"] == "veto_unknown"
    r = _eval(_trend(), {**TREND_OK, "regime_1d": {"state": "ranging"}})
    assert r["status"] == "vetoed"


def test_reversal_counts_compound_items_and_unknowns():
    doc = _rev()
    div = {"events": [{"type": "regular_bullish", "status": "confirmed", "confirmed_at": "2026-11-02T00:00:00+00:00"}]}
    none = {"events": []}
    choch = {"events": [{"kind": "CHoCH", "direction": "bullish", "confirmed_at": "2026-11-02T12:00:00+00:00"}]}
    near = {"support": [{"distance_atr": 0.5}], "resistance": []}
    r = _eval(doc, {"rsi_div_4h": div, "macd_div_4h": div, "breaks_4h": none, "zones_1d": near, "cmf_4h": 0.1})
    assert {c["key"]: c["state"] for c in r["conditions"]}["bullish_reversal_setup"] == "met"
    # Only the divergence item is true; zones unavailable -> unknown.
    r = _eval(doc, {"rsi_div_4h": div, "macd_div_4h": none, "breaks_4h": none, "zones_1d": "MISSING", "cmf_4h": 0.1})
    assert {c["key"]: c["state"] for c in r["conditions"]}["bullish_reversal_setup"] == "unknown"
    # CHoCH older than 20 candles does not count (confirmed 40 candles back).
    old = {"events": [{"kind": "CHoCH", "direction": "bullish", "confirmed_at": "2026-10-27T00:00:00+00:00"}]}
    r = _eval(doc, {"rsi_div_4h": div, "macd_div_4h": none, "breaks_4h": old, "zones_1d": {"support": [], "resistance": []},
                    "cmf_4h": 0.1})
    assert {c["key"]: c["state"] for c in r["conditions"]}["bullish_reversal_setup"] == "unknown"  # zone path missing
    r = _eval(doc, {"rsi_div_4h": div, "macd_div_4h": none, "breaks_4h": choch, "zones_1d": {"support": [], "resistance": []},
                    "cmf_4h": 0.1})
    assert {c["key"]: c["state"] for c in r["conditions"]}["bullish_reversal_setup"] == "met"


def test_expired_and_invalidated_divergences_do_not_count():
    doc = _rev()
    gone = {"events": [{"type": "regular_bullish", "status": "expired"}, {"type": "regular_bullish", "status": "invalidated"}],
            "developing": [{"type": "regular_bullish", "status": "developing"}]}
    r = _eval(doc, {"rsi_div_4h": gone, "macd_div_4h": gone, "breaks_4h": {"events": []},
                    "zones_1d": {"support": [{"distance_atr": 3}], "resistance": [{"distance_atr": 3}]}, "cmf_4h": 0})
    assert {c["key"]: c["state"] for c in r["conditions"]}["bullish_reversal_setup"] == "not_met"


def test_diagnostics_duplicates_and_source_note():
    doc = _trend()
    doc["members"].append({**copy.deepcopy(doc["members"][0]), "key": "trend_1d_again"})
    r = _eval(doc, {**TREND_OK, "trend_1d_again": "up"})
    assert ["trend_1d", "trend_1d_again"] in r["diagnostics"]["duplicates"]
    assert "price" in r["diagnostics"]["source_separation"]["note"]
    assert r["diagnostics"]["known_redundancy"]


def test_point_in_time_is_refused_and_invalid_docs_are_not_evaluated():
    assert sg.evaluate_group(_trend(), _ctx(), data_mode="point_in_time")["status"] == "unsupported"
    bad = _trend()
    bad["schema"] = "nope"
    assert sg.evaluate_group(bad, _ctx())["status"] == "invalid"


def test_member_results_keep_full_signal_metadata():
    r = _eval(_trend(), TREND_OK)
    sig = r["members"][0]["signal"]
    for field in ("status", "confirmation", "observed_at", "available_at", "backfilled", "provenance", "evidence"):
        assert field in sig
    json.dumps(r)


def test_starters_run_end_to_end_on_synthetic_candles():
    from tests.test_signal_library_ta import _ctx as full_ctx
    for alias in sg.STARTERS:
        r = sg.evaluate_group(sg.starter(alias), full_ctx())
        assert r["status"] in ("ok", "vetoed", "veto_unknown", "insufficient")
        assert all(c["state"] in ("met", "not_met", "unknown", "active", "clear") for c in r["conditions"])


# ----------------------------------------------------------------------------- Sets

def _set():
    return ex("set_multi_timeframe.json")


def test_design_set_is_valid_and_hashes_match():
    doc = _set()
    assert sg.validate_set(doc) == []
    for g in doc["groups"]:
        assert g["provenance"]["content_sha256"] == sg.content_sha256(g["snapshot"])


def test_set_validator_refusals():
    doc = _set()
    doc["score"] = {"method": "weighted_mean"}
    assert any("Set scores" in e for e in sg.validate_set(doc))
    doc = _set()
    doc["market_context"][0]["data_modes"] = ["live", "point_in_time"]
    assert any("current context only" in e for e in sg.validate_set(doc))
    doc = _set()
    doc["groups"][0]["snapshot"]["members"][0]["weight"] = -3
    assert any(e.startswith("trend:") for e in sg.validate_set(doc))
    doc = _set()
    doc["standalone"].append({"key": "etf", "ref": {"id": "flows.btc_etf", "version": 1, "timeframe": "1D", "params": {}},
                              "role": "context"})
    assert any("market context" in e for e in sg.validate_set(doc))


def test_set_evaluates_groups_once_and_reports_shared_sources():
    from tests.test_signal_library_ta import _ctx as full_ctx
    calls = []

    def market(scope):
        calls.append(scope)
        return DataContext("market", scope.split(":")[1], flows_loader=lambda *a: {"error": "none stored"})

    r = sg.evaluate_set(_set(), full_ctx(), market_context=market)
    assert r["status"] == "ok" and r["score"] is None
    assert [g["key"] for g in r["groups"]] == ["trend", "reversal"]
    assert r["diagnostics"]["sources_by_part"]["price"] == sorted(
        ["trend", "reversal", "standalone:alignment", "standalone:zones_4h"])
    assert calls == ["market:bitcoin"]
    assert r["market_context"][0]["signal"]["status"] == "missing_data"
    json.dumps(r)


def test_set_skips_crypto_context_for_shares():
    frame = _frame(400)
    ctx = DataContext("equity", "AAPL", candle_loader=lambda k, a, tf: {"frame": frame, "session": None, "source": "t"})
    r = sg.evaluate_set(_set(), ctx, market_context=lambda s: None)
    assert r["market_context"][0]["skipped"].startswith("applies to crypto")


def test_set_point_in_time_refused():
    assert sg.evaluate_set(_set(), _ctx(), data_mode="point_in_time")["status"] == "unsupported"
