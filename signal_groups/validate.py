"""
Validator for Group and Set documents (design sections 3, 5). Returns a list of plain-language errors; empty = valid.
Runs before anything is saved and before anything is evaluated.
"""

from __future__ import annotations

import json
import math
import re

import signal_library as sl
from signal_library.core import EVENTS, NUMERIC

from . import lineage, rules, transforms

GROUP_SCHEMA = "angstrom.group/1"
SET_SCHEMA = "angstrom.set/1"
ROLES = ("score", "condition", "levels", "context")
SCORE_POLICIES = ("exclude", "neutral")
MAX_MEMBERS, MAX_CONDITIONS, MAX_PREDICATES, MAX_BYTES = 30, 20, 50, 64 * 1024
MAX_SET_GROUPS, MAX_SET_ITEMS = 10, 20
KEY = re.compile(r"^[a-z0-9_]{1,40}$")


def _ref_errors(ref, where: str, allow_market: bool = False) -> tuple[list[str], object]:
    if not isinstance(ref, dict):
        return [f"{where}: ref must be an object"], None
    try:
        definition = sl.REGISTRY.get(ref["id"], ref["version"])
    except (KeyError, TypeError):
        return [f"{where}: unknown signal {ref.get('id')}@{ref.get('version')}"], None
    if definition.scope.startswith("market:") and not allow_market:
        return [f"{where}: {definition.key} is market context; put it in a Set's market_context"], None
    try:
        sl.SignalRef.make(definition, ref.get("timeframe"), **dict(ref.get("params") or {}))
    except (ValueError, TypeError) as exc:
        return [f"{where}: {exc}"], None
    return [], definition


def validate_group(doc) -> list[str]:
    if not isinstance(doc, dict):
        return ["a Group must be a JSON object"]
    errors = []
    if doc.get("schema") != GROUP_SCHEMA:
        errors.append(f"schema must be {GROUP_SCHEMA}")
    if not str(doc.get("name") or "").strip():
        errors.append("name is required")
    if len(json.dumps(doc).encode()) > MAX_BYTES:
        errors.append("document larger than 64 KB")
    lv = doc.get("lineage_version")
    try:
        roots_table = lineage.table(lv)
    except (KeyError, TypeError, ValueError):
        return errors + [f"lineage_version {lv!r} does not exist"]
    members = doc.get("members")
    if not isinstance(members, list) or not members:
        return errors + ["members must be a non-empty list"]
    if len(members) > MAX_MEMBERS:
        errors.append(f"at most {MAX_MEMBERS} members")
    by_key = {}
    for i, m in enumerate(members):
        where = f"members[{i}]"
        if not isinstance(m, dict):
            errors.append(f"{where}: must be an object")
            continue
        key = m.get("key")
        if not isinstance(key, str) or not KEY.match(key):
            errors.append(f"{where}: key must be lowercase letters, digits or _ (max 40)")
            continue
        if key in by_key:
            errors.append(f"{where}: duplicate key {key!r}")
            continue
        by_key[key] = m
        e, definition = _ref_errors(m.get("ref"), f"{key}")
        errors += e
        if definition and definition.id not in roots_table:
            errors.append(f"{key}: {definition.id} has no lineage in version {lv}")
        role = m.get("role")
        if role not in ROLES:
            errors.append(f"{key}: role must be one of {ROLES}")
            continue
        if role == "score":
            if m.get("when_unavailable") not in SCORE_POLICIES:
                errors.append(f"{key}: a score member needs when_unavailable 'exclude' or 'neutral'")
            w = m.get("weight")
            if isinstance(w, bool) or not isinstance(w, (int, float)) or not math.isfinite(w) or not 0 <= w <= 1000:
                errors.append(f"{key}: weight must be a number from 0 to 1000")
            t = m.get("transform")
            if not isinstance(t, dict):
                errors.append(f"{key}: a score member needs a transform")
            else:
                errors += [f"{key}: {e}" for e in transforms.config_errors(t)]
                if definition:
                    if t.get("kind") == "events" and definition.output != EVENTS:
                        errors.append(f"{key}: events transform needs an events signal")
                    if t.get("kind") in ("bands", "clip") and definition.output != NUMERIC and not t.get("field"):
                        errors.append(f"{key}: {t['kind']} needs a numeric signal or a field path")
        else:
            for field in ("weight", "transform", "when_unavailable"):
                if field in m:
                    errors.append(f"{key}: role {role} has no {field} (its missing-data rule is fixed)")
    score = doc.get("score")
    has_score = score is not None
    if has_score:
        if not isinstance(score, dict) or score.get("method") != "weighted_mean":
            errors.append("score.method must be weighted_mean")
        elif not str(score.get("meaning") or "").strip():
            errors.append("score.meaning is required")
        mc = (score or {}).get("min_coverage") if isinstance(score, dict) else None
        if not isinstance(mc, dict) or not all(isinstance(mc.get(k), int) and not isinstance(mc.get(k), bool) for k in ("num", "den")) \
                or not 0 <= mc["num"] <= mc["den"] or mc["den"] == 0:
            errors.append("score.min_coverage must be {num, den} whole numbers with 0 ≤ num ≤ den, den > 0")
        if not any(m.get("role") == "score" and isinstance(m.get("weight"), (int, float)) and m["weight"] > 0
                   for m in by_key.values()):
            errors.append("a score needs at least one score member with weight above 0")
    conditions = doc.get("conditions") or []
    if not isinstance(conditions, list):
        return errors + ["conditions must be a list"]
    if len(conditions) > MAX_CONDITIONS:
        errors.append(f"at most {MAX_CONDITIONS} conditions")

    def roots_of_member(key):
        m = by_key.get(key) or {}
        rid = (m.get("ref") or {}).get("id")
        return roots_table.get(rid, frozenset())

    total, seen = 0, set()
    for i, c in enumerate(conditions):
        where = f"conditions[{i}]"
        if not isinstance(c, dict) or not isinstance(c.get("key"), str) or not KEY.match(c["key"]):
            errors.append(f"{where}: needs a key")
            continue
        if c["key"] in seen:
            errors.append(f"{where}: duplicate key {c['key']!r}")
        seen.add(c["key"])
        if c.get("kind") not in ("confirmation", "veto"):
            errors.append(f"{c['key']}: kind must be confirmation or veto")
        e, n = rules.check(c.get("rule"), by_key, has_score, roots_of_member, path=c["key"])
        errors += e
        total += n
    if total > MAX_PREDICATES:
        errors.append(f"at most {MAX_PREDICATES} predicates in all")
    return errors


def validate_set(doc) -> list[str]:
    if not isinstance(doc, dict):
        return ["a Set must be a JSON object"]
    errors = []
    if doc.get("schema") != SET_SCHEMA:
        errors.append(f"schema must be {SET_SCHEMA}")
    if not str(doc.get("name") or "").strip():
        errors.append("name is required")
    if doc.get("score") is not None:
        errors.append("Set scores are not available yet (score must be null)")
    try:
        lineage.table(doc.get("lineage_version"))
    except (KeyError, TypeError, ValueError):
        errors.append(f"lineage_version {doc.get('lineage_version')!r} does not exist")
    if len(json.dumps(doc).encode()) > 4 * MAX_BYTES:
        errors.append("document larger than 256 KB")
    groups = doc.get("groups") or []
    if not isinstance(groups, list) or len(groups) > MAX_SET_GROUPS:
        errors.append(f"groups must be a list of at most {MAX_SET_GROUPS}")
        groups = []
    keys = set()
    for i, g in enumerate(groups):
        key = (g or {}).get("key")
        if not isinstance(key, str) or not KEY.match(key) or key in keys:
            errors.append(f"groups[{i}]: needs a unique key")
            continue
        keys.add(key)
        if "snapshot" not in g:
            errors.append(f"{key}: a Set embeds the Group snapshot itself")
            continue
        errors += [f"{key}: {e}" for e in validate_group(g["snapshot"])]
    items = list(doc.get("standalone") or []) + list(doc.get("market_context") or [])
    if len(items) > MAX_SET_ITEMS:
        errors.append(f"at most {MAX_SET_ITEMS} standalone and market items")
    for section in ("standalone", "market_context"):
        for i, item in enumerate(doc.get(section) or []):
            key = (item or {}).get("key")
            if not isinstance(key, str) or not KEY.match(key) or key in keys:
                errors.append(f"{section}[{i}]: needs a unique key")
                continue
            keys.add(key)
            e, definition = _ref_errors(item.get("ref"), key, allow_market=(section == "market_context"))
            errors += e
            if item.get("role") not in ("context", "levels"):
                errors.append(f"{key}: role must be context or levels")
            if section == "market_context" and definition is not None:
                if not definition.scope.startswith("market:"):
                    errors.append(f"{key}: market_context takes market signals only")
                elif item.get("subject") != definition.scope:
                    errors.append(f"{key}: subject must be {definition.scope}")
                if (item.get("ref") or {}).get("params", {}).get("point_in_time") is False and item.get("data_modes") != ["live"]:
                    errors.append(f"{key}: non-point-in-time flows are current context only (data_modes ['live'])")
    return errors
