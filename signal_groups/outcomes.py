"""Group outcomes (docs/design/lattice_prism.md §4.1, extension E1).

An optional, ordered list of labelled rules evaluated after the Group's conditions:

1. Ordered rules give the raw outcome. The first rule that is true wins. If the first rule that is not false is
   unknown, the raw outcome is `unknown` and later rules are not evaluated (the unknown rule might have matched).
   When every rule is false, the `otherwise` outcome applies.
2. The Group status gates it, so a label never hides a veto or a withheld score:
   ok -> raw; vetoed -> `vetoed`; veto_unknown -> raw, qualified (it may be `vetoed`); insufficient -> `unknown`.

Outcome ids are stable (Sets refer to ids); labels are display text and can be renamed in a new version.
"""

from __future__ import annotations

import re

from . import rules
from .transforms import UNKNOWN

RESERVED = {"unknown": "Unknown", "vetoed": "Vetoed"}
ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
MAX_RULES = 10
MAX_LABEL = 24
VERSION = 1


def outcome_ids(spec: dict) -> list[str]:
    """User-defined ids, in order, then the otherwise id."""
    return [r["id"] for r in spec.get("rules") or []] + [spec["otherwise"]["id"]]


def raw_outcome(spec: dict, rctx: rules.Context) -> tuple[str, str, int | None]:
    """(id, label, index of the deciding rule or None)."""
    for i, r in enumerate(spec["rules"]):
        value, _, _ = rules.evaluate(r["when"], rctx)
        if value is True:
            return r["id"], r["label"], i
        if value is UNKNOWN:
            return "unknown", RESERVED["unknown"], i
    other = spec["otherwise"]
    return other["id"], other["label"], None


def publish(spec: dict, rctx: rules.Context, status: str) -> dict:
    rid, rlabel, rule_index = raw_outcome(spec, rctx)
    qualified = False
    if status == "vetoed":
        pid, plabel = "vetoed", RESERVED["vetoed"]
    elif status == "insufficient":
        pid, plabel = "unknown", RESERVED["unknown"]
    else:
        pid, plabel = rid, rlabel
        qualified = status == "veto_unknown" and rid != "unknown"
    return {"id": pid, "label": plabel, "qualified": qualified, "status": status,
            "raw": {"id": rid, "label": rlabel, "rule": rule_index}}


def check(spec, members: dict, has_score: bool, roots_of_member) -> tuple[list[str], int, list[tuple[str, dict]]]:
    """(errors, predicate count, [(path, rule)] for the field checks)."""
    if not isinstance(spec, dict):
        return ["outcomes must be an object"], 0, []
    errors: list[str] = []
    if spec.get("version") != VERSION:
        errors.append(f"outcomes.version must be {VERSION}")
    extra = set(spec) - {"version", "rules", "otherwise"}
    if extra:
        errors.append(f"outcomes: unknown keys {sorted(extra)}")
    items = spec.get("rules")
    if not isinstance(items, list) or not items:
        return errors + ["outcomes.rules must be a non-empty list"], 0, []
    if len(items) > MAX_RULES:
        errors.append(f"at most {MAX_RULES} outcome rules")
    seen: set = set()
    total, walk = 0, []

    def check_label(entry, where):
        oid, label = entry.get("id"), entry.get("label")
        if not isinstance(oid, str) or not ID.match(oid):
            errors.append(f"{where}: id must start with a letter and use lowercase letters, digits or _ (max 24)")
        elif oid in RESERVED:
            errors.append(f"{where}: {oid!r} is reserved for the system")
        elif oid in seen:
            errors.append(f"{where}: duplicate outcome id {oid!r}")
        else:
            seen.add(oid)
        if not isinstance(label, str) or not label.strip() or len(label) > MAX_LABEL:
            errors.append(f"{where}: label must be 1 to {MAX_LABEL} characters")
        elif label.strip().lower() in RESERVED:
            errors.append(f"{where}: the label {label!r} is reserved for the system")

    for i, r in enumerate(items):
        where = f"outcomes.rules[{i}]"
        if not isinstance(r, dict):
            errors.append(f"{where}: must be an object")
            continue
        check_label(r, where)
        if set(r) - {"id", "label", "when"}:
            errors.append(f"{where}: unknown keys {sorted(set(r) - {'id', 'label', 'when'})}")
        e, n = rules.check(r.get("when"), members, has_score, roots_of_member, path=f"{where}.when")
        errors += e
        total += n
        walk.append((f"{where}.when", r.get("when")))
    other = spec.get("otherwise")
    if not isinstance(other, dict) or set(other) - {"id", "label"}:
        errors.append("outcomes.otherwise must be {id, label}")
    else:
        check_label(other, "outcomes.otherwise")
    return errors, total, walk
