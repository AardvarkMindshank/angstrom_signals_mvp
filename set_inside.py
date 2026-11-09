"""🔍 Look inside a Set: the building blocks it is made of, in plain words (Prism's library, provided and own Sets).

Its Groups (with their signals and labels), its single signals (with any settings and the asset they are pinned
to), and its decision written out, from the Set document itself, so it always shows exactly what runs.
"""

from __future__ import annotations

import re

import lattice_editor as le
from signal_groups.units import score_to_display

_TF = {"15m": "15-minute", "1h": "hourly", "4h": "4-hour", "1D": "daily", "1W": "weekly"}
_STATES = {"met": "met", "not_met": "not met", "active": "active", "clear": "clear"}


def _clean(name: str) -> str:
    return re.sub(r"\s*\((weekly, )?with labels\)", lambda m: " (weekly)" if m.group(1) else "", str(name or "")).strip()


def _on(subject) -> str:
    return f" on {subject['id'].upper() if subject.get('kind') == 'equity' else subject['id']}" if subject else ""


def _signal(ref: dict) -> str:
    return le._name_of(ref["id"])


def _settings(params: dict) -> str:
    return ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in sorted((params or {}).items()))


def parts(doc: dict) -> dict:
    groups = []
    for g in doc.get("groups") or []:
        snap = g.get("snapshot") or {}
        out = snap.get("outcomes") or {}
        labels = [r["label"] for r in out.get("rules") or []] + ([out["otherwise"]["label"]] if out.get("otherwise") else [])
        groups.append({
            "name": _clean(snap.get("name") or g["key"]) + _on(g.get("subject")),
            "signals": [f"{m.get('label') or _signal(m['ref'])} ({_TF.get(m['ref'].get('timeframe'), m['ref'].get('timeframe'))}"
                        + (", " + _settings(m["ref"].get("params")) if m["ref"].get("params") else "") + ")"
                        + ("" if m.get("role") == "score" else f" · {m.get('role')}")
                        for m in snap.get("members") or []],
            "labels": labels, "score": snap.get("score") is not None})
    signals = [{"name": f"{_signal(m['ref'])} ({_TF.get(m['ref'].get('timeframe'), m['ref'].get('timeframe'))})"
                        + _on(m.get("subject")),
                "settings": _settings(m["ref"].get("params"))}
               for m in doc.get("standalone") or []]
    rule = (doc.get("decision") or {}).get("rule")
    return {"groups": groups, "signals": signals, "decision": decision_words(doc, rule) if rule else ""}


def decision_words(doc: dict, rule: dict) -> str:
    groups = {g["key"]: g for g in doc.get("groups") or []}
    items = {m["key"]: m for m in doc.get("standalone") or []}

    def gname(key):
        g = groups.get(key) or {}
        return _clean((g.get("snapshot") or {}).get("name") or key) + _on(g.get("subject"))

    def label(key, oid):
        out = ((groups.get(key) or {}).get("snapshot") or {}).get("outcomes") or {}
        for r in (out.get("rules") or []) + ([out["otherwise"]] if out.get("otherwise") else []):
            if r["id"] == oid:
                return r["label"]
        return "Vetoed" if oid == "vetoed" else oid

    def choice(spec, f):
        vals = [spec["eq"]] if "eq" in spec else spec.get("in") or []
        return " or ".join(f(v) for v in vals)

    def num(spec, scale=False):
        show = (lambda v: score_to_display(v)) if scale else (lambda v: f"{v:g}" if isinstance(v, (int, float)) else str(v))
        parts_ = []
        if "gte" in spec:
            parts_.append(f"is at least {show(spec['gte'])}")
        if "lte" in spec:
            parts_.append(f"is at most {show(spec['lte'])}")
        if "between" in spec:
            parts_.append(f"is between {show(spec['between'][0])} and {show(spec['between'][1])}")
        if spec.get("exists") is True:
            parts_.append("has a value")
        if "eq" in spec:
            parts_.append("is yes" if spec["eq"] is True else "is no" if spec["eq"] is False else f"is {spec['eq']}")
        return " and ".join(parts_)

    def words(r) -> str:
        for combo, joint in (("all", " and "), ("any", " or ")):
            if combo in r:
                bits = [words(x) for x in r[combo]]
                return bits[0] if len(bits) == 1 else "(" + joint.join(bits) + ")"
        if "not" in r:
            inner = words(r["not"])
            return inner.replace(" is ", " is not ", 1) if " is " in inner and not inner.startswith("(") \
                else "not " + inner
        if "sequence" in r:
            q = r["sequence"]
            text = f"{words(q['first'])} on an earlier close, then {words(q['then'])} within {q['within']} daily closes"
            return text + (f" (unless {words(q['cancel'])} in between)" if q.get("cancel") else "")
        if "group" in r:
            k = r["group"]
            if "outcome" in r:
                return f"{gname(k)} label is {choice(r['outcome'], lambda v: label(k, v))}"
            if "score" in r:
                return f"{gname(k)} score {num(r['score'], scale=True)}"
            if "condition" in r:
                cond = next((c for c in (groups.get(k) or {}).get("snapshot", {}).get("conditions") or []
                             if c["key"] == r["condition"]), {})
                return f"{gname(k)}: “{cond.get('label') or r['condition']}” is {choice(r['state'], _STATES.get)}"
            return f"{gname(k)} status is {choice(r['status'], str)}"
        m = items.get(r.get("member")) or {}
        name = _signal(m["ref"]) + _on(m.get("subject")) if m else str(r.get("member"))
        field = f" {r['field'].replace('.0.', ' (nearest) ').replace('_', ' ')}" if r.get("field") else ""
        if "events" in r:
            return f"{name}{field} has a matching event"
        return f"{name}{field} {num(r)}"

    text = words(rule)
    if text.startswith("(") and text.endswith(")") and ("all" in rule or "any" in rule):
        text = text[1:-1]
    return "Yes when " + text + "."
