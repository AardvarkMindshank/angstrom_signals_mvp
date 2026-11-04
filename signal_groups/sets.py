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

from . import lineage
from . import replay
from .evaluate import _ref, evaluate_group
from .validate import validate_set

APPLIES = {"crypto": ("crypto",), "equity": ("equity",), "all": ("crypto", "equity")}


def canonical(body) -> bytes:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_sha256(body) -> str:
    return hashlib.sha256(canonical(body)).hexdigest()


def evaluate_set(doc: dict, ctx: sl.DataContext, *, market_context=None, data_mode: str = "live") -> dict:
    """`market_context(scope)` returns a DataContext for a market subject such as "market:bitcoin"."""
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
    groups = []
    for g in doc.get("groups") or []:
        result = evaluate_group(g["snapshot"], ctx, results=shared, validated=True, data_mode=data_mode,
                                as_of=ctx.as_of if pit else None)
        groups.append({"key": g["key"], "provenance": g.get("provenance"), "result": result})

    standalone = []
    items = list(doc.get("standalone") or [])
    refs = {i["key"]: _ref(i) for i in items}
    got = sl.evaluate([r for r in refs.values() if r.instance_key not in shared], ctx)
    shared.update(got)
    for i in items:
        standalone.append({"key": i["key"], "label": i.get("label"), "role": i["role"],
                           "signal": shared[refs[i["key"]].instance_key].as_dict()})

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
    if pit:
        out["completeness"] = replay.set_completeness(out, ctx)
    return out
