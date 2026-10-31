"""The hold-out procedure: frozen spec, guards, reproduction check, look-ahead safeguards, dual benchmarks.
Synthetic data only. Nothing here reads the real price cache."""

import copy

import numpy as np
import pandas as pd
import pytest

import research as rs
import research_stats as st
from test_research_stats import fake_universe


def classes_of(details):
    return {t: rs.asset_class(t) for t in details}


def test_spec_has_exactly_the_three_signed_off_tests():
    assert set(rs.HOLDOUT_SPEC["primary"]) == {"B", "C1", "C2"}
    assert rs.HOLDOUT_SPEC["dropped_at_development_gate"] == ["A1", "A2"]
    for cfg in rs.HOLDOUT_SPEC["primary"].values():
        assert cfg["direction"] == 1 and cfg["mme"] > 0 and cfg["kappa"] in (1.0, 1.2)


def test_spec_hash_changes_with_any_value():
    changed = copy.deepcopy(rs.HOLDOUT_SPEC)
    changed["primary"]["B"]["mme"] = 0.4
    assert rs.spec_hash(changed) != rs.HOLDOUT_SPEC_HASH
    assert rs.spec_hash(copy.deepcopy(rs.HOLDOUT_SPEC)) == rs.HOLDOUT_SPEC_HASH


@pytest.mark.parametrize("unlock,hash_,env", [
    ("wrong", rs.HOLDOUT_SPEC_HASH, {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": rs.HOLDOUT_TAG}),
    (rs.HOLDOUT_TAG, "0" * 64, {"GITHUB_REF_TYPE": "tag", "GITHUB_REF_NAME": rs.HOLDOUT_TAG}),
    (rs.HOLDOUT_TAG, rs.HOLDOUT_SPEC_HASH, {"GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": "main"}),
    (rs.HOLDOUT_TAG, rs.HOLDOUT_SPEC_HASH, {}),
])
def test_holdout_refuses_without_every_guard(monkeypatch, tmp_path, unlock, hash_, env):
    for k in ("GITHUB_REF_TYPE", "GITHUB_REF_NAME"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    loaded = []
    monkeypatch.setattr(rs, "load_cache", lambda *_: loaded.append(1))
    with pytest.raises(SystemExit, match="Hold-out refused"):
        rs.run_holdout("prices", str(tmp_path), unlock, hash_)
    assert not loaded                                  # refused before a single price is loaded


@pytest.fixture
def dev_universe():
    frames, details = fake_universe(seed=21)
    dev_f = rs.development_frames(frames, rs.HOLDOUT_START)
    dev_d = {t: rs.development_view(d, rs.HOLDOUT_START) for t, d in details.items()}
    return frames, details, dev_f, dev_d


def test_reproduction_check_matches_and_catches_drift(monkeypatch, dev_universe):
    _, details, dev_f, dev_d = dev_universe
    cls = classes_of(details)
    expected = {}
    for key, cfg in rs.HOLDOUT_SPEC["primary"].items():
        n, d = rs.primary_rows(dev_f, dev_d, cls, key, cfg)
        expected[key] = float(n.sum() / d.sum())
    spec = copy.deepcopy(rs.HOLDOUT_SPEC)
    spec["expected_development"] = expected
    monkeypatch.setattr(rs, "HOLDOUT_SPEC", spec)
    assert rs.reproduce_development(dev_f, dev_d, cls)["all_match"]
    drifted = {t: d.copy() for t, d in dev_d.items()}
    for i, d in enumerate(drifted.values()):
        d["Trend"] = d["Trend"] * (1 if i % 2 else -1)           # a scoring change
        d["x_atr_pct"] = d["x_atr_pct"].shift(1)
    assert not rs.reproduce_development(dev_f, drifted, cls)["all_match"]


def test_evaluation_uses_no_price_after_label_end_and_no_signal_before_eligibility(dev_universe):
    _, details, dev_f, dev_d = dev_universe
    cls = classes_of(details)
    start = pd.Timestamp("2023-06-01")
    label_end = pd.Timestamp("2024-06-30")
    base = rs.evaluate_window(dev_f, dev_d, cls, start, label_end, runs=200)
    # poison prices after label_end, and signals/ATR before each class's first eligible date
    pf = {t: f.copy() for t, f in dev_f.items()}
    for f in pf.values():
        f.loc[f.index > label_end, ["open", "high", "low", "close"]] *= 7
    pd_ = {t: d.copy() for t, d in dev_d.items()}
    for t, d in pd_.items():
        first = pd.Timestamp(base["first_eligible_signal"][rs.asset_class(t)])
        d.loc[d.index < first, ["Trend", "x_atr_pct"]] = -d.loc[d.index < first, ["Trend", "x_atr_pct"]] + 3
    again = rs.evaluate_window(pf, pd_, cls, start, label_end, runs=200)
    for key in rs.HOLDOUT_SPEC["primary"]:
        assert again["primary"][key]["estimate"] == pytest.approx(base["primary"][key]["estimate"], abs=1e-12)
        assert again["primary"][key]["p_value"] == pytest.approx(base["primary"][key]["p_value"], abs=1e-12)


def test_evaluation_reports_holm_outcomes_and_both_benchmarks(dev_universe):
    _, details, dev_f, dev_d = dev_universe
    res = rs.evaluate_window(dev_f, dev_d, classes_of(details), pd.Timestamp("2023-06-01"),
                             pd.Timestamp("2024-10-29"), runs=200)
    assert set(res["primary"]) == {"B", "C1", "C2"}
    for t in res["primary"].values():
        assert t["outcome"] in {"Confirmed", "Confirmed, clearly above the minimum", "Inconclusive", "Contradicted"}
        assert isinstance(t["holm_passed"], bool)
    for label in ("base 0.20%", "stress 0.50%"):
        s = res["long_only"][label]
        assert "Bitcoin bought and held" in s["against"]
        assert s["strategy_one_way_turnover_a_year"] > 0 and s["strategy_max_drawdown_pct"] <= 0
    text = rs.format_evaluation(res, "test")
    assert "not investable proof" in text and "Bitcoin" in text


def test_first_eligible_dates_in_evaluation_follow_the_embargo(dev_universe):
    _, details, dev_f, dev_d = dev_universe
    start = pd.Timestamp("2023-06-01")
    res = rs.evaluate_window(dev_f, dev_d, classes_of(details), start, pd.Timestamp("2024-10-29"), runs=50)
    coin_idx = dev_f["SOL-USD"].index
    assert res["first_eligible_signal"]["crypto"] == str(coin_idx[coin_idx.searchsorted(start) + 30].date())


def test_buy_and_hold_enters_at_the_next_close_and_pays_once():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    close = pd.Series([1.0, 2.0, 3.0, 3.0, 6.0], index=idx)
    r = st.buy_and_hold(close, idx, cost_per_side=0.01)
    assert list(r["net"]) == pytest.approx([0.0, -0.01, 0.5, 0.0, 1.0])     # the 1->2 jump is not earned


def test_concentration_contributions_add_up_to_the_spread(dev_universe):
    _, details, dev_f, dev_d = dev_universe
    c = rs.crypto_concentration(dev_f, dev_d, classes_of(details))
    assert sum(c["contribution_by_coin_pct"].values()) == pytest.approx(c["all"]["estimate"], rel=1e-9)
    assert "BTC-USD" not in c["contribution_by_coin_pct"]            # already-seen coins stay out
    assert "## By calendar year" in rs.format_concentration(c)
