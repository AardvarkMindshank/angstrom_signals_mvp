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

from . import decision, lineage, replay, rules, sequence
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


def _parts(doc: dict, ctx, subject_context, data_mode: str, pit: bool, keep: tuple | None = None):
    """(Group entries, standalone items, their refs, their results) at ctx's moment. keep: (Group keys, standalone
    keys) to read, for the earlier closes of a sequence; everything when None."""
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
        if keep is not None and g["key"] not in keep[0]:
            continue
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

    items = [i for i in doc.get("standalone") or [] if keep is None or i["key"] in keep[1]]
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
    return groups, items, refs, results_for


def _members(items, refs, results_for, table) -> rules.Context:
    members = {}
    for i in items:
        res = results_for[i["key"]]
        members[i["key"]] = {"available": res.status in AVAILABLE, "value": res.value,
                             "instance": refs[i["key"]].instance_key, "roots": set(table[refs[i["key"]].id])}
    return rules.Context(members, None, set(), {m["instance"]: m["roots"] for m in members.values()},
                         lambda key, event: None)


def _past(doc: dict, ctx, earlier, data_mode: str, pit: bool, table, cache: dict | None = None) -> list | None:
    """The earlier closes a sequence reads, newest first, as (groups, members); None for a close that could not be
    read. None when there is no way to read earlier closes here. cache: day -> reading, kept by a caller that works
    out many days in a row (each earlier close is then read once)."""
    n = sequence.longest(doc.get("decision"))
    if not n or earlier is None:
        return None
    keep = sequence.needs(doc["decision"]["rule"])
    days = sequence.closes(ctx, n)
    if not days:                       # the scanned asset's own candles could not be read
        return None
    out = []
    for day in days[1:]:
        if cache is not None and day in cache:
            out.append(cache[day])
            continue
        try:
            past_ctx, past_subjects = earlier(day)
            groups, items, refs, results_for = _parts(doc, past_ctx, past_subjects, data_mode, pit, keep)
            got = ({g["key"]: g["result"] for g in groups}, _members(items, refs, results_for, table))
        except Exception:
            got = None
        if cache is not None:
            cache[day] = got
        out.append(got)
    return out


def evaluate_set(doc: dict, ctx: sl.DataContext, *, market_context=None, data_mode: str = "live",
                 subject_context=None, earlier=None, earlier_cache: dict | None = None) -> dict:
    """`market_context(scope)` returns a DataContext for a market subject such as "market:bitcoin".
    `subject_context(kind, asset_id)` returns a DataContext for a fixed subject (E4, lattice_prism.md §4.4), read at
    the same moment as `ctx`. Without it, items with a fixed subject are unavailable and their predicates unknown.
    `earlier(day)` returns (context, subject_context) at the close of the earlier daily candle starting `day`, read as
    known then; sequences need it (docs/design/sequences.md). Without it, every sequence is undecided."""
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
    groups, items, refs, results_for = _parts(doc, ctx, subject_context, data_mode, pit)
    standalone = []
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
        mctx = _members(items, refs, results_for, table)
        out["decision"] = decision.evaluate(doc["decision"], {g["key"]: g["result"] for g in groups}, mctx,
                                            _past(doc, ctx, earlier, data_mode, pit, table,
                                                  earlier_cache))
    if pit:
        out["completeness"] = replay.set_completeness(out, ctx)
    return out
