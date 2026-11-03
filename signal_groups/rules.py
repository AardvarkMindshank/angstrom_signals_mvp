"""
Rules (design sections 3.4 and 3.4.1): bounded JSON expressions evaluated to True, False or UNKNOWN.

Every expression also returns its support set (signal instances referenced anywhere inside it) and its lineage
roots (union over those instances), which the counting operators use to merge items before counting.
"""

from __future__ import annotations

import math

from .transforms import UNKNOWN, resolve

COMBINATORS = ("all", "any", "not", "count_at_least", "count_distinct_sources_at_least")
COMPARATORS = ("eq", "in", "gte", "lte", "between", "exists")
EVENT_FILTERS = ("type_in", "kind_in", "direction", "within_candles", "include_developing")
MAX_DEPTH = 6


class Context:
    """What rules can see: member values and availability, the score, and lineage."""

    def __init__(self, members: dict, score, score_support: set, roots_of: dict, candles_since):
        self.members = members              # key -> {"available": bool, "value": ..., "instance": str, "roots": set}
        self.score = score                  # float or None (withheld)
        self.score_support = score_support  # instance keys of enabled score members
        self.roots_of = roots_of            # instance key -> set of roots
        self.candles_since = candles_since  # (member key, event) -> int | None


def _num(x):
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _compare(rule: dict, x):
    if "exists" in rule:
        return (x is not None) == bool(rule["exists"])
    if x is None:
        return UNKNOWN
    if "eq" in rule:
        return x == rule["eq"]
    if "in" in rule:
        return x in rule["in"]
    n = _num(x)
    if n is None:
        return UNKNOWN
    if "gte" in rule and not n >= rule["gte"]:
        return False
    if "lte" in rule and not n <= rule["lte"]:
        return False
    if "between" in rule:
        lo, hi = rule["between"]
        if not lo <= n <= hi:
            return False
    return True


def _events_match(rule: dict, key: str, value, ctx: Context):
    if not isinstance(value, dict) or not isinstance(value.get("events"), list):
        return UNKNOWN
    f = rule["events"]
    pool = [e for e in value["events"] if e.get("status", "confirmed") == "confirmed"]
    if f.get("include_developing"):
        pool += list(value.get("developing") or [])
    for e in pool:
        if "type_in" in f and e.get("type") not in f["type_in"]:
            continue
        if "kind_in" in f and e.get("kind") not in f["kind_in"]:
            continue
        if "direction" in f and e.get("direction") != f["direction"]:
            continue
        if "within_candles" in f:
            since = ctx.candles_since(key, e)
            if since is None:
                return UNKNOWN  # cannot place the event in time: do not guess
            if since > f["within_candles"]:
                continue
        return True
    return False


def evaluate(rule: dict, ctx: Context):
    """(value, support set, lineage roots)."""
    for combo in COMBINATORS:
        if combo in rule:
            break
    else:
        combo = None
    if combo in ("all", "any", "not"):
        subs = [rule["not"]] if combo == "not" else rule[combo]
        parts = [evaluate(s, ctx) for s in subs]
        support = set().union(*(p[1] for p in parts))
        roots = set().union(*(p[2] for p in parts))
        values = [p[0] for p in parts]
        if combo == "not":
            v = values[0]
            return (UNKNOWN if v is UNKNOWN else (not v)), support, roots
        if combo == "all":
            v = False if False in values else UNKNOWN if UNKNOWN in values else True
        else:
            v = True if True in values else UNKNOWN if UNKNOWN in values else False
        return v, support, roots
    if combo in ("count_at_least", "count_distinct_sources_at_least"):
        items = [evaluate(s, ctx) for s in rule["of"]]
        v = count(combo, rule[combo], items)
        return v, set().union(*(i[1] for i in items)), set().union(*(i[2] for i in items))
    if "score" in rule:
        support = set(ctx.score_support)
        roots = set().union(*(ctx.roots_of.get(i, set()) for i in support)) if support else set()
        if ctx.score is None:
            return UNKNOWN, support, roots
        return _compare(rule["score"], ctx.score), support, roots
    key = rule["member"]
    m = ctx.members[key]
    support, roots = {m["instance"]}, set(m["roots"])
    if not m["available"]:
        return UNKNOWN, support, roots
    if "events" in rule:
        return _events_match(rule, key, m["value"], ctx), support, roots
    found, x = resolve(m["value"], rule.get("field"))
    if not found:
        if "exists" in rule:
            return (not bool(rule["exists"])), support, roots
        return UNKNOWN, support, roots
    return _compare(rule, x), support, roots


def count(op: str, k: int, items: list) -> object:
    """Section 3.4.1: merge items sharing an instance (or a source), then count clusters three-valuedly."""
    idx = 1 if op == "count_at_least" else 2
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i][idx] & items[j][idx]:
                parent[find(i)] = find(j)
    clusters: dict = {}
    for i, item in enumerate(items):
        clusters.setdefault(find(i), []).append(item[0])
    values = [True if True in v else UNKNOWN if UNKNOWN in v else False for v in clusters.values()]
    trues, unknowns = values.count(True), values.count(UNKNOWN)
    if trues >= k:
        return True
    if trues + unknowns < k:
        return False
    return UNKNOWN


# ----------------------------------------------------------------------------- static checks for the validator

def check(rule, members: dict, has_score: bool, roots_of_member, path="rule", depth=0) -> tuple[list[str], int]:
    """(errors, predicate count). Structural only; field paths are checked at evaluation (unknown when missing)."""
    errors: list[str] = []
    if depth > MAX_DEPTH:
        return [f"{path}: nested deeper than {MAX_DEPTH}"], 0
    if not isinstance(rule, dict):
        return [f"{path}: must be an object"], 0
    combos = [c for c in COMBINATORS if c in rule]
    if len(combos) > 1:
        return [f"{path}: more than one combinator {combos}"], 0
    if combos:
        c = combos[0]
        if c in ("all", "any"):
            if not isinstance(rule[c], list) or not rule[c]:
                return [f"{path}.{c}: needs a non-empty list"], 0
            subs = rule[c]
        elif c == "not":
            subs = [rule["not"]]
        else:
            k, subs = rule[c], rule.get("of")
            if not isinstance(subs, list) or not subs:
                return [f"{path}.of: needs a non-empty list"], 0
            if not isinstance(k, int) or isinstance(k, bool) or not 1 <= k <= len(subs):
                errors.append(f"{path}.{c}: k must be an integer from 1 to {len(subs)}")
            if c == "count_distinct_sources_at_least" and isinstance(k, int):
                roots = [_roots(s, members, roots_of_member) for s in subs]
                if _max_clusters(roots) < k:
                    errors.append(f"{path}: unsatisfiable: the items share sources and can never reach {k} distinct sources")
        total = 0
        for i, s in enumerate(subs):
            e, n = check(s, members, has_score, roots_of_member, f"{path}.{c}[{i}]", depth + 1)
            errors += e
            total += n
        return errors, total
    if "score" in rule:
        if not has_score:
            errors.append(f"{path}: score predicate in a Group without a score")
        ops = set(rule["score"]) if isinstance(rule["score"], dict) else set()
        if not ops or not ops <= {"gte", "lte", "between"}:
            errors.append(f"{path}: score predicates use gte, lte or between")
        return errors, 1
    key = rule.get("member")
    if key not in members:
        return [f"{path}: unknown member {key!r}"], 1
    m = members[key]
    if m.get("role") == "context":
        errors.append(f"{path}: member {key!r} has role context and cannot be used in rules")
    if "events" in rule:
        f = rule["events"]
        if not isinstance(f, dict) or not set(f) <= set(EVENT_FILTERS):
            errors.append(f"{path}: events filters are {EVENT_FILTERS}")
        elif "within_candles" in f and (not isinstance(f["within_candles"], int) or f["within_candles"] < 0):
            errors.append(f"{path}: within_candles must be a whole number ≥ 0")
        return errors, 1
    ops = [o for o in COMPARATORS if o in rule]
    extra = set(rule) - {"member", "field"} - set(COMPARATORS)
    if len(ops) != 1 or extra:
        errors.append(f"{path}: a predicate needs exactly one of {COMPARATORS}")
    elif ops[0] in ("gte", "lte") and _num(rule[ops[0]]) is None:
        errors.append(f"{path}: {ops[0]} needs a finite number")
    elif ops[0] == "between" and (not isinstance(rule["between"], list) or len(rule["between"]) != 2
                                  or any(_num(v) is None for v in rule["between"]) or rule["between"][0] > rule["between"][1]):
        errors.append(f"{path}: between needs [low, high]")
    elif ops[0] == "in" and not isinstance(rule["in"], list):
        errors.append(f"{path}: in needs a list")
    if "field" in rule and (not isinstance(rule["field"], str) or not rule["field"]):
        errors.append(f"{path}: field must be a dotted path")
    return errors, 1


def _roots(rule, members, roots_of_member) -> set:
    if "member" in rule:
        return set(roots_of_member(rule["member"]))
    if "score" in rule:
        return set().union(*(roots_of_member(k) for k, m in members.items() if m.get("role") == "score")) if members else set()
    out = set()
    for key in ("all", "any", "of"):
        for sub in rule.get(key, []) or []:
            out |= _roots(sub, members, roots_of_member)
    if "not" in rule:
        out |= _roots(rule["not"], members, roots_of_member)
    return out


def _max_clusters(root_sets: list) -> int:
    parent = list(range(len(root_sets)))

    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i

    for i in range(len(root_sets)):
        for j in range(i + 1, len(root_sets)):
            if root_sets[i] & root_sets[j]:
                parent[find(i)] = find(j)
    return len({find(i) for i in range(len(root_sets))})
