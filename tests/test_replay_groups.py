"""Stage 3: Groups and Sets at a past time T (docs/design/point_in_time.md, section 5)."""

import copy
import json

import pandas as pd
import pytest

import signal_groups as sg
import signal_groups_inspector as gi
from signal_groups import replay as gr
from signal_library import REGISTRY, DataContext, certification, engine
from signal_library import certify as cf
from signal_library import replay as rp
from tests.replay_helpers import simple_indicators

ADMIN = {"evaluated_at", "as_of", "computed_at"}
PIT_ONLY = {"replay_mode", "completeness", "replay_availability", "data_mode"}


@pytest.fixture(autouse=True)
def certified(monkeypatch):
    """A current certification record: every candle and flow signal certified (derivatives never are)."""
    record = {"suite_version": certification.SUITE_VERSION, "code_sha256": certification.code_hash(), "signals": {}}
    for d in REGISTRY.latest():
        if "derivatives" in d.requires:
            continue
        record["signals"][d.key] = {tf: {"algorithm": "certified", "slice_equivalent": False} for tf in d.timeframes}
    monkeypatch.setattr(certification, "load", lambda: record)
    engine.clear_cache()
    yield record
    engine.clear_cache()


@pytest.fixture(scope="module")
def coin():
    return cf.synthetic_crypto(days=300, seed=3)


def _run(ds, mode=rp.DISPLAY):
    return rp.ReplayRun(mode, ds.candles, indicators=simple_indicators)


def _cutoff(ds, back=20):
    return pd.Timestamp(int(ds.histories["1D"].ends[-back]), tz="UTC")


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in ADMIN | PIT_ONLY}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _with_derivatives_veto():
    doc = sg.starter("starter:trend-confirmation")
    doc["members"].append({"key": "funding_1h", "label": "Funding", "role": "condition", "category": "positioning",
                           "ref": {"id": "positioning.oi_price", "version": 1, "timeframe": "1h", "params": {}}})
    doc["conditions"].append({"key": "crowded_veto", "label": "Funding is extreme", "kind": "veto",
                              "rule": {"member": "funding_1h", "field": "funding_latest", "gte": 0.1}})
    assert sg.validate_group(doc) == []
    return doc


# ------------------------------------------------------------------------------------------- Groups at T

@pytest.mark.parametrize("alias", sorted(sg.STARTERS))
def test_replayed_group_equals_the_live_group_on_data_cut_at_t(coin, alias):
    """The Group engine at T, through a replay, gives exactly what it gives live on data physically cut at T."""
    t = _cutoff(coin)
    replayed = sg.evaluate_group(sg.starter(alias), _run(coin).context("crypto", coin.asset_id, t),
                                 data_mode="point_in_time", as_of=t)
    frames = {tf: {"frame": simple_indicators(cf.reference_cut(h, t)).assign(forming=False), "session": None,
                   "source": h.source["provider"]} for tf, h in coin.histories.items()}
    engine.clear_cache()
    live = sg.evaluate_group(sg.starter(alias), DataContext("crypto", coin.asset_id, now=t,
                                                            candle_loader=lambda k, a, tf: frames[tf]))
    assert _strip(json.loads(json.dumps(replayed, default=str))) == _strip(json.loads(json.dumps(live, default=str)))
    assert replayed["as_of"] == t.isoformat() and replayed["data_mode"] == "point_in_time"
    assert replayed["completeness"]["label"] == "complete"
    assert all(m["replay_availability"] == "replayable" for m in replayed["members"])


def test_missing_member_makes_the_result_partial_and_an_unknown_veto_is_qualified(coin):
    t = _cutoff(coin)
    r = sg.evaluate_group(_with_derivatives_veto(), _run(coin).context("crypto", coin.asset_id, t),
                          data_mode="point_in_time", as_of=t)
    assert r["status"] == "veto_unknown"
    c = r["completeness"]
    assert c["label"] == "partial" and c["qualified"]
    [missing] = c["missing"]
    assert missing["member"] == "funding_1h" and missing["reason"] == "not_replayable"
    assert missing["critical"] and missing["vetoes_unknown"] == ["crowded_veto"]
    assert any("veto could not be checked" in n for n in c["notes"])
    # The score itself is unchanged by a missing condition-only member.
    assert r["score"]["value"] is not None


def test_missing_score_members_are_counted_by_the_existing_coverage_rules(coin):
    t = _cutoff(coin)
    doc = sg.starter("starter:trend-confirmation")
    run = rp.ReplayRun(rp.DISPLAY, lambda k, a, tf: coin.candles(k, a, tf) if tf != "4h" else {"error": "no 4h data"},
                       indicators=simple_indicators)
    r = sg.evaluate_group(doc, run.context("crypto", coin.asset_id, t), data_mode="point_in_time", as_of=t)
    trend_4h = next(m for m in r["members"] if m["key"] == "trend_4h")
    assert trend_4h["replay_availability"] == "no_history_at_T" and trend_4h["state"] == "excluded"
    assert r["score"]["observed_coverage"] == pytest.approx(2 / 3)
    entry = next(a for a in r["completeness"]["missing"] if a["member"] == "trend_4h")
    assert entry["affects_score_coverage"] and entry["critical"] is False
    # A confirmation that is already false on the score alone stays false (three-valued AND); only the ones left
    # unknown by the missing member are listed.
    unknown = {c["key"] for c in r["conditions"] if c["state"] == "unknown"}
    listed = set(next(a for a in r["completeness"]["missing"] if a["member"] == "momentum_4h")["confirmations_unknown"])
    assert listed == unknown and listed <= {"bullish_confirmed", "bearish_confirmed"} and listed


def test_limited_sources_are_carried_into_completeness(coin):
    limited = {tf: rp.CandleHistory(h.raw, tf, "equity", None, {**h.source, "quality": rp.RECONSTRUCTED_LIMITED,
                                                                   "limitations": [rp.SPLIT_LIMITATION]})
               for tf, h in coin.histories.items()}
    run = rp.ReplayRun(rp.DISPLAY, lambda k, a, tf: limited[tf], indicators=simple_indicators)
    t = _cutoff(coin)
    r = sg.evaluate_group(sg.starter("starter:trend-confirmation"), run.context("equity", "XYZ", t),
                          data_mode="point_in_time", as_of=t)
    assert r["completeness"]["label"] == "limited" and r["completeness"]["limitations"] == [rp.SPLIT_LIMITATION]


def test_critical_members():
    crit = gr.critical_members(_with_derivatives_veto())
    assert crit["regime_1d"] == ["veto 'ranging_veto' depends on it"]
    assert "funding_1h" in crit
    # 3 equal score members with a 2/3 minimum: losing any one still leaves 2/3, so none is critical for coverage.
    assert "trend_1d" not in crit
    doc = sg.starter("starter:trend-confirmation")
    doc["score"]["min_coverage"] = {"num": 1, "den": 1}
    assert "the score cannot reach its minimum coverage without it" in gr.critical_members(doc)["trend_1d"]


def test_mode_and_context_must_agree(coin):
    t = _cutoff(coin)
    live_ctx = DataContext("crypto", coin.asset_id)
    doc = sg.starter("starter:trend-confirmation")
    assert sg.evaluate_group(doc, live_ctx, data_mode="point_in_time", as_of=t)["status"] == "unsupported"
    replay_ctx = _run(coin).context("crypto", coin.asset_id, t)
    assert sg.evaluate_group(doc, replay_ctx)["status"] == "unsupported"
    other = sg.evaluate_group(doc, replay_ctx, data_mode="point_in_time", as_of=t - pd.Timedelta(days=1))
    assert other["status"] == "unsupported" and "not at the requested" in other["reason"]


def test_research_replays_of_groups_refuse_the_hold_out(coin):
    class Frozen:
        research_dataset = True

        def __call__(self, k, a, tf):
            return coin.candles(k, a, tf)
    run = rp.ReplayRun(rp.RESEARCH, Frozen(), indicators=simple_indicators)
    with pytest.raises(rp.ReplayRefused):
        run.context("crypto", coin.asset_id, rp.HOLDOUT_START)
    t = _cutoff(coin)
    r = sg.evaluate_group(sg.starter("starter:reversal-evidence"), run.context("crypto", coin.asset_id, t),
                          data_mode="point_in_time", as_of=t)
    assert r["replay_mode"] == "research" and r["completeness"]["label"] == "complete"


# ------------------------------------------------------------------------------------------- Sets at T

def test_set_at_t_marks_live_only_market_context_and_reports_its_worst_case(coin):
    t = _cutoff(coin)
    run = _run(coin)
    r = sg.evaluate_set(gi.example_set(), run.context("crypto", coin.asset_id, t), data_mode="point_in_time",
                        market_context=lambda scope: run.context("market", scope.split(":")[1], t))
    assert r["status"] == "ok" and r["score"] is None and r["as_of"] == t.isoformat()
    assert all(g["result"]["as_of"] == t.isoformat() for g in r["groups"])
    btc = r["market_context"][0]
    assert "live only" in btc["skipped"]
    c = r["completeness"]
    assert c["label"] == "partial" and c["missing_items"] == [{"item": "btc_etf", "section": "market_context",
                                                               "reason": btc["skipped"]}]
    assert c["groups"] == {"trend": "complete", "reversal": "complete"}
    for item in r["standalone"]:
        assert pd.Timestamp(item["signal"]["available_at"]) <= t


def test_set_market_context_must_be_a_replay_at_the_same_time(coin):
    t = _cutoff(coin)
    doc = gi.example_set()
    doc["market_context"][0]["ref"]["params"]["point_in_time"] = True
    doc["market_context"][0]["data_modes"] = ["live", "point_in_time"]
    run = _run(coin)
    r = sg.evaluate_set(doc, run.context("crypto", coin.asset_id, t), data_mode="point_in_time",
                        market_context=lambda scope: DataContext("market", "bitcoin"))
    assert "replay context" in r["market_context"][0]["skipped"]
    flows = cf.synthetic_flows(end="2024-06-30")[0]
    run2 = rp.ReplayRun(rp.DISPLAY, coin.candles, flows=flows.flow_loader(), indicators=simple_indicators)
    t2 = pd.Timestamp("2024-05-02 12:00", tz="UTC")
    r2 = sg.evaluate_set(doc, run2.context("crypto", coin.asset_id, t2), data_mode="point_in_time",
                         market_context=lambda scope: run2.context("market", scope.split(":")[1], t2))
    sig = r2["market_context"][0]["signal"]
    assert sig["status"] == "ok" and pd.Timestamp(sig["available_at"]) <= t2


def test_set_for_a_share_skips_crypto_context_without_counting_it_missing(coin):
    t = _cutoff(coin)
    run = _run(coin)
    r = sg.evaluate_set(gi.example_set(), run.context("equity", coin.asset_id, t), data_mode="point_in_time",
                        market_context=lambda scope: run.context("market", scope.split(":")[1], t))
    assert r["market_context"][0]["skipped"].startswith("applies to crypto")
    assert r["completeness"]["missing_items"] == []


# ------------------------------------------------------------------------------------------- coverage profiles

def test_group_coverage_profile_has_periods_with_levels(coin):
    run = _run(coin)
    end = pd.Timestamp(int(coin.histories["1D"].ends[-1]), tz="UTC")
    cov = gr.group_coverage(sg.starter("starter:trend-confirmation"), run, "crypto", coin.asset_id, end=end)
    levels = [p["level"] for p in cov["periods"]]
    assert levels[-1] == "replayable"
    assert all(p["missing"] for p in cov["periods"][:-1])
    assert cov["certification"]["current"]
    partial = _with_derivatives_veto()
    cov2 = gr.group_coverage(partial, run, "crypto", coin.asset_id, end=end)
    assert {p["level"] for p in cov2["periods"]} == {"partially_evaluable"}
    assert all("funding_1h" in p["critical_missing"] for p in cov2["periods"])
    only_derivs = copy.deepcopy(partial)
    only_derivs["members"] = [m for m in partial["members"] if m["key"] == "funding_1h"]
    only_derivs["conditions"] = [c for c in partial["conditions"] if c["key"] == "crowded_veto"]
    only_derivs["score"] = None
    cov3 = gr.group_coverage(only_derivs, run, "crypto", coin.asset_id, end=end)
    assert cov3["periods"] == [{"from": None, "to": None, "level": "live_only", "missing": ["funding_1h"],
                                "critical_missing": ["funding_1h"],
                                "reasons": {"funding_1h": "derivatives are live only (no stored history)"}}]


def test_set_coverage_combines_groups_and_items(coin):
    run = _run(coin)
    end = pd.Timestamp(int(coin.histories["1D"].ends[-1]), tz="UTC")
    doc = gi.example_set()
    cov = gr.set_coverage(doc, run, "crypto", coin.asset_id, end=end)
    assert set(cov["groups"]) == {"trend", "reversal"}
    assert {p["level"] for p in cov["periods"]} == {"partially_evaluable"}       # the ETF item is live only
    assert all("btc_etf" in p["missing"] for p in cov["periods"])
    doc["market_context"][0]["ref"]["params"]["point_in_time"] = True
    doc["market_context"][0]["data_modes"] = ["live", "point_in_time"]
    flows = cf.synthetic_flows(end="2024-06-30")[0]
    first_seen = min(pd.Timestamp(r["fetched_at"]) for r in flows.flows if not r["backfilled"])
    # Without flow data in the run, the source start is known but readings are not confirmed: never replayable.
    cov2 = gr.set_coverage(doc, run, "crypto", coin.asset_id, end=end, flow_starts={"flows.btc_etf": first_seen})
    assert cov2["items"]["btc_etf"]["confirmed_from"] is None and "not confirmed" in cov2["items"]["btc_etf"]["reason"]
    run2 = rp.ReplayRun(rp.DISPLAY, coin.candles, flows=flows.flow_loader(), indicators=simple_indicators)
    cov3 = gr.set_coverage(doc, run2, "crypto", coin.asset_id, end=end, flow_starts={"flows.btc_etf": first_seen})
    item = cov3["items"]["btc_etf"]
    # The ETF signal needs 5 sessions first seen live: its confirmed start is later than the first sighting.
    assert pd.Timestamp(item["confirmed_from"]) > pd.Timestamp(item["source_from"]) == first_seen
    last = cov3["periods"][-1]
    assert last["level"] == "replayable"
    assert pd.Timestamp(last["from"]) == max(pd.Timestamp(i["confirmed_from"]) for i in cov3["items"].values())


def test_coverage_is_conservative_readings_not_just_source_data(coin):
    """A replayable range starts only where every member is confirmed to read, never where candles merely exist."""
    run = _run(coin)
    end = pd.Timestamp(int(coin.histories["1D"].ends[-1]), tz="UTC")
    doc = sg.starter("starter:trend-confirmation")
    cov = gr.group_coverage(doc, run, "crypto", coin.asset_id, end=end)
    members = cov["members"]
    for key, m in members.items():
        assert pd.Timestamp(m["confirmed_from"]) >= pd.Timestamp(m["source_from"]), key
    # Warm-up: the daily trend needs 50 closed candles, so it reads well after its first candle.
    assert pd.Timestamp(members["trend_1d"]["confirmed_from"]) >= \
        pd.Timestamp(members["trend_1d"]["source_from"]) + pd.Timedelta(days=49)
    replayable = [p for p in cov["periods"] if p["level"] == "replayable"]
    assert replayable
    first = pd.Timestamp(replayable[0]["from"])
    at_start = sg.evaluate_group(doc, run.context("crypto", coin.asset_id, first), data_mode="point_in_time",
                                 as_of=first)
    assert all(m["replay_availability"] == "replayable" for m in at_start["members"])
    assert at_start["completeness"]["label"] == "complete"
    before = first - pd.Timedelta(seconds=1)
    early = sg.evaluate_group(doc, _run(coin).context("crypto", coin.asset_id, before), data_mode="point_in_time",
                              as_of=before)
    assert early["completeness"]["partial"]
    # Before that, ranges where data exists but readings do not are labelled as such.
    source_only = [p for p in cov["periods"] if gr.SOURCE_ONLY in p["reasons"].values()]
    assert source_only and all(p["level"] == "partially_evaluable" for p in source_only)
    assert "not the first time its source data exists" in cov["evaluability"]


def test_uncertified_signals_make_coverage_partial(coin, certified):
    certified["signals"].pop("structure.swings@1")
    run = _run(coin)
    end = pd.Timestamp(int(coin.histories["1D"].ends[-1]), tz="UTC")
    cov = gr.group_coverage(sg.starter("starter:trend-confirmation"), run, "crypto", coin.asset_id, end=end)
    assert {p["level"] for p in cov["periods"]} == {"partially_evaluable"}
    assert "not certified" in cov["members"]["structure_1d"]["reason"]
    assert cov["members"]["structure_1d"]["confirmed_from"] is None


# ------------------------------------------------------------------------------------------- stage 4: admin inspector

@pytest.fixture
def offline_display(monkeypatch, coin):
    from signal_library import replay_display

    monkeypatch.setattr(replay_display, "live_candles", coin.candles)
    monkeypatch.setattr(rp, "default_indicators", simple_indicators)
    return coin


def test_inspector_reconstructs_one_group_at_one_time(offline_display):
    t = _cutoff(offline_display)
    title, kind, result, record, error = gi.reconstruct(None, "group", sg.starter("starter:trend-confirmation"),
                                                        "crypto", offline_display.asset_id, t, "Trend")
    assert error is None and result["data_mode"] == "point_in_time" and result["as_of"] == t.isoformat()
    assert result["completeness"]["label"] == "complete"
    assert record["mode"] == "display" and record["cutoffs"] == [t.isoformat()]
    assert all(i["sha256"] for i in record["inputs"])


def test_inspector_reconstructs_a_set_and_refuses_the_future(offline_display):
    t = _cutoff(offline_display)
    _, _, result, record, error = gi.reconstruct(None, "set", gi.example_set(), "crypto",
                                                 offline_display.asset_id, t, "Set")
    assert error is None and result["completeness"]["label"] == "partial"
    future = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
    *_, error = gi.reconstruct(None, "set", gi.example_set(), "crypto", offline_display.asset_id, future, "Set")
    assert error == "Choose a time in the past."


def test_inspector_reconstruction_uses_certified_slicing_only(offline_display, certified, monkeypatch):
    """Admin reconstructions slice only signal/timeframe pairs certified slice-equivalent; the rest stay exact."""
    certified["signals"]["trend.direction@1"]["1D"]["slice_equivalent"] = True    # sliced
    certified["signals"]["structure.swings@1"]["1D"]["slice_equivalent"] = False  # stays exact
    seen = {}
    original = rp.ReplayRun.slice_ok

    def spy(self, signal_key, timeframe):
        result = original(self, signal_key, timeframe)
        seen[(signal_key, timeframe)] = (self.shortcut, result)
        return result
    monkeypatch.setattr(rp.ReplayRun, "slice_ok", spy)
    t = _cutoff(offline_display)
    _, _, result, record, error = gi.reconstruct(None, "group", sg.starter("starter:trend-confirmation"), "crypto",
                                                 offline_display.asset_id, t, "Trend")
    assert error is None
    assert seen[("trend.direction@1", "1D")] == (True, True)
    assert seen[("structure.swings@1", "1D")] == (True, False)
    paths = {(i["timeframe"], i["path"]) for i in record["inputs"]}
    assert ("1D", "slice") in paths and ("1D", "exact") in paths    # both recorded, one per path
    # The sliced reconstruction equals the exact one.
    exact = sg.evaluate_group(sg.starter("starter:trend-confirmation"),
                              rp.ReplayRun(rp.DISPLAY, offline_display.candles).context(
                                  "crypto", offline_display.asset_id, t), data_mode="point_in_time", as_of=t)
    assert _strip(json.loads(json.dumps(result, default=str))) == _strip(json.loads(json.dumps(exact, default=str)))
