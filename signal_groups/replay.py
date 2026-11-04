"""
Point-in-time evaluation of Groups and Sets (design: docs/design/point_in_time.md, section 5; stage 3).

A Group or Set is replayed at T by passing data_mode="point_in_time" and a replay context at T
(signal_library.replay.ReplayRun.context). Members whose signal cannot be reconstructed at T are unavailable,
with the reason, and the existing coverage, exclude/neutral and three-valued condition rules apply unchanged.
Everything here only describes the result; it never changes a score, a condition or a status.

- completeness (5.1): complete / partial / limited for each replayed result, listing what is missing at T and
  what that affects: score coverage, confirmations and vetoes that became unknown. A partial or limited result,
  or one with an unknown veto, is marked `qualified` and must never be shown unqualified.
- critical members (5.2): members a veto depends on, and score members without which the minimum coverage cannot
  be met.
- coverage profiles (5.2): date ranges with one of four levels, computed from certification records and the
  history each source actually has: replayable, reconstructed_with_limitations, partially_evaluable, live_only.
"""

from __future__ import annotations

from fractions import Fraction

import pandas as pd

import signal_library as sl
from signal_library import certification
from signal_library.replay import (
    NOT_REPLAYABLE, POINT_IN_TIME, RECONSTRUCTED_LIMITED, CandleHistory, ReplayContext, utc,
)

POINT_IN_TIME_MODE = "point_in_time"
REPLAYABLE_STATUSES = ("ok", "stale")
NO_HISTORY_STATUSES = ("missing_data", "insufficient_data")

LEVELS = ("replayable", "reconstructed_with_limitations", "partially_evaluable", "live_only")


# ---------------------------------------------------------------------------------------------- requests

def context_problem(ctx, as_of) -> str | None:
    """None when ctx is a replay context at the requested cutoff."""
    if not isinstance(ctx, ReplayContext):
        return "Point-in-time evaluation needs a replay context (signal_library.replay), not a live one."
    if as_of is not None and utc(as_of) != ctx.as_of:
        return f"The replay context is at {ctx.as_of.isoformat()}, not at the requested {utc(as_of).isoformat()}."
    return None


def availability(status: str) -> str:
    """How a member's signal stood at T."""
    if status in REPLAYABLE_STATUSES:
        return "replayable"
    if status == NOT_REPLAYABLE:
        return "not_replayable"
    if status in NO_HISTORY_STATUSES:
        return "no_history_at_T"
    return status


# ---------------------------------------------------------------------------------------------- rule structure

def rule_members(rule, score_members: set) -> set:
    """Member keys a rule depends on; a score predicate depends on every scoring member."""
    if not isinstance(rule, dict):
        return set()
    if "member" in rule:
        return {rule["member"]}
    if "score" in rule:
        return set(score_members)
    out = set()
    for key in ("all", "any", "of"):
        for sub in rule.get(key) or []:
            out |= rule_members(sub, score_members)
    if "not" in rule:
        out |= rule_members(rule["not"], score_members)
    return out


def _score_members(doc) -> set:
    return {m["key"] for m in doc.get("members") or [] if m.get("role") == "score" and Fraction(str(m.get("weight", 0)))}


def critical_members(doc: dict) -> dict:
    """{member key: [reasons]}: members a veto depends on, and score members without which the minimum score
    coverage cannot be reached."""
    out: dict = {}
    scoring = _score_members(doc)
    for c in doc.get("conditions") or []:
        if c.get("kind") == "veto":
            for key in rule_members(c.get("rule"), scoring):
                out.setdefault(key, []).append(f"veto '{c['key']}' depends on it")
    if doc.get("score") is not None:
        weights = {m["key"]: Fraction(str(m["weight"])) for m in doc["members"] if m["key"] in scoring}
        enabled = sum(weights.values(), Fraction(0))
        mc = doc["score"]["min_coverage"]
        for key, w in weights.items():
            if (enabled - w) * mc["den"] < enabled * mc["num"]:
                out.setdefault(key, []).append("the score cannot reach its minimum coverage without it")
    return out


# ---------------------------------------------------------------------------------------------- completeness (5.1)

def _limitations(ctx: ReplayContext) -> list[str]:
    found = []
    for value in ctx._memo.values():
        if isinstance(value, dict) and value.get("source_quality") == RECONSTRUCTED_LIMITED:
            for text in value.get("limitations") or []:
                if text not in found:
                    found.append(text)
    return found


def group_completeness(doc: dict, result: dict, ctx: ReplayContext) -> dict:
    scoring = _score_members(doc)
    critical = critical_members(doc)
    rows = {m["key"]: m for m in result.get("members") or []}
    missing = {k: m for k, m in rows.items() if m.get("replay_availability") != "replayable"}
    conditions = {c["key"]: c for c in result.get("conditions") or []}
    affected = []
    for key, row in missing.items():
        deps = [c for c in doc.get("conditions") or [] if key in rule_members(c.get("rule"), scoring)]
        affected.append({
            "member": key, "label": row.get("label"), "role": row.get("role"),
            "reason": row.get("replay_availability"), "notes": (row.get("signal") or {}).get("notes") or [],
            "critical": key in critical, "critical_because": critical.get(key, []),
            "affects_score_coverage": key in scoring and doc.get("score") is not None,
            "confirmations_unknown": [c["key"] for c in deps if c["kind"] == "confirmation"
                                      and conditions.get(c["key"], {}).get("state") == "unknown"],
            "vetoes_unknown": [c["key"] for c in deps if c["kind"] == "veto"
                               and conditions.get(c["key"], {}).get("state") == "unknown"],
        })
    limitations = _limitations(ctx)
    partial, limited = bool(missing), bool(limitations)
    label = "partial and limited" if partial and limited else "partial" if partial else "limited" if limited else "complete"
    veto_unknown = result.get("status") == "veto_unknown"
    notes = []
    if partial:
        notes.append(f"Reconstructed without {len(missing)} member(s) at this time: "
                     + ", ".join(f"{a['member']} ({a['reason']})" for a in affected) + ".")
    if any(a["critical"] for a in affected):
        notes.append("A critical member is missing: a veto or the score's minimum coverage depends on it.")
    if veto_unknown:
        notes.append("A veto could not be checked at this time, so the result must not be read as cleared.")
    unknown_conf = sorted({k for a in affected for k in a["confirmations_unknown"]})
    if unknown_conf:
        notes.append("Confirmations unknown because of missing members: " + ", ".join(unknown_conf) + ".")
    notes += limitations
    return {"label": label, "partial": partial, "limited": limited, "qualified": partial or limited or veto_unknown,
            "missing": affected, "limitations": limitations, "notes": notes}


def set_completeness(result: dict, ctx: ReplayContext) -> dict:
    groups = {g["key"]: (g["result"].get("completeness") or {}) for g in result.get("groups") or []}
    missing_items = []
    for item in result.get("standalone") or []:
        status = (item.get("signal") or {}).get("status")
        if availability(status) != "replayable":
            missing_items.append({"item": item["key"], "section": "standalone", "reason": availability(status)})
    for item in result.get("market_context") or []:
        if item.get("skipped") and "applies to" in item["skipped"]:
            continue                                    # not relevant to this asset, so not missing
        status = (item.get("signal") or {}).get("status")
        if item.get("skipped") or availability(status) != "replayable":
            missing_items.append({"item": item["key"], "section": "market_context",
                                  "reason": item.get("skipped") or availability(status)})
    partial = bool(missing_items) or any(c.get("partial") for c in groups.values())
    limitations = _limitations(ctx)
    for c in groups.values():
        for text in c.get("limitations") or []:
            if text not in limitations:
                limitations.append(text)
    limited = bool(limitations)
    label = "partial and limited" if partial and limited else "partial" if partial else "limited" if limited else "complete"
    qualified = partial or limited or any(c.get("qualified") for c in groups.values())
    return {"label": label, "partial": partial, "limited": limited, "qualified": qualified,
            "groups": {k: c.get("label") for k, c in groups.items()}, "missing_items": missing_items,
            "limitations": limitations,
            "note": "A Set is as complete as its least complete part; each Group's own completeness is listed."}


# ---------------------------------------------------------------------------------------------- coverage (5.2)

CONFIRM_READINGS = 3          # a first reading counts only when the next few cutoffs read too
MAX_RESTARTS = 12


def _readable(probe, ref, kind, asset_id, t) -> bool:
    got = sl.evaluate([ref], probe.context(kind, asset_id, t))[ref.instance_key]
    return got.status in REPLAYABLE_STATUSES


def _first_reading(run, ref, kind: str, asset_id: str, candidates: list) -> tuple:
    """First cutoff from which the signal actually produces a reading, confirmed by the next CONFIRM_READINGS
    candidate cutoffs. Searched by bisection over candle closes, then verified; a failed verification restarts the
    search after it. Returns (Timestamp or None, number of evaluations)."""
    from signal_library.replay import CERTIFICATION, ReplayRun

    probe = ReplayRun(CERTIFICATION, run.candles_source, flows=run.flows_source, indicators=run.indicators)
    probe._histories = run._histories                  # share the loaded data, not the results
    lo, evaluations = 0, 0
    for _ in range(MAX_RESTARTS):
        hi = len(candidates)
        a, b = lo, hi
        while a < b:                                   # first index that reads, assuming readings persist
            mid = (a + b) // 2
            evaluations += 1
            if _readable(probe, ref, kind, asset_id, candidates[mid]):
                b = mid
            else:
                a = mid + 1
        if a >= hi:
            return None, evaluations
        failed = None
        for j in range(a + 1, min(hi, a + 1 + CONFIRM_READINGS)):
            evaluations += 1
            if not _readable(probe, ref, kind, asset_id, candidates[j]):
                failed = j
                break
        if failed is None:
            return candidates[a], evaluations
        lo = failed + 1
    return None, evaluations


def _signal_start(run, definition, ref, kind: str, asset_id: str, flow_starts: dict, end) -> dict:
    """Where this signal's history starts in this run, kept apart:
    source_from: the first time its input data exists (candle closes, first live flow sighting);
    from: the first time it is CONFIRMED to produce readings (warm-up, confirmation periods and other timeframes
    included), found by evaluating it. Coverage levels use `from` only."""
    out = {"source_from": None, "from": None, "limited": False, "reason": None, "method": None}
    if "derivatives" in definition.requires:
        return {**out, "reason": "derivatives are live only (no stored history)"}
    if "capital_flows" in definition.requires and not dict(ref.params).get("point_in_time"):
        return {**out, "reason": "non point-in-time flows are live only"}
    if run.check_certification:
        cert = certification.status(definition.key, ref.timeframe)
        if cert.get("algorithm") != "certified":
            return {**out, "reason": f"not certified: {cert.get('reason')}"}
    end = utc(end)
    if "capital_flows" in definition.requires:
        start = flow_starts.get(definition.id)
        if start is None:
            return {**out, "reason": "no stored history"}
        out["source_from"] = utc(start)
        if run.flows_source is None:
            return {**out, "reason": "source data exists; readings not confirmed (no flow data in this run)"}
        days = pd.date_range(utc(start).normalize(), end, freq="D")
        candidates = [d + pd.Timedelta(hours=23, minutes=59, seconds=59) for d in days]
        candidates = [c for c in candidates if c <= end]
    else:
        timeframes = [ref.timeframe]
        if "signals" in definition.requires:          # multi-timeframe alignment reads several timeframes
            from signal_library.signals_ta import MTF_SETS
            timeframes = list(MTF_SETS[dict(ref.params).get("set", "all")])
        starts = []
        for tf in timeframes:
            history = run.history(kind, asset_id, tf)
            if isinstance(history, CandleHistory) and len(history.raw):
                starts.append(pd.Timestamp(int(history.ends[0]), tz="UTC"))
                out["limited"] = out["limited"] or history.source.get("quality") == RECONSTRUCTED_LIMITED
        if not starts:
            return {**out, "reason": "no candle history"}
        out["source_from"] = min(starts)
        base = run.history(kind, asset_id, ref.timeframe)
        if not isinstance(base, CandleHistory):
            return {**out, "reason": f"no {ref.timeframe} candle history"}
        candidates = [pd.Timestamp(int(x), tz="UTC") for x in base.ends if x <= end.value]
    first, evaluations = _first_reading(run, ref, kind, asset_id, candidates)
    out["method"] = (f"first reading confirmed by evaluation ({evaluations} evaluations; the first reading must be "
                     f"followed by {CONFIRM_READINGS} more)")
    if first is None:
        return {**out, "reason": "source data exists, but the signal never produced a confirmed reading"}
    out["from"] = first
    return out


SOURCE_ONLY = "source data present, but no confirmed reading yet (warm-up, confirmation or other timeframes)"


def _periods(items: dict, end, critical: set) -> list[dict]:
    """items: key -> {"source_from", "from", "limited", "reason"}. Levels use the confirmed `from` only; the source
    start adds a boundary so the period where data exists but readings do not is shown as such."""
    starts = sorted({i[k] for i in items.values() for k in ("source_from", "from") if i.get(k) is not None})
    if not any(i["from"] is not None for i in items.values()):
        return [{"from": None, "to": None, "level": "live_only", "missing": sorted(items), "critical_missing":
                 sorted(k for k in items if k in critical),
                 "reasons": {k: i["reason"] or SOURCE_ONLY for k, i in items.items()}}]
    end = utc(end)
    out = []
    for n, begin in enumerate(starts):
        if begin >= end:
            break
        stop = starts[n + 1] if n + 1 < len(starts) else end
        present = {k for k, i in items.items() if i["from"] is not None and i["from"] <= begin}
        missing = sorted(set(items) - present)
        limited = any(items[k]["limited"] for k in present)
        level = "partially_evaluable" if missing else "reconstructed_with_limitations" if limited else "replayable"
        reasons = {}
        for k in missing:
            i = items[k]
            if i["reason"]:
                reasons[k] = i["reason"]
            elif i.get("source_from") is not None and i["source_from"] <= begin:
                reasons[k] = SOURCE_ONLY
            else:
                reasons[k] = "no source data yet at this time"
        out.append({"from": begin.isoformat(), "to": utc(stop).isoformat(), "level": level, "missing": missing,
                    "critical_missing": [k for k in missing if k in critical], "reasons": reasons})
    merged = []
    for p in out:                                       # join neighbouring ranges that read the same
        if merged and all(merged[-1][k] == p[k] for k in ("level", "missing", "critical_missing", "reasons")):
            merged[-1]["to"] = p["to"]
        else:
            merged.append(p)
    return merged


def _member_view(i: dict, critical: bool) -> dict:
    iso_ = (lambda x: None if x is None else x.isoformat())
    return {"source_from": iso_(i.get("source_from")), "confirmed_from": iso_(i["from"]), "limited": i["limited"],
            "reason": i["reason"], "method": i.get("method"), "critical": critical}


EVALUABILITY_NOTE = ("Levels use the first time each member is confirmed to produce readings (found by evaluating it), "
                     "not the first time its source data exists. Inside a replayable range an individual date can "
                     "still lack a reading; the completeness of a replay at that date says so.")


def group_coverage(doc: dict, run, kind: str, asset_id: str, *, end=None, flow_starts: dict | None = None) -> dict:
    """Date ranges for one Group on one asset in this run's data, each with a level and what is missing."""
    from .evaluate import _ref

    end = end or pd.Timestamp.now(tz="UTC")
    items = {}
    for m in doc.get("members") or []:
        ref = _ref(m)
        items[m["key"]] = _signal_start(run, sl.REGISTRY.get(ref.id, ref.version), ref, kind, asset_id,
                                        flow_starts or {}, end)
    critical = set(critical_members(doc))
    return {"subject": f"{kind}:{asset_id}", "periods": _periods(items, end, critical),
            "members": {k: _member_view(i, k in critical) for k, i in items.items()},
            "evaluability": EVALUABILITY_NOTE,
            "computed_from": "certification records, the history each source has in this run, and evaluation",
            "certification": certification.suite_reference()}


def set_coverage(doc: dict, run, kind: str, asset_id: str, *, end=None, flow_starts: dict | None = None) -> dict:
    """Each Group's coverage, and the Set's own: date ranges over every Group member, standalone item and
    applicable market item."""
    from .evaluate import _ref
    from .sets import APPLIES

    end = end or pd.Timestamp.now(tz="UTC")
    items, critical, groups = {}, set(), {}
    for g in doc.get("groups") or []:
        cov = group_coverage(g["snapshot"], run, kind, asset_id, end=end, flow_starts=flow_starts)
        groups[g["key"]] = cov
        for key, info in cov["members"].items():
            items[f"{g['key']}.{key}"] = {
                "source_from": None if info["source_from"] is None else utc(info["source_from"]),
                "from": None if info["confirmed_from"] is None else utc(info["confirmed_from"]),
                "limited": info["limited"], "reason": info["reason"]}
            if info["critical"]:
                critical.add(f"{g['key']}.{key}")
    for section, subject_kind in (("standalone", kind), ("market_context", "market")):
        for item in doc.get(section) or []:
            if section == "market_context":
                if kind not in APPLIES.get(item.get("applies_to", "all"), ("crypto", "equity")):
                    continue
                if item.get("data_modes") == ["live"]:
                    items[item["key"]] = {"source_from": None, "from": None, "limited": False,
                                          "reason": "this item is live only"}
                    continue
            ref = _ref(item)
            sub_id = item["subject"].split(":", 1)[1] if section == "market_context" else asset_id
            items[item["key"]] = _signal_start(run, sl.REGISTRY.get(ref.id, ref.version), ref, subject_kind, sub_id,
                                               flow_starts or {}, end)
    return {"subject": f"{kind}:{asset_id}", "periods": _periods(items, end, critical), "groups": groups,
            "items": {k: _member_view(i, k in critical) for k, i in items.items()},
            "evaluability": EVALUABILITY_NOTE,
            "computed_from": "certification records, the history each source has in this run, and evaluation",
            "certification": certification.suite_reference()}


def flow_history_start(supabase, source: str, series: str):
    """First time a stored flow observation was seen live (not backfilled): the start of its replayable history."""
    rows = (supabase.table("capital_flow_observations").select("fetched_at").eq("source", source)
            .eq("series", series).eq("backfilled", False).order("fetched_at").limit(1).execute().data or [])
    return utc(rows[0]["fetched_at"]) if rows else None


__all__ = ["POINT_IN_TIME", "POINT_IN_TIME_MODE", "LEVELS", "availability", "context_problem", "critical_members",
           "flow_history_start", "group_completeness", "group_coverage", "rule_members", "set_completeness",
           "set_coverage"]
