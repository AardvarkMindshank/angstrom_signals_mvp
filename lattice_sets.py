"""
Lattice Set editor: the logic behind the Set screen (docs/design/lattice_prism.md §4.2, §7; build stage 4, part 2).

A Set holds saved Group versions (embedded exactly, as the storage requires) and single signals, and a decision
that answers Yes, No or Unknown. The browser component draws and sends back a simple model; everything that decides
anything is here and in the engine's validator.

Set model:
    {"name", "purpose",
     "groups": [{"key", "source"}],                 # source: "saved:<config id>:<version>"
     "standalone": [{"key", "id", "version", "timeframe", "role"}],   # role: condition or context
     "lines": [ line | {"any": [line, ...]} ]}       # all lines must hold (ALL); an ANY box holds if any line holds
line:
    {"target": "outcome", "group", "op": "is" | "is_not", "value": outcome id}
    {"target": "score",   "group", "op": "gte" | "lte", "value": "+30"}          # shown −100..+100
    {"target": "status",  "group", "op": "is" | "is_not", "value": status}
    {"target": "member",  "member", "field", "op": "gte" | "lte" | "yes" | "no" | "is" | "is_not", "value"}
"""

from __future__ import annotations

import copy
import re

import lattice_editor as le
import perspectives
import signal_groups as sg
import signal_library as sl
from signal_groups import lineage
from signal_groups.units import score_from_display
from signal_library import fields

LINEAGE = 3
STATUSES = {"ok": "OK", "vetoed": "vetoed", "veto_unknown": "veto unknown", "insufficient": "not enough data"}
MAX_GROUPS, MAX_ITEMS, MAX_LINES = 10, 20, 20


# ----------------------------------------------------------------------------------------------- what can go in

def group_choices(saved: list[dict], user_id: str) -> dict:
    """source -> {name, body, provenance, owner, labels, has_score} for every readable saved Group version."""
    out = {}
    for c in saved:
        if c.get("kind") != "group":
            continue
        owner = "starter" if c.get("starter_alias") else ("yours" if c.get("owner_id") == user_id else "shared")
        for v in c["versions"]:
            body = v["body"]
            spec = body.get("outcomes") or {}
            labels = [(r["id"], r["label"]) for r in spec.get("rules") or []]
            if spec:
                labels.append((spec["otherwise"]["id"], spec["otherwise"]["label"]))
            out[f"saved:{c['id']}:{v['version']}"] = {
                "name": f"{c['name']} v{v['version']}", "owner": owner, "body": body,
                "provenance": {"source_config": c.get("starter_alias") or c["id"], "source_version": v["version"]},
                "labels": labels, "has_score": body.get("score") is not None,
                "members": [m.get("label") or m["ref"]["id"] for m in body.get("members") or []]}
    return out


def clean_subject(raw):
    """E4: {"kind": crypto | equity, "id"} or None. Share tickers are upper case."""
    if not isinstance(raw, dict) or raw.get("kind") not in ("crypto", "equity"):
        return None
    sid = str(raw.get("id") or "").strip()
    sid = sid.upper() if raw["kind"] == "equity" else sid.lower()
    return {"kind": raw["kind"], "id": sid} if re.match(r"^[A-Za-z0-9][A-Za-z0-9.\-_^=]{0,24}$", sid) else None


def subject_text(subject) -> str:
    if not subject:
        return ""
    return f" on {subject['id']}"


def empty_model() -> dict:
    return {"name": "My Set", "purpose": "", "groups": [], "standalone": [], "lines": []}


def _key(base: str, taken: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")[:30] or "item"
    base = base if base[0].isalpha() else f"g_{base}"[:30]
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


# ----------------------------------------------------------------------------------------------- cleaning

def _clean_line(raw, groups: set, members: set):
    if not isinstance(raw, dict):
        return None
    target = raw.get("target")
    op, value = str(raw.get("op") or ""), str(raw.get("value") if raw.get("value") is not None else "")[:40]
    if target in ("outcome", "status", "score") and raw.get("group") in groups:
        ops = ("gte", "lte") if target == "score" else ("is", "is_not")
        return {"target": target, "group": raw["group"], "op": op if op in ops else ops[0], "value": value}
    if target == "condition" and raw.get("group") in groups and re.match(r"^[a-z0-9_]{1,40}$", str(raw.get("condition") or "")):
        return {"target": "condition", "group": raw["group"], "condition": raw["condition"],
                "op": op if op in ("is", "is_not") else "is", "value": value}
    if target == "member" and raw.get("member") in members:
        return {"target": "member", "member": raw["member"], "field": str(raw.get("field") or "")[:60],
                "op": op if op in le.OPS else "gte", "value": value}
    return None


def clean_model(raw, choices: dict) -> dict:
    """The model sent by the browser, reduced to known Groups, signals, roles and limits."""
    raw = raw if isinstance(raw, dict) else {}
    cat = {s["id"]: s for s in le.catalogue()}
    model = {"name": str(raw.get("name") or "")[:80], "purpose": str(raw.get("purpose") or "")[:200],
             "groups": [], "standalone": [], "lines": []}
    taken: set = set()
    for g in (raw.get("groups") or [])[:MAX_GROUPS]:
        if isinstance(g, dict) and g.get("source") in choices:
            key = str(g.get("key") or "")
            if not re.match(r"^[a-z0-9_]{1,40}$", key) or key in taken:
                key = _key(choices[g["source"]]["name"].split(" v")[0], taken)
            taken.add(key)
            entry = {"key": key, "source": g["source"]}
            subject = clean_subject(g.get("subject"))
            if subject:
                entry["subject"] = subject
            model["groups"].append(entry)
    for m in (raw.get("standalone") or [])[:MAX_ITEMS]:
        if not isinstance(m, dict) or m.get("id") not in cat:
            continue
        s = cat[m["id"]]
        tf = m.get("timeframe") if m.get("timeframe") in s["timeframes"] else ("1D" if "1D" in s["timeframes"]
                                                                              else s["timeframes"][0])
        key = str(m.get("key") or "")
        if not re.match(r"^[a-z0-9_]{1,40}$", key) or key in taken:
            key = _key(f"{m['id'].split('.')[-1]}_{tf}", taken)
        taken.add(key)
        role = m.get("role") if m.get("role") in ("condition", "context") else "condition"
        entry = {"key": key, "id": s["id"], "version": s["version"], "timeframe": tf, "role": role}
        subject = clean_subject(m.get("subject"))
        if subject:
            entry["subject"] = subject
        model["standalone"].append(entry)
    gkeys = {g["key"] for g in model["groups"]}
    mkeys = {m["key"] for m in model["standalone"]}
    for line in (raw.get("lines") or [])[:MAX_LINES]:
        if isinstance(line, dict) and isinstance(line.get("any"), list):
            inner = [x for x in (_clean_line(l, gkeys, mkeys) for l in line["any"][:MAX_LINES]) if x]
            if inner:
                model["lines"].append({"any": inner})
        else:
            x = _clean_line(line, gkeys, mkeys)
            if x:
                model["lines"].append(x)
    return model


# ----------------------------------------------------------------------------------------------- model -> document

def _predicate(line: dict) -> dict:
    t, op, value = line["target"], line["op"], line.get("value")
    if t == "outcome":
        pred = {"group": line["group"], "outcome": {"eq": value}}
        return {"not": pred} if op == "is_not" else pred
    if t == "status":
        pred = {"group": line["group"], "status": {"eq": value}}
        return {"not": pred} if op == "is_not" else pred
    if t == "condition":
        pred = {"group": line["group"], "condition": line["condition"], "state": {"eq": value}}
        return {"not": pred} if op == "is_not" else pred
    if t == "score":
        try:
            v = score_from_display(value)
        except ValueError:
            n = le._number(value)
            v = n / 100 if n is not None else value
        return {"group": line["group"], "score": {op: v}}
    clause = {"operand": f"{line['member']}:{line.get('field') or ''}", "op": op, "value": value}
    return le._predicate(clause)


def to_document(model: dict, choices: dict) -> dict:
    groups = []
    for g in model.get("groups") or []:
        c = choices.get(g["source"])
        if c is None:
            continue
        entry = {"key": g["key"], "snapshot": copy.deepcopy(c["body"]), "provenance": dict(c["provenance"])}
        if g.get("subject"):
            entry["subject"] = dict(g["subject"])
        groups.append(entry)
    standalone = []
    for m in model.get("standalone") or []:
        entry = {"key": m["key"], "label": le._name_of(m["id"]), "role": m["role"],
                 "ref": {"id": m["id"], "version": m["version"], "timeframe": m["timeframe"], "params": {}}}
        if m.get("subject"):
            entry["subject"] = dict(m["subject"])
        standalone.append(entry)
    doc = {"schema": "angstrom.set/1", "name": (model.get("name") or "").strip() or "Untitled Set",
           "purpose": (model.get("purpose") or "").strip(), "lineage_version": LINEAGE, "score": None,
           "groups": groups, "standalone": standalone, "market_context": [],
           "notes": "Built in the Lattice editor."}
    lines = []
    for line in model.get("lines") or []:
        if "any" in line:
            preds = [_predicate(l) for l in line["any"]]
            lines.append(preds[0] if len(preds) == 1 else {"any": preds})
        else:
            lines.append(_predicate(line))
    if lines:
        doc["decision"] = {"version": 1, "rule": lines[0] if len(lines) == 1 else {"all": lines}}
    return doc


# ----------------------------------------------------------------------------------------------- what lines can test

def targets(model: dict, choices: dict) -> list[dict]:
    """Everything a decision line can test, for the screen."""
    out = []
    for g in model.get("groups") or []:
        c = choices.get(g["source"])
        if c is None:
            continue
        name = c["name"] + subject_text(g.get("subject"))
        if c["labels"]:
            out.append({"key": f"outcome:{g['key']}", "target": "outcome", "group": g["key"], "type": "label",
                        "label": f"{name} · label", "scale": "", "values": c["labels"] + [("vetoed", "Vetoed")]})
        if c["has_score"]:
            out.append({"key": f"score:{g['key']}", "target": "score", "group": g["key"], "type": "number",
                        "label": f"{name} · score", "scale": "−100 to +100", "values": []})
        for cond in c["body"].get("conditions") or []:
            states = [("met", "met"), ("not_met", "not met")] if cond["kind"] == "confirmation" else \
                [("active", "active"), ("clear", "clear")]
            kind = "confirmation" if cond["kind"] == "confirmation" else "veto"
            out.append({"key": f"condition:{g['key']}:{cond['key']}", "target": "condition", "group": g["key"],
                        "condition": cond["key"], "type": "label",
                        "label": f"{name} · {kind}: {cond.get('label') or cond['key']}", "scale": "", "values": states})
        out.append({"key": f"status:{g['key']}", "target": "status", "group": g["key"], "type": "label",
                    "label": f"{name} · status", "scale": "", "values": list(STATUSES.items())})
    cat = {(s["id"], s["version"]): s for s in le.catalogue()}
    for m in model.get("standalone") or []:
        if m["role"] != "condition":
            continue
        s = cat.get((m["id"], m["version"]))
        for o in (s or {}).get("operands") or []:
            kind = "standard score" if o["field"] == "standard_score" else o["label"]
            out.append({"key": f"member:{m['key']}:{o['field']}", "target": "member", "member": m["key"],
                        "field": o["field"], "type": o["type"],
                        "label": f"{s['name']} ({m['timeframe']}){subject_text(m.get('subject'))} · {kind}",
                        "scale": o["scale"], "values": [(l, l) for l in o["labels"]]})
    return out


# ----------------------------------------------------------------------------------------------- checks and words

def checks(model: dict, choices: dict) -> dict:
    blocks, warns = [], []
    if len(model.get("groups") or []) + len(model.get("standalone") or []) == 0:
        blocks.append("Add at least one Group or signal.")
    for g in model.get("groups") or []:
        if g["source"] not in choices:
            blocks.append("A Group in this Set can no longer be read.")
    known = {t["key"] for t in targets(model, choices)}
    for i, line in enumerate(model.get("lines") or []):
        for l in line.get("any", [line]):
            key = (f"member:{l['member']}:{l.get('field') or ''}" if l["target"] == "member" else
                   f"condition:{l['group']}:{l['condition']}" if l["target"] == "condition" else f"{l['target']}:{l['group']}")
            if key not in known:
                blocks.append(f"Line {i + 1} tests something this Set no longer has (or a Context item, which "
                              "rules cannot use).")
            if l["target"] == "score" or (l["target"] == "member" and l["op"] in ("gte", "lte")):
                if le._number(l.get("value")) is None:
                    blocks.append(f"Line {i + 1}: {l.get('value')!r} is not a number.")
    if not blocks:
        doc = to_document(model, choices)
        names = {g["key"]: choices[g["source"]]["name"] for g in model.get("groups") or [] if g["source"] in choices}
        names.update({m["key"]: f"{le._name_of(m['id'])} ({m['timeframe']})" for m in model.get("standalone") or []})
        for e in sg.validate_set(doc):
            text = e.replace("decision.rule: ", "").replace("decision: ", "")
            text = text.replace("outside the Group score range -1 to 1 (stored scale; +30 on screen is 0.30)",
                                "outside the Group score scale, −100 to +100")
            blocks.append(le._plain(text, names))
        if not model.get("lines"):
            warns.append("This Set has no decision yet, so Prism cannot scan it. Add at least one line.")
        warns += _shared(model, choices)
    fixed = [x for x in (model.get("groups") or []) + (model.get("standalone") or []) if x.get("subject")]
    if fixed:
        warns.append("Fixed assets are read at the same moment as the scanned asset. \"A, then B within N days\" "
                     "needs a strategy, which comes later.")
    used = {l.get("member") for line in model.get("lines") or [] for l in line.get("any", [line])}
    for m in model.get("standalone") or []:
        name = le._name_of(m["id"])
        if m["role"] == "condition" and m["key"] not in used:
            warns.append(f"{name} is a Condition, but no line uses it, so it changes nothing.")
        if "sentiment" in sl.REGISTRY.get(m["id"]).requires:
            warns.append(f"{name}: sentiment history starts in November 2026, so earlier dates will show it as missing.")
    return {"blocks": list(dict.fromkeys(blocks)), "warnings": list(dict.fromkeys(warns))}


def _shared(model: dict, choices: dict) -> list[str]:
    """Groups and signals that rest on the same readings: agreement between them is partly the same evidence."""
    uses: dict = {}
    for g in model.get("groups") or []:
        if g["source"] not in choices:
            continue
        for m in choices[g["source"]]["body"].get("members") or []:
            r = m["ref"]
            uses.setdefault((r["id"], r["timeframe"], str(g.get("subject"))), set()).add(choices[g["source"]]["name"])
    for m in model.get("standalone") or []:
        uses.setdefault((m["id"], m["timeframe"], str(m.get("subject"))), set()).add(f"{le._name_of(m['id'])} ({m['timeframe']})")
    out = []
    for (sid, tf, _subject), where in sorted(uses.items()):
        if len(where) > 1:
            out.append(f"{' and '.join(sorted(where))} both read {le._name_of(sid)} ({tf}). Agreement between them is "
                       "partly the same reading counted twice.")
    return out


def _line_text(l: dict, model: dict, choices: dict) -> str:
    groups = {g["key"]: {**choices[g["source"]], "name": choices[g["source"]]["name"] + subject_text(g.get("subject"))}
              for g in model.get("groups") or [] if g["source"] in choices}
    if l["target"] == "condition":
        c = groups.get(l["group"])
        cond = next((x for x in (c or {}).get("body", {}).get("conditions") or [] if x["key"] == l["condition"]), {})
        state = {"met": "met", "not_met": "not met", "active": "active", "clear": "clear"}.get(l["value"], l["value"])
        return f"{(c or {}).get('name', l['group'])} {cond.get('kind', 'check')} “{cond.get('label') or l['condition']}” {le.OPS[l['op']]} {state}"
    if l["target"] in ("outcome", "status", "score"):
        c = groups.get(l["group"])
        name = c["name"] if c else l["group"]
        if l["target"] == "score":
            return f"{name} score {le.OPS[l['op']]} {l['value']}"
        values = dict((c or {}).get("labels") or []) if l["target"] == "outcome" else STATUSES
        values = {**values, "vetoed": "Vetoed"}
        return f"{name} {'label' if l['target'] == 'outcome' else 'status'} {le.OPS[l['op']]} {values.get(l['value'], l['value'])}"
    m = next((x for x in model.get("standalone") or [] if x["key"] == l["member"]), None)
    clause = {"operand": f"{l['member']}:{l.get('field') or ''}", "op": l["op"], "value": l.get("value")}
    text = le._clause_text(clause, {l["member"]: m} if m else {})
    if m and m.get("subject"):
        text = text.replace(f"({m['timeframe']})", f"({m['timeframe']}){subject_text(m['subject'])}", 1)
    return text


def describe(model: dict, choices: dict) -> str:
    name = (model.get("name") or "").strip() or "This Set"
    lines = model.get("lines") or []
    if not lines:
        return f"{name} has no decision yet."
    parts = []
    for line in lines:
        if "any" in line:
            parts.append("any of (" + "; ".join(_line_text(l, model, choices) for l in line["any"]) + ")")
        else:
            parts.append(_line_text(line, model, choices))
    return (f"{name} says Yes when " + ", and ".join(parts) + ". If any line fails it says No, even with missing "
            "data; if nothing fails but something needed is missing, it says Unknown and names it.")


def state_for_screen(model: dict, choices: dict) -> dict:
    found = checks(model, choices)
    return {"model": copy.deepcopy(model), "targets": targets(model, choices), "checks": found,
            "description": describe(model, choices), "can_save": not found["blocks"],
            "scannable": bool(model.get("lines")) and not found["blocks"],
            "groups": [{"source": k, "name": v["name"], "owner": v["owner"], "labels": [l for _, l in v["labels"]],
                        "has_score": v["has_score"], "members": v["members"][:6],
                        "icons": perspectives.chips(v["body"])} for k, v in choices.items()],
            "member_tags": {m["key"]: le.member_tag(m) for m in model.get("standalone") or []}}


# ----------------------------------------------------------------------------------------------- document -> model

def _line(pred: dict):
    negate = "not" in pred
    p = pred["not"] if negate else pred
    if "group" in p and "condition" in p and set(p.get("state") or {}) == {"eq"}:
        return {"target": "condition", "group": p["group"], "condition": p["condition"],
                "op": "is_not" if negate else "is", "value": p["state"]["eq"]}
    if "group" in p:
        for target in ("outcome", "status"):
            if target in p and set(p[target]) == {"eq"}:
                return {"target": target, "group": p["group"], "op": "is_not" if negate else "is", "value": p[target]["eq"]}
        if "score" in p and not negate and len(p["score"]) == 1:
            (op, v), = p["score"].items()
            if op in ("gte", "lte"):
                return {"target": "score", "group": p["group"], "op": op, "value": le.score_to_display(v)}
        return None
    clause = le._clause(pred)
    if not clause:
        return None
    member, _, field = clause["operand"].partition(":")
    return {"target": "member", "member": member, "field": field, "op": clause["op"], "value": clause["value"]}


def from_document(doc: dict, choices: dict) -> tuple[dict | None, str | None]:
    model = {"name": doc.get("name") or "", "purpose": doc.get("purpose") or "", "groups": [], "standalone": [],
             "lines": []}
    by_prov = {(str(c["provenance"]["source_config"]), int(c["provenance"]["source_version"])): k
               for k, c in choices.items()}
    for g in doc.get("groups") or []:
        prov = g.get("provenance") or {}
        source = by_prov.get((str(prov.get("source_config")), int(prov.get("source_version") or 0)))
        if source is None:
            return None, f"Group {g['key']!r} comes from a version you cannot read here."
        model["groups"].append({"key": g["key"], "source": source, **({"subject": g["subject"]} if g.get("subject") else {})})
    if doc.get("market_context"):
        return None, "This Set has market context items, which the editor cannot show yet."
    for m in doc.get("standalone") or []:
        ref = m["ref"]
        if ref.get("params") or not fields.described(f"{ref['id']}@{ref['version']}") or m["role"] not in ("condition", "context"):
            return None, f"{m['key']} cannot be shown in the editor yet."
        model["standalone"].append({"key": m["key"], "id": ref["id"], "version": ref["version"],
                                    "timeframe": ref["timeframe"], "role": m["role"],
                                    **({"subject": m["subject"]} if m.get("subject") else {})})
    rule = (doc.get("decision") or {}).get("rule")
    if rule:
        items = rule["all"] if "all" in rule else [rule]
        for item in items:
            if "any" in item:
                inner = [_line(p) for p in item["any"]]
                if None in inner:
                    return None, "The decision is more complex than the editor can show yet."
                model["lines"].append({"any": inner})
            else:
                line = _line(item)
                if line is None:
                    return None, "The decision is more complex than the editor can show yet."
                model["lines"].append(line)
    return model, None
