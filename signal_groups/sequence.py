"""Sequences in Set decisions (docs/design/sequences.md): "A, then B within N closed daily candles".

    {"sequence": {"first": rule, "then": rule, "within": N, "cancel": rule?}}

The answer at a close is worked out afresh from the closes before it, each read as it was known at its own close
(`earlier`, given by the caller). No state is stored, so a restart or a late check gives the same answer.

At close c0 with earlier closes c1 … cN: B must hold at c0, and A at some ck (1 ≤ k ≤ N) with no cancel true at any
close after ck up to c0. Unknown is never met: an A, a cancel or a close that could not be read makes the answer
Unknown when it could have changed it.
"""

from __future__ import annotations

import pandas as pd

from .transforms import UNKNOWN

MAX_WITHIN = 20
MAX_SEQUENCES = 2
PARTS = ("first", "then", "cancel")
STATES = ("met", "armed", "expired", "cancelled", "waiting", "unknown")


def _and(a, b):
    return False if False in (a, b) else UNKNOWN if UNKNOWN in (a, b) else True


def find(rule, path: str = "decision.rule") -> list[tuple[str, dict]]:
    """[(path, sequence spec)] in rule order."""
    if not isinstance(rule, dict):
        return []
    if "sequence" in rule:
        return [(path, rule["sequence"])]
    out = []
    for combo in ("all", "any"):
        for i, sub in enumerate(rule.get(combo) or []):
            out += find(sub, f"{path}.{combo}[{i}]")
    if "not" in rule:
        out += find(rule["not"], f"{path}.not")
    return out


def longest(spec: dict | None) -> int:
    """The largest `within` in a decision (0 when it has no sequence)."""
    if not isinstance(spec, dict):
        return 0
    return max((s.get("within") or 0 for _, s in find(spec.get("rule"))), default=0)


def needs(rule) -> tuple[set, set]:
    """(Group keys, standalone keys) a rule reads."""
    groups, members = set(), set()

    def walk(r):
        if not isinstance(r, dict):
            return
        if "sequence" in r:
            for part in PARTS:
                walk(r["sequence"].get(part))
            return
        for combo in ("all", "any"):
            for sub in r.get(combo) or []:
                walk(sub)
        if "not" in r:
            walk(r["not"])
        if "group" in r:
            groups.add(r["group"])
        if "member" in r:
            members.add(r["member"])

    walk(rule)
    return groups, members


def closes(ctx, n: int) -> list[pd.Timestamp]:
    """The starts of the last n+1 closed daily candles of the scanned asset, newest first ([c0, c1, … cn]);
    fewer when the asset has less history. [] when its daily candles cannot be read."""
    try:
        got = ctx.candles("1D")
    except Exception:
        return []
    frame = (got or {}).get("frame")
    if frame is None or not len(frame):
        return []
    if "forming" in frame.columns:
        frame = frame[~frame["forming"].astype(bool)]
    return list(reversed(list(frame.index[-(n + 1):])))


def judge(spec: dict, a: list, b, c: list | None) -> dict:
    """a[k], c[k]: the value of first / cancel at ck (k = 0 now), True / False / UNKNOWN; b: then at c0.
    Returns {"value", "state", "since", "left"}."""
    n = spec["within"]
    c = c if c is not None else [False] * len(a)

    def cancelled(k):                     # a cancel at a close after ck, up to c0
        later = c[:k]
        return True if True in later else UNKNOWN if UNKNOWN in later else False

    counts, maybe = [], False
    for k in range(1, min(n, len(a) - 1) + 1):
        gone = cancelled(k)
        if a[k] is True and gone is False:
            counts.append(k)
        elif (a[k] is True and gone is UNKNOWN) or (a[k] is UNKNOWN and gone is not True):
            maybe = True
    exists = True if counts else UNKNOWN if maybe else False
    value = _and(b, exists)
    out = {"value": value, "since": None, "left": None}
    if value is True:
        out.update(state="met", since=min(counts))
        return out
    live = [k for k in range(0, min(n, len(a))) if a[k] is True and cancelled(k) is False]
    if value is UNKNOWN:
        out["state"] = "unknown"
    elif b is not True and live:
        k = min(live)
        out.update(state="armed", since=k, left=n - k)
    elif len(a) > n and a[n] is True and cancelled(n) is False:
        out.update(state="expired", since=n)
    elif any(a[k] is True for k in range(len(a))):
        out["state"] = "cancelled" if any(a[k] is True and cancelled(k) is True for k in range(len(a))) else "waiting"
    else:
        out["state"] = "waiting"
    return out


def words(spec: dict, state: dict, first_text: str, then_text: str) -> str:
    """The sequence in plain words, as facts about the Set."""
    k, left = state.get("since"), state.get("left")
    ago = "today" if k == 0 else "1 close ago" if k == 1 else f"{k} closes ago"
    s = state["state"]
    if s == "met":
        return f"{first_text} {ago}, then {then_text} today"
    if s == "armed":
        return f"{first_text} {ago}; {then_text} not yet ({left} close{'s' if left != 1 else ''} left)"
    if s == "expired":
        return f"{first_text} {ago}; {then_text} did not follow within {spec['within']}"
    if s == "cancelled":
        return f"{first_text} was seen but cancelled since"
    if s == "unknown":
        return f"{first_text}, then {then_text}: could not be decided"
    return f"waiting for {first_text}"
