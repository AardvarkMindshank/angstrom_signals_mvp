"""
Trend, Stretch and Flow for the dashboard, alerts and the digest, worked out by the starter Groups (build stage 6).

The three readings everywhere in the app now come from the Trend, Stretch and Flow Groups, evaluated on the same
stored daily bars, with labels written as Group outcomes. `score()` returns the same shape as `signals_v2.score()`
so every screen keeps working, plus, per reading, the Group that produced it (name, outcome, completeness).

The numbers are the same as before: the starter Groups were built to reproduce the old calculation exactly, and
CI checks it (`replay_certify.py --parity`, tolerance 1e-9, identical displayed percent and coverage).

`signals_v2` is kept for two things only: research reproducibility (evidence records, the validation reports), and
the non-directional context beside the readings (volatility, trend strength, regime, warnings), which no Group
describes yet.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime

import pandas as pd

import signals_v2 as v2

VERSION = "groups-1"
CLUSTERS = v2.CLUSTERS                     # names, icons, horizons and questions are unchanged
STARTERS = {"trend": "starter:trend", "stretch": "starter:stretch", "flow": "starter:flow"}

# Outcome labels, the same bands as before (strong 0.5, band 0.2). Rules only use "at least" and "at most", and the
# order makes the edges match the old wording exactly (-0.2 is a downtrend, -0.5 a strong one).
WORDS = {
    "trend": ("Strong uptrend", "Uptrend", "No clear trend", "Downtrend", "Strong downtrend"),
    "stretch": ("Very stretched up", "Stretched up", "Not stretched", "Stretched down", "Very stretched down"),
    "flow": ("Strong buying volume", "Buying volume", "Volume neutral", "Selling volume", "Strong selling volume"),
}
IDS = ("strong_up", "up", "neutral", "down", "strong_down")
UNKNOWN_LABEL = "Not enough data"


def dashboard_group(cluster: str) -> dict:
    """The starter Group with the dashboard's labels added as outcomes. Built in code, read-only."""
    import signal_groups as sg

    doc = copy.deepcopy(sg.starter(STARTERS[cluster]))
    strong, band = v2.DEFINITIONS["label_band_strong"], v2.DEFINITIONS["label_band"]
    w = WORDS[cluster]
    doc["outcomes"] = {"version": 1, "rules": [
        {"id": IDS[0], "label": w[0], "when": {"score": {"gte": strong}}},
        {"id": IDS[1], "label": w[1], "when": {"score": {"gte": band}}},
        {"id": IDS[4], "label": w[4], "when": {"score": {"lte": -strong}}},
        {"id": IDS[3], "label": w[3], "when": {"score": {"lte": -band}}},
    ], "otherwise": {"id": IDS[2], "label": w[2]}}
    return doc


def _fingerprint() -> str:
    try:
        docs = {c: dashboard_group(c) for c in STARTERS}
    except Exception:
        docs = {}
    return hashlib.sha256((VERSION + v2.FINGERPRINT + json.dumps(docs, sort_keys=True)).encode()).hexdigest()[:12]


FINGERPRINT = _fingerprint()
SCORING_BARS = v2.SCORING_BARS
TREND_ALERT_DEFAULT = v2.TREND_ALERT_DEFAULT
TREND_ALERT_REARM = v2.TREND_ALERT_REARM


def _engine_kind(kind: str) -> str:
    return "crypto" if str(kind).lower().startswith("crypto") else "equity"


def _cluster(cluster: str, result: dict, members: list[str], horizon: str) -> dict:
    score = result.get("score") or {}
    value = score.get("value")
    by_key = {m.get("key"): m for m in result.get("members") or []}
    observed = [k for k in members if (by_key.get(k) or {}).get("state") == "observed"]
    outcome = result.get("outcome") or {}
    known = value is not None and outcome.get("id") not in (None, "unknown")
    comps = {}
    for k in members:
        m = by_key.get(k) or {}
        part = m.get("contribution") if m.get("state") == "observed" else None
        comps[k] = {"value": part, "percent": v2.percent(part)}
    return {
        "value": value, "percent": v2.percent(value),
        "label": outcome.get("label") if known else UNKNOWN_LABEL,
        "coverage": [len(observed), len(members)], "horizon": horizon, "components": comps,
        "group": {
            "name": CLUSTERS[cluster]["name"], "starter": STARTERS[cluster],
            "outcome": outcome.get("id") or "unknown", "status": result.get("status"),
            "completeness": "Complete" if len(observed) == len(members) else "Partial" if observed else "None",
        },
    }


def score(frame: pd.DataFrame, kind: str, now: datetime | None = None) -> dict:
    """The readings for the last finished daily bar of `frame` (the output of scoring.calculate_indicators), in the
    shape of signals_v2.score, with Trend, Stretch and Flow from the starter Groups."""
    import signal_groups as sg
    from signal_library import DataContext

    legacy = v2.score(frame, kind, now)
    out = {**legacy, "version": VERSION, "fingerprint": FINGERPRINT, "source": "groups"}
    if legacy.get("status") != "ok":
        return out
    pos = v2.last_completed_position(frame.index, kind, now)
    done = frame.iloc[: pos + 1]
    loaded = {"frame": done.assign(forming=False), "session": None, "source": "stored"}
    ctx = DataContext(_engine_kind(kind), "dashboard", candle_loader=lambda k, a, tf: loaded,
                      now=pd.Timestamp(done.index[-1]) + pd.Timedelta(days=3))
    clusters = {}
    for cluster, spec in CLUSTERS.items():
        result = sg.evaluate_group(dashboard_group(cluster), ctx)
        clusters[cluster] = _cluster(cluster, result, spec["components"], spec["horizon"])
    out["clusters"] = clusters

    t, s = clusters["trend"]["value"], clusters["stretch"]["value"]
    level = v2.DEFINITIONS["against_trend_level"]
    against = None
    if t is not None and s is not None and abs(t) >= level and abs(s) >= level and (t > 0) != (s > 0):
        against = "pullback" if t > 0 else "rally"
    lenses = {}
    for key, weights in v2.DEFINITIONS["lenses"].items():
        parts = [(w, clusters[c]["value"]) for c, w in weights.items() if clusters[c]["value"] is not None]
        total = sum(abs(w) for w, _ in parts)
        value = sum(w * v for w, v in parts) / total if parts and total else None
        lenses[key] = {"value": value, "percent": v2.percent(value)}
    out.update(lenses=lenses, against_trend=against, summary=v2.summary(clusters, against))
    return out


def flat_fields(result: dict) -> dict:
    """The few numbers tables, alerts and the digest use."""
    return v2.flat_fields(result)
