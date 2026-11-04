"""
Group evaluation (design sections 3 and 4). On demand, live mode only; uses the Signal Library engine, so a signal
used several times (or by several Groups in a Set) is calculated once.

The result keeps every member's full SignalResult (status, confirmation, observed_at, available_at, backfilled,
provenance, evidence) and adds its role, transform output, weight and observation state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction

import pandas as pd

import signal_library as sl
from signal_library.context import confirmed_frame

from . import lineage, replay, rules, transforms
from .transforms import UNKNOWN
from .validate import validate_group

AVAILABLE = ("ok",)
KNOWN_REDUNDANCY = {
    frozenset({"trend.direction", "momentum.direction"}):
        "Trend and momentum direction agree about 80% of the time when both point a direction (development data).",
}


def _ref(member: dict) -> sl.SignalRef:
    r = member["ref"]
    return sl.SignalRef.make(sl.REGISTRY.get(r["id"], r["version"]), r["timeframe"], **dict(r.get("params") or {}))


def _frac(x) -> Fraction:
    return Fraction(str(x))


def evaluate_group(doc: dict, ctx: sl.DataContext, *, data_mode: str = "live", as_of=None,
                   results: dict | None = None, validated: bool = False) -> dict:
    """Evaluate one Group on one subject. `results` (instance_key -> SignalResult) lets a Set share evaluations."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    base = {"name": doc.get("name"), "subject": ctx.subject, "data_mode": data_mode, "evaluated_at": now,
            "as_of": now if as_of is None else str(as_of), "lineage_version": doc.get("lineage_version")}
    pit = data_mode == replay.POINT_IN_TIME_MODE
    if data_mode not in ("live", replay.POINT_IN_TIME_MODE):
        return {**base, "status": "unsupported", "reason": f"Unknown data mode {data_mode!r}."}
    if pit:
        problem = replay.context_problem(ctx, as_of)
        if problem:
            return {**base, "status": "unsupported", "reason": problem}
        base["as_of"] = ctx.as_of.isoformat()
        base["replay_mode"] = ctx.replay.mode
    elif getattr(ctx, "replay", None) is not None:
        return {**base, "status": "unsupported", "reason": "A replay context needs data_mode='point_in_time'."}
    if not validated:
        errors = validate_group(doc)
        if errors:
            return {**base, "status": "invalid", "errors": errors}
    roots_table = lineage.table(doc["lineage_version"])
    members = doc["members"]
    refs = {m["key"]: _ref(m) for m in members}
    pending = [r for r in refs.values() if results is None or r.instance_key not in results]
    fresh = sl.evaluate(pending, ctx) if pending else {}
    pool = {**(results or {}), **fresh}
    if results is not None:
        results.update(fresh)

    def candles_since(key, event):
        member = next(m for m in members if m["key"] == key)
        when = event.get("confirmed_at")
        if not when:
            return None
        frame = confirmed_frame(ctx.candles(member["ref"]["timeframe"]))
        if frame is None or frame.empty:
            return None
        stamp = pd.Timestamp(when)
        index = frame.index if frame.index.tz is not None else frame.index.tz_localize("UTC")
        return int((index >= stamp).sum())

    # ------------------------------------------------------------------ members and score
    rows, rule_members = [], {}
    w_enabled = w_observed = w_imputed = Fraction(0)
    weighted_sum = Fraction(0)
    score_support = set()
    for m in members:
        ref = refs[m["key"]]
        res = pool[ref.instance_key]
        available = res.status in AVAILABLE
        row = {"key": m["key"], "label": m.get("label"), "role": m["role"], "category": m.get("category"),
               "instance": ref.instance_key, "lineage": sorted(roots_table[ref.id]), "signal": res.as_dict()}
        rule_members[m["key"]] = {"available": available, "value": res.value, "instance": ref.instance_key,
                                  "roots": set(roots_table[ref.id])}
        if m["role"] == "score":
            w = _frac(m["weight"])
            row["weight"] = float(w)
            if w == 0:
                row["state"] = "disabled"
            else:
                w_enabled += w
                score_support.add(ref.instance_key)
                c, flags = (UNKNOWN, [])
                if available:
                    c, flags = transforms.apply(m["transform"], res.value, lambda e, k=m["key"]: candles_since(k, e))
                row["flags"] = flags
                if c is UNKNOWN:
                    row["unobserved_reason"] = "unavailable" if not available else "transform_unknown"
                    if m["when_unavailable"] == "neutral":
                        w_imputed += w
                        row["state"], row["contribution"] = "imputed", 0.0
                    else:
                        row["state"] = "excluded"
                else:
                    w_observed += w
                    weighted_sum += w * _frac(c)
                    row["state"], row["contribution"] = "observed", float(c)
        if pit:
            row["replay_availability"] = replay.availability(res.status)
        rows.append(row)

    score_block = None
    score_value = None
    if doc.get("score") is not None:
        mc = doc["score"]["min_coverage"]
        withheld = None
        if w_enabled == 0:
            withheld = "no_enabled_members"
        elif w_observed == 0:
            withheld = "all_unavailable"
        elif w_observed * mc["den"] < w_enabled * mc["num"]:
            withheld = "below_min_coverage"
        if withheld is None:
            score_value = float(weighted_sum / (w_observed + w_imputed))
        score_block = {"value": score_value, "withheld": withheld, "meaning": doc["score"]["meaning"],
                       "observed_coverage": float(w_observed / w_enabled) if w_enabled else 0.0,
                       "weights": {"enabled": float(w_enabled), "observed": float(w_observed), "imputed": float(w_imputed)},
                       "min_coverage": mc}
        for row in rows:
            if row.get("state") in ("observed", "imputed") and (w_observed + w_imputed):
                row["weight_share"] = float(_frac(row["weight"]) / (w_observed + w_imputed))

    # ------------------------------------------------------------------ conditions
    rctx = rules.Context(rule_members, score_value, score_support,
                         {r["instance"]: set(r["lineage"]) for r in rows}, candles_since)
    conditions = []
    for c in doc.get("conditions") or []:
        value, support, roots = rules.evaluate(c["rule"], rctx)
        if c["kind"] == "veto":
            state = "active" if value is True else "clear" if value is False else "unknown"
        else:
            state = "met" if value is True else "not_met" if value is False else "unknown"
        conditions.append({"key": c["key"], "label": c.get("label"), "kind": c["kind"], "state": state,
                           "sources": sorted(roots)})

    vetoes = [c for c in conditions if c["kind"] == "veto"]
    if any(v["state"] == "active" for v in vetoes):
        status = "vetoed"
    elif any(v["state"] == "unknown" for v in vetoes):
        status = "veto_unknown"
    elif score_block is not None and score_block["value"] is None:
        status = "insufficient"
    else:
        status = "ok"

    out = {**base, "status": status, "score": score_block, "conditions": conditions, "members": rows,
           "diagnostics": _diagnostics(rows, score_value, members)}
    if pit:
        out["completeness"] = replay.group_completeness(doc, out, ctx)
    return out


def _diagnostics(rows: list, score, members: list) -> dict:
    scoring = [r for r in rows if r.get("state") == "observed"]
    out = {}
    if score is not None and scoring:
        sign = (score > 0) - (score < 0)
        total = sum(r["weight"] for r in scoring)
        agree = [r for r in scoring if sign and ((r["contribution"] > 0) - (r["contribution"] < 0)) == sign]
        out["agreement"] = {
            "share_of_observed_weight": round(sum(r["weight"] for r in agree) / total, 4) if total and sign else None,
            "agreeing": [r["key"] for r in agree],
            "opposing": [r["key"] for r in scoring if sign and r["contribution"] * sign < 0],
            "zero": [r["key"] for r in scoring if r["contribution"] == 0],
        }
        roots = set().union(*(set(r["lineage"]) for r in agree)) if agree else set()
        out["source_separation"] = {
            "sources_behind_agreement": sorted(roots),
            "note": ("All agreeing members derive from price: this is consistency between views of one source, "
                     "not independent confirmation.") if roots == {"price"} else
                    "Distinct sources are not statistical independence; they can still be correlated.",
        }
    by_cat: dict = {}
    for r in scoring:
        by_cat.setdefault(r.get("category"), set()).add((r["contribution"] > 0) - (r["contribution"] < 0))
    out["category_conflicts"] = sorted(str(c) for c, signs in by_cat.items() if {1, -1} <= signs)
    seen: dict = {}
    for r in rows:
        seen.setdefault(r["instance"], []).append(r["key"])
    out["duplicates"] = [keys for keys in seen.values() if len(keys) > 1]
    ids = {m["ref"]["id"] for m in members}
    out["known_redundancy"] = [note for pair, note in KNOWN_REDUNDANCY.items() if pair <= ids]
    observed_at = [r["signal"]["observed_at"] for r in rows if r["signal"].get("observed_at")]
    available_at = [r["signal"]["available_at"] for r in rows if r["signal"].get("available_at")]
    out["timing"] = {"oldest_observed_at": min(observed_at) if observed_at else None,
                     "newest_available_at": max(available_at) if available_at else None,
                     "unavailable": [r["key"] for r in rows if r["signal"]["status"] not in AVAILABLE]}
    return out
