"""Tides preview: the engine's fixed rules (tides.py) and the macro calendar (macro_calendar.py)."""

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import macro_calendar as mc
import tides as td


def _walk(seed, start=100.0, n=1600, vol=0.01, drift=0.0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=n)
    return pd.Series(start * np.exp(np.cumsum(rng.normal(drift, vol, n))), index=days)


def _raw():
    yahoo, fred = td.symbols_needed()
    raw = {s: _walk(i, vol=0.02 if "USD" in s else 0.01) for i, s in enumerate(sorted(yahoo))}
    raw["^TNX"] = _walk(50, start=4.0, vol=0.01)
    raw["^VIX"] = _walk(51, start=18.0, vol=0.03)
    for i, sid in enumerate(sorted(fred)):
        raw[f"fred:{sid}"] = _walk(60 + i, start=3.0, vol=0.01)
    months = pd.date_range(end=pd.Timestamp.now().normalize(), periods=80, freq="MS")
    raw["fred:CPIAUCSL"] = pd.Series(np.linspace(250, 320, 80), index=months)
    return raw


def test_snapshot_is_complete_and_json_ready():
    snap = td.snapshot(_raw(), btc_dominance=57.3, fear_greed=32)
    json.dumps(snap)
    assert set(snap["currents"]) == set(td.CURRENT_KEYS) and len(td.CURRENT_KEYS) == 12
    ok = [c for c in snap["currents"].values() if c["status"] == "ok"]
    assert len(ok) == 12, [c["key"] for c in snap["currents"].values() if c["status"] != "ok"]
    for c in ok:
        assert 0 <= c["score"] <= 100 and c["band"] and c["direction"] in ("rising", "falling", "flat")
        assert -1 <= c["contribution"] <= 1 and len(c["wave"]) > 100
    t = snap["tide"]
    assert t["status"] == "ok" and t["label"] in ("in", "slack", "out") and -1 <= t["score"] <= 1
    assert snap["sea"]["state"] in ("calm", "moderate", "rough", "storm")
    assert set(snap["winds"]) == {"crypto", "equity"}
    assert any("tide" in line.lower() for line in td.summary(snap))


def test_non_voting_currents_do_not_move_the_tide():
    raw = _raw()
    base = td.snapshot(raw)["tide"]["score"]
    raw["GC=F"] = raw["GC=F"] * np.linspace(1, 3, len(raw["GC=F"]))      # gold soars
    raw["CL=F"] = raw["CL=F"] * np.linspace(1, 0.3, len(raw["CL=F"]))    # oil collapses
    raw["HG=F"] = raw["HG=F"] * np.linspace(1, 3, len(raw["HG=F"]))      # keep copper/gold unchanged
    assert abs(td.snapshot(raw)["tide"]["score"] - base) < 1e-9


def test_signs_and_bands():
    up = pd.Series(np.linspace(1, 2, 1600), index=pd.bdate_range(end="2026-11-12", periods=1600))
    r = td.read_current("dollar", up)
    assert r["direction"] == "rising" and r["contribution"] < 0 and r["band"] == "very high"   # strong dollar: defensive
    r = td.read_current("credit", up)
    assert r["contribution"] > 0                                                                # credit calm: supportive
    assert td.band(10) == "very low" and td.band(50) == "normal" and td.band(99.9) == "very high"


def test_tide_label_needs_five_closes():
    labels = pd.Series(["in"] * 10 + ["out"] * 4 + ["in"] * 3 + ["out"] * 5)
    shown = td.persist(labels).tolist()
    assert shown[13] == "in" and shown[16] == "in"          # 4 closes of "out" are not enough
    assert shown[-1] == "out" and shown[-2] == "in"         # the fifth close flips it
    assert td.label_for(0.25) == "in" and td.label_for(-0.25) == "out" and td.label_for(0.1) == "slack"


def test_missing_sources_degrade_honestly():
    raw = _raw()
    del raw["fred:DGS2"], raw["^VIX"]
    snap = td.snapshot(raw)
    assert snap["currents"]["short_rates"]["status"] == "missing" and snap["currents"]["fear"]["status"] == "missing"
    assert snap["tide"]["status"] == "ok"                   # the other families still vote
    assert snap["sea"]["status"] == "ok" and snap["sea"]["vix_score"] is None   # Bitcoin's volatility alone


def test_calendar_and_storm_warning():
    ev = mc.events()
    assert ev == sorted(ev, key=lambda e: e["at"]) and {e["kind"] for e in ev} == set(mc.KINDS)
    cpi = next(e for e in ev if e["kind"] == "cpi" and e["reference"] == "November 2026")
    assert cpi["at"] == datetime(2026, 12, 10, 13, 30, tzinfo=timezone.utc)      # 08:30 New York in winter
    fed = next(e for e in ev if e["kind"] == "fomc" and e["at"].year == 2026)
    assert fed["at"].hour == 19 and fed["tier"] == 2                            # 14:00 New York
    jobs = next(e for e in ev if e["kind"] == "jobs" and e["reference"] == "November 2026")
    assert mc.storm_warning(jobs["at"] - timedelta(hours=23))["kind"] == "jobs"
    assert mc.storm_warning(jobs["at"] + timedelta(hours=23))["kind"] == "jobs"
    assert mc.storm_warning(cpi["at"] - timedelta(hours=20))["kind"] == "fomc"   # the Fed (9 Dec) is nearer
    assert mc.storm_warning(datetime(2026, 11, 20, tzinfo=timezone.utc)) is None
    ppi = next(e for e in ev if e["kind"] == "ppi" and e["reference"] == "October 2026")
    assert mc.storm_warning(ppi["at"], majors_only=True) is None                  # PPI is one pennant
    soon = mc.upcoming(datetime(2026, 11, 12, tzinfo=timezone.utc))
    assert [e["kind"] for e in soon][:1] == ["ppi"] and mc.pennants(2) == "🚩🚩"
    assert mc.when_words(cpi["at"], cpi["at"] - timedelta(hours=5)) == "in 5 hours"


def test_the_tide_never_reads_a_date_after_today():
    raw = _raw()
    future = pd.Timestamp.now().normalize() + pd.Timedelta(days=40)
    raw["fred:CPIAUCSL"] = pd.concat([raw["fred:CPIAUCSL"], pd.Series([330.0], index=[future])])
    snap = td.snapshot(raw)
    assert snap["tide"]["history"][-1][0] <= pd.Timestamp.now().date().isoformat()
    fam = snap["tide"]["families"]
    weights = {f: td.FAMILIES[f][1] for f in fam}
    expect = sum(fam[f] * weights[f] for f in fam) / sum(weights.values())
    assert abs(snap["tide"]["score"] - expect) < 0.02          # today's score is all four families, not one
