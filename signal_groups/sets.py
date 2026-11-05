"""
Signal Sets (design section 5): embedded Group snapshots, standalone signals and market context, side by side.
No Set score in this version. Signals shared between Groups are evaluated once; the diagnostics report instances and
sources that several Groups rely on, so a Set cannot hide duplicated evidence.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import signal_library as sl

from . import decision, lineage, replay, rules
from .evaluate import AVAILABLE, _ref, evaluate_group
from .validate import validate_set

APPLIES = {"crypto": ("crypto",), "equity": ("equity",), "all": ("crypto", "equity")}


def canonical(body) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_sha256(body) -> str:
    return hashlib.sha256(canonical(body)).hexdigest()


def scannable(doc: dict) -> bool:
    """Prism scans only Sets with a decision (docs/design/lattice_prism.md §4.2); a Set without one is never No."""
    return isinstance(doc, dict) and doc.get("decision") is not None


def evaluate_set(doc: dict, ctx: sl.DataContext, *, market_context=None, data_mode: str = "live",
                 subject_context=None) -> dict:
    """`market_context(scope)` returns a DataContext for a market subject such as "market:bitcoin".
    `subject_context(kind, asset_id)` returns a DataContext for a fixed subject (E4, lattice_prism.md §4.4), read at
    the same moment as `ctx`. Without it, items with a fixed subject are unavailable and their predicates unknown."""
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    base = {"name": doc.get("name"), "subject": ctx.subject, "data_mode": data_mode, "evaluated_at": now,
            "lineage_version": doc.get("lineage_version"), "score": None}
    pit = data_mode == replay.POINT_IN_TIME_MODE
    if data_mode not in ("live", replay.POINT_IN_TIME_MODE):
        return {**base, "status": "unsupported", "reason": f"Unknown data mode {data_mode!r}."}
    if pit:
        problem = replay.context_problem(ctx, None)
        if problem:
            return {**base, "status": "unsupported", "reason": problem}
        base["as_of"] = ctx.as_of.isoformat()
        base["replay_mode"] = ctx.replay.mode
    elif getattr(ctx, "replay", None) is not None:
        return {**base, "status": "unsupported", "reason": "A replay context needs data_mode='point_in_time'."}
    errors = validate_set(doc)
    if errors:
        return {**base, "status": "invalid", "errors": errors}
    shared: dict = {}
    by_subject: dict = {}        # fixed subjects: their own contexts and shared results, never mixed with ctx's
    subject_problem = {}

    def context_for(item):
        subject = item.get("subject")
        if not subject:
            return ctx, shared
        key = f"{subject['kind']}:{subject['id']}"
        if key not in by_subject:
            sub_ctx = None
            if subject_context is not None:
                try:
                    sub_ctx = subject_context(subject["kind"], subject["id"])
                except Exception as exc:            # a refused reconstruction or a missing source
                    subject_problem[key] = str(exc)[:200]
            elif not subject_problem.get(key):
                subject_problem[key] = "no data source for a fixed subject here"
            by_subject[key] = (sub_ctx, {})
        return by_subject[key]

    groups = []
    for g in doc.get("groups") or []:
        g_ctx, g_shared = context_for(g)
        entry = {"key": g["key"], "provenance": g.get("provenance")}
        if g.get("subject"):
            entry["subject"] = g["subject"]
        if g_ctx is None:
            key = f"{g['subject']['kind']}:{g['subject']['id']}"
            entry["result"] = {"status": "unsupported", "reason": subject_problem.get(key, "no data"),
                               "subject": key, "members": [], "conditions": []}
        else:
            entry["result"] = evaluate_group(g["snapshot"], g_ctx, results=g_shared, validated=True,
                                             data_mode=data_mode, as_of=ctx.as_of if pit else None)
        groups.append(entry)

    standalone = []
    items = list(doc.get("standalone") or [])
    refs = {i["key"]: _ref(i) for i in items}
    results_for: dict = {}
    for i in items:
        i_ctx, i_shared = context_for(i)
        ref = refs[i["key"]]
        if i_ctx is None:
            key = f"{i['subject']['kind']}:{i['subject']['id']}"
            results_for[i["key"]] = sl.core.SignalResult(
                ref={}, subject=key, status=sl.core.MISSING, notes=[subject_problem.get(key, "no data")])
            continue
        if ref.instance_key not in i_shared:
            i_shared.update(sl.evaluate([ref], i_ctx))
        results_for[i["key"]] = i_shared[ref.instance_key]
    for i in items:
        entry = {"key": i["key"], "label": i.get("label"), "role": i["role"], "signal": results_for[i["key"]].as_dict()}
        if i.get("subject"):
            entry["subject"] = i["subject"]
        standalone.append(entry)

    market = []
    for i in doc.get("market_context") or []:
        entry = {"key": i["key"], "label": i.get("label"), "role": i["role"], "subject": i["subject"],
                 "data_modes": i.get("data_modes")}
        if ctx.kind not in APPLIES.get(i.get("applies_to", "all"), ("crypto", "equity")):
            entry["skipped"] = f"applies to {i.get('applies_to')} only"
        elif pit and i.get("data_modes") == ["live"]:
            entry["skipped"] = "this item is live only (current context, not replayable)"
        elif market_context is None:
            entry["skipped"] = "no market data source configured"
        else:
            ref = _ref(i)
            mctx = market_context(i["subject"])
            problem = replay.context_problem(mctx, ctx.as_of) if pit else None
            if problem:
                entry["skipped"] = problem
            else:
                entry["signal"] = sl.evaluate([ref], mctx)[ref.instance_key].as_dict()
        market.append(entry)

    # ------------------------------------------------------------------ cross-Group diagnostics
    table = lineage.table(doc["lineage_version"])
    used: dict = {}
    sources: dict = {}
    for g in groups:
        for m in g["result"].get("members") or []:
            used.setdefault(m["instance"], set()).add(g["key"])
            for root in m["lineage"]:
                sources.setdefault(root, set()).add(g["key"])
    for i in items:
        used.setdefault(refs[i["key"]].instance_key, set()).add(f"standalone:{i['key']}")
        for root in table[refs[i["key"]].id]:
            sources.setdefault(root, set()).add(f"standalone:{i['key']}")
    diagnostics = {
        "shared_signals": sorted([inst, sorted(where)] for inst, where in used.items() if len(where) > 1),
        "sources_by_part": {root: sorted(where) for root, where in sorted(sources.items())},
        "note": ("Groups that rest on the same source are views of the same data, not independent confirmations. "
                 "Distinct sources are not statistical independence either."),
        "group_statuses": {g["key"]: g["result"]["status"] for g in groups},
    }
    out = {**base, "status": "ok", "groups": groups, "standalone": standalone, "market_context": market,
           "diagnostics": diagnostics}
    if doc.get("decision") is not None:
        # Optional (docs/design/lattice_prism.md §4.2): only Sets that define a decision gain this key.
        members = {}
        for i in items:
            res = results_for[i["key"]]
            members[i["key"]] = {"available": res.status in AVAILABLE, "value": res.value,
                                 "instance": refs[i["key"]].instance_key, "roots": set(table[refs[i["key"]].id])}
        mctx = rules.Context(members, None, set(), {m["instance"]: m["roots"] for m in members.values()},
                             lambda key, event: None)
        out["decision"] = decision.evaluate(doc["decision"], {g["key"]: g["result"] for g in groups}, mctx)
    if pit:
        out["completeness"] = replay.set_completeness(out, ctx)
    return out
