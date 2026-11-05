"""Set decisions (docs/design/lattice_prism.md §4.2, extension E2).

An optional three-valued rule on a Set that answers "does this asset match?": Yes (true), No (false) or Unknown.
It never scores, enters, exits, sizes or manages risk.

Predicates:
    {"group": g, "outcome": {"eq": id} | {"in": [ids]}}        the Group's published outcome (E1)
    {"group": g, "score": {"gte" | "lte" | "between": ...}}    the Group score, stored -1..+1
    {"group": g, "condition": c, "state": {"eq" | "in": ...}}  a named condition: met / not_met, active / clear
    {"group": g, "status": {"eq" | "in": ...}}                 ok / vetoed / veto_unknown / insufficient
    {"member": m, ...}                                          a standalone condition item, as in Groups
combined with "all", "any" and "not". Counting operators are not available in decisions yet.

Unknown can never become a decision: no predicate tests for "unknown"; an unknown outcome, state or score makes the
predicate unknown, and `not` keeps it unknown. A qualified outcome (Group status veto_unknown) is evaluated for its raw
outcome and for `vetoed`: the same result for both gives that result, otherwise unknown.
"""

from __future__ import annotations

import math

from . import rules
from .outcomes import RESERVED, outcome_ids
from .transforms import UNKNOWN

VERSION = 1
GROUP_TARGETS = ("outcome", "score", "condition", "status")
STATES = {"confirmation": ("met", "not_met"), "veto": ("active", "clear")}
STATUSES = ("ok", "vetoed", "veto_unknown", "insufficient")
FAILED = ("invalid", "unsupported")
MAX_DEPTH, MAX_PREDICATES = 6, 50
ANSWER = {True: "yes", False: "no"}


def _word(value) -> str:
    return "true" if value is True else "false" if value is False else "unknown"


def _choice(spec: dict, x) -> bool:
    return x == spec["eq"] if "eq" in spec else x in spec["in"]


def _choice_text(spec: dict) -> str:
    return f"is {spec['eq']}" if "eq" in spec else "is one of " + ", ".join(map(str, spec["in"]))


def _num_text(spec: dict) -> str:
    parts = []
    if "gte" in spec:
        parts.append(f"≥ {spec['gte']}")
    if "lte" in spec:
        parts.append(f"≤ {spec['lte']}")
    if "between" in spec:
        parts.append(f"between {spec['between'][0]} and {spec['between'][1]}")
    if "eq" in spec:
        parts.append(f"= {spec['eq']}")
    if "in" in spec:
        parts.append("one of " + ", ".join(map(str, spec["in"])))
    if "exists" in spec:
        parts.append("exists" if spec["exists"] else "is absent")
    return " and ".join(parts)


def _reading(x):
    if isinstance(x, float):
        return round(x, 6) if math.isfinite(x) else None
    if isinstance(x, (int, str, bool)) or x is None:
        return x
    return "(structured value)"


def _group_line(pred: dict, groups: dict) -> tuple[object, str, object]:
    key = pred["group"]
    result = groups.get(key) or {}
    failed = result.get("status") in FAILED or not result
    if "outcome" in pred:
        spec = pred["outcome"]
        text = f"{key} outcome {_choice_text(spec)}"
        out = result.get("outcome")
        if failed or not out:
            return UNKNOWN, text, None
        reading = out["id"] + (" (qualified: a veto is unknown)" if out["qualified"] else "")
        if out["id"] == "unknown":
            return UNKNOWN, text, reading
        value = _choice(spec, out["id"])
        if out["qualified"] and _choice(spec, "vetoed") != value:
            value = UNKNOWN
        return value, text, reading
    if "score" in pred:
        text = f"{key} score {_num_text(pred['score'])}"
        score = (result.get("score") or {}).get("value")
        if failed or score is None:
            return UNKNOWN, text, None
        return rules._compare(pred["score"], score), text, round(score, 6)
    if "condition" in pred:
        text = f"{key} condition {pred['condition']} {_choice_text(pred['state'])}"
        found = next((c for c in result.get("conditions") or [] if c["key"] == pred["condition"]), None)
        if failed or found is None or found["state"] == "unknown":
            return UNKNOWN, text, None if found is None else found["state"]
        return _choice(pred["state"], found["state"]), text, found["state"]
    text = f"{key} status {_choice_text(pred['status'])}"
    status = result.get("status")
    return _choice(pred["status"], status), text, status


def _node(rule: dict, groups: dict, members: rules.Context, path: str) -> dict:
    for combo in ("all", "any", "not"):
        if combo in rule:
            subs = [rule["not"]] if combo == "not" else rule[combo]
            kids = [_node(s, groups, members, f"{path}.not" if combo == "not" else f"{path}.{combo}[{i}]")
                    for i, s in enumerate(subs)]
            values = [k["value"] for k in kids]
            if combo == "not":
                value = UNKNOWN if values[0] is UNKNOWN else (not values[0])
            elif combo == "all":
                value = False if False in values else UNKNOWN if UNKNOWN in values else True
            else:
                value = True if True in values else UNKNOWN if UNKNOWN in values else False
            return {"kind": combo, "value": value, "children": kids}
    if "group" in rule:
        value, text, reading = _group_line(rule, groups)
    else:
        value = rules.evaluate(rule, members)[0]
        m = members.members[rule["member"]]
        found, x = (False, None) if not m["available"] else rules.resolve(m["value"], rule.get("field"))
        reading = _reading(x) if found else None
        field = f".{rule['field']}" if rule.get("field") else ""
        text = f"{rule['member']}{field} " + ("has a matching event" if "events" in rule else _num_text(rule))
    return {"kind": "line", "value": value, "line": {"path": path, "text": text, "reading": reading, "value": _word(value)}}


def _decisive(node: dict) -> list[dict]:
    if node["kind"] == "line":
        return [node["line"]]
    kids, value = node["children"], node["value"]
    if node["kind"] == "not":
        return _decisive(kids[0])
    if node["kind"] == "all":
        pick = [k for k in kids if k["value"] is False] if value is False else \
            [k for k in kids if k["value"] is UNKNOWN] if value is UNKNOWN else kids
    else:
        pick = [k for k in kids if k["value"] is True] if value is True else \
            [k for k in kids if k["value"] is UNKNOWN] if value is UNKNOWN else kids
    return [line for k in pick for line in _decisive(k)]


def _lines(node: dict) -> list[dict]:
    if node["kind"] == "line":
        return [node["line"]]
    return [line for k in node["children"] for line in _lines(k)]


def evaluate(spec: dict, groups: dict, members: rules.Context) -> dict:
    """`groups`: Group key -> evaluate_group result. `members`: rules.Context over the Set's standalone items."""
    tree = _node(spec["rule"], groups, members, "decision.rule")
    value = tree["value"]
    return {"answer": ANSWER.get(value, "unknown"), "decisive": _decisive(tree), "lines": _lines(tree),
            "version": spec.get("version")}


# ----------------------------------------------------------------------------- validation

def check(spec, snapshots: dict, members: dict, roots_of_member) -> tuple[list[str], list[tuple[str, dict]]]:
    """(errors, [(path, member predicate)] for the field checks). `snapshots`: Group key -> embedded Group document;
    `members`: standalone key -> item."""
    if not isinstance(spec, dict):
        return ["decision must be an object"], []
    errors: list[str] = []
    if spec.get("version") != VERSION:
        errors.append(f"decision.version must be {VERSION}")
    if set(spec) - {"version", "rule"}:
        errors.append(f"decision: unknown keys {sorted(set(spec) - {'version', 'rule'})}")
    member_preds: list[tuple[str, dict]] = []
    count = [0]

    def choice_errors(where, value, allowed, what):
        if not isinstance(value, dict) or len(value) != 1 or not set(value) <= {"eq", "in"}:
            errors.append(f"{where}: {what} needs exactly one of eq or in")
            return
        wanted = [value["eq"]] if "eq" in value else value["in"]
        if not isinstance(wanted, list) or not wanted:
            errors.append(f"{where}: in needs a non-empty list")
            return
        if "unknown" in wanted:
            errors.append(f"{where}: Unknown cannot be tested; a missing reading can never become a decision")
            wanted = [w for w in wanted if w != "unknown"]
        bad = [w for w in wanted if w not in allowed]
        if bad:
            errors.append(f"{where}: {what} {bad} not among {list(allowed)}")

    def walk(rule, where, depth):
        if depth > MAX_DEPTH:
            errors.append(f"{where}: nested deeper than {MAX_DEPTH}")
            return
        if not isinstance(rule, dict):
            errors.append(f"{where}: must be an object")
            return
        if any(c in rule for c in ("count_at_least", "count_distinct_sources_at_least")):
            errors.append(f"{where}: counting operators are not available in Set decisions yet")
            return
        combos = [c for c in ("all", "any", "not") if c in rule]
        if combos:
            if len(combos) > 1 or len(rule) != 1:
                errors.append(f"{where}: one combinator per object")
                return
            c = combos[0]
            subs = [rule["not"]] if c == "not" else rule[c]
            if c != "not" and (not isinstance(subs, list) or not subs):
                errors.append(f"{where}.{c}: needs a non-empty list")
                return
            for i, s in enumerate(subs):
                walk(s, f"{where}.not" if c == "not" else f"{where}.{c}[{i}]", depth + 1)
            return
        count[0] += 1
        if ("group" in rule) == ("member" in rule):
            errors.append(f"{where}: a predicate names exactly one group or one member")
            return
        if "member" in rule:
            item = members.get(rule["member"])
            if item is None:
                errors.append(f"{where}: unknown standalone item {rule['member']!r}")
                return
            if item.get("role") not in ("condition", "levels"):
                errors.append(f"{where}: {rule['member']!r} has role {item.get('role')} and cannot be used in the "
                              "decision (give it role condition)")
                return
            if isinstance(rule.get("events"), dict) and "within_candles" in rule["events"]:
                errors.append(f"{where}: within_candles is not available in Set decisions yet")
                return
            e, _ = rules.check(rule, members, False, roots_of_member, path=where)
            errors.extend(e)
            member_preds.append((where, rule))
            return
        key = rule["group"]
        snap = snapshots.get(key)
        if snap is None:
            errors.append(f"{where}: unknown group {key!r}")
            return
        targets = [t for t in GROUP_TARGETS if t in rule]
        allowed_keys = {"group", *targets} | ({"state"} if targets == ["condition"] else set())
        if len(targets) != 1 or set(rule) - allowed_keys:
            errors.append(f"{where}: a Group predicate uses exactly one of {GROUP_TARGETS}")
            return
        target = targets[0]
        if target == "outcome":
            spec_o = snap.get("outcomes")
            if not isinstance(spec_o, dict):
                errors.append(f"{where}: this Group version has no outcomes; embed a newer version")
                return
            try:
                allowed = outcome_ids(spec_o) + ["vetoed"]
            except (KeyError, TypeError):
                return  # the Group's own validation reports its outcome errors
            choice_errors(where, rule["outcome"], allowed, "outcome")
        elif target == "score":
            if snap.get("score") is None:
                errors.append(f"{where}: this Group has no score")
                return
            ops = rule["score"] if isinstance(rule["score"], dict) else {}
            if not ops or not set(ops) <= {"gte", "lte", "between"}:
                errors.append(f"{where}: score predicates use gte, lte or between")
                return
            low, high = (snap["score"].get("range") or [-1, 1])
            values = [ops[k] for k in ("gte", "lte") if k in ops] + list(ops.get("between") or [])
            if any(rules._num(v) is None for v in values):
                errors.append(f"{where}: score thresholds must be finite numbers")
            elif any(not low <= v <= high for v in values):
                errors.append(f"{where}: a score threshold is outside the Group score range {low} to {high} "
                              "(stored scale; +30 on screen is 0.30)")
        elif target == "condition":
            found = next((c for c in snap.get("conditions") or [] if c.get("key") == rule["condition"]), None)
            if found is None:
                errors.append(f"{where}: the Group has no condition {rule['condition']!r}")
                return
            if "state" not in rule:
                errors.append(f"{where}: a condition predicate needs state")
                return
            choice_errors(where, rule["state"], STATES.get(found.get("kind"), ()), "state")
        else:
            choice_errors(where, rule["status"], STATUSES, "status")

    walk(spec.get("rule"), "decision.rule", 0)
    if count[0] > MAX_PREDICATES:
        errors.append(f"at most {MAX_PREDICATES} predicates in a decision")
    return errors, member_preds


__all__ = ["evaluate", "check", "RESERVED", "STATUSES", "STATES", "VERSION"]
