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


def stored_context(frame: pd.DataFrame, kind: str, now: datetime | None = None, asset_id: str = "dashboard"):
    """(engine context, start of the last finished daily bar) for stored daily bars with indicators: what the
    dashboard reads. Every Group or Set evaluated through it sees exactly the dashboard's numbers."""
    from signal_library import DataContext

    pos = v2.last_completed_position(frame.index, kind, now)
    done = frame.iloc[: pos + 1]
    loaded = {"frame": done.assign(forming=False), "session": None, "source": "stored"}
    ctx = DataContext(_engine_kind(kind), asset_id, candle_loader=lambda k, a, tf: loaded if tf == "1D" else
                      {"error": f"Stored bars are daily; {tf} is not stored."},
                      now=pd.Timestamp(done.index[-1]) + pd.Timedelta(days=3))
    return ctx, pd.Timestamp(done.index[-1])


CONTEXT_REFS = (("regime.observation", {"window": v2.DEFINITIONS["percentile_window"]}), ("volume.relative", {}))


def context_from_signals(ctx, kind: str, warnings: list | None = None) -> dict:
    """The non-directional context beside the readings (daily range, trend strength, regime, volume against usual),
    read from the Regime evidence and Relative volume signals, in the shape the asset card draws."""
    import signal_library as sl

    refs = [sl.SignalRef.make(sl.REGISTRY.get(i, 1), "1D", **params) for i, params in CONTEXT_REFS]
    got = sl.evaluate(refs, ctx)
    regime_sig, volume_sig = (got[r.instance_key] for r in refs)
    obs = regime_sig.value if regime_sig.status == "ok" and isinstance(regime_sig.value, dict) else {}
    pct, adx = obs.get("atr_pct_percentile"), obs.get("adx")
    stock = not str(kind).lower().startswith("crypto")
    strong, weak = v2.DEFINITIONS["adx_strong"], v2.DEFINITIONS["adx_weak"]
    return {
        "volatility": {
            "atr_pct": obs.get("atr_pct"), "percentile": pct,
            "label": ("Higher than usual" if pct is not None and pct >= 80 else
                      "Lower than usual" if pct is not None and pct <= 20 else
                      "About usual" if pct is not None else "Not enough history"),
            "validation": "volatility_stock" if stock else "volatility_crypto",
        },
        "trend_strength": {"adx": adx, "label": ("Strong" if adx is not None and adx >= strong else
                                                  "Weak" if adx is not None and adx < weak else
                                                  "Developing" if adx is not None else "Not enough data")},
        "regime": ({"state": obs["state"], "direction": obs.get("direction"),
                    "label": obs["state"] if obs["state"] != "trending" else f"trending_{obs.get('direction')}"} if obs.get("state") else None),
        "participation": {"volume_ratio": volume_sig.value if volume_sig.status == "ok" else None},
        "warnings": list(warnings or []),
        "source": "signals",
    }


def against_trend(ctx) -> str | None:
    """"pullback" or "rally" when the provided Set of that name answers Yes (prism.against_trend_sets), else None."""
    import prism
    import signal_groups as sg

    for key, word in (("demo:pullback", "pullback"), ("demo:rally", "rally")):
        doc = prism.against_trend_sets()[key]
        result = sg.evaluate_set(doc, ctx)
        if (result.get("decision") or {}).get("answer") == "yes":
            return word
    return None


def score(frame: pd.DataFrame, kind: str, now: datetime | None = None) -> dict:
    """The readings for the last finished daily bar of `frame` (the output of scoring.calculate_indicators), in the
    shape of signals_v2.score, with Trend, Stretch and Flow from the starter Groups."""
    import signal_groups as sg

    legacy = v2.score(frame, kind, now)
    out = {**legacy, "version": VERSION, "fingerprint": FINGERPRINT, "source": "groups"}
    if legacy.get("status") != "ok":
        return out
    ctx, _ = stored_context(frame, kind, now)
    clusters = {}
    for cluster, spec in CLUSTERS.items():
        result = sg.evaluate_group(dashboard_group(cluster), ctx)
        clusters[cluster] = _cluster(cluster, result, spec["components"], spec["horizon"])
    out["clusters"] = clusters

    against = against_trend(ctx)
    out["context"] = context_from_signals(ctx, kind, (legacy.get("context") or {}).get("warnings"))
    out.pop("lenses", None)               # the old "named views": retired (Groups and Sets cover them)
    out.update(against_trend=against, summary=v2.summary(clusters, against))
    return out


def flat_fields(result: dict) -> dict:
    """The few numbers tables, alerts and the digest use."""
    return v2.flat_fields(result)
