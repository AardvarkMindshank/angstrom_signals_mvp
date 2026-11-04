"""
Transforms v1 (design section 3.3): native signal value -> number in [-1, 1], or UNKNOWN.

Unknown is never 0. Non-finite numbers, nulls, missing field paths and unlisted labels are unknown.
"""

from __future__ import annotations

import math

UNKNOWN = "unknown"
KINDS = ("map", "bands", "clip", "events")


def resolve(value, path: str | None):
    """(found, value) for a dotted path with integer list indexes. No path = the value itself."""
    if not path:
        return value is not None, value
    for part in str(path).split("."):
        if isinstance(value, list) and part.isdigit():
            idx = int(part)
            if idx >= len(value):
                return False, None
            value = value[idx]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return False, None
    return value is not None, value


def _number(x):
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, str):
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def config_errors(t: dict) -> list[str]:
    """Problems with a transform's parameters (empty = valid)."""
    errors = []
    kind = t.get("kind")
    if kind not in KINDS:
        return [f"unknown transform kind {kind!r}"]
    if t.get("version", 1) != 1:
        errors.append(f"{kind}: only version 1 exists")
    if kind == "map":
        mapping = t.get("map")
        if not isinstance(mapping, dict) or not mapping:
            errors.append("map: 'map' must be a non-empty object")
        else:
            for label, v in mapping.items():
                if v is not None and (_number(v) is None or not -1 <= v <= 1):
                    errors.append(f"map: value for {label!r} must be in [-1, 1] or null")
    elif kind == "bands":
        bands = t.get("bands")
        if not isinstance(bands, list) or not bands:
            return errors + ["bands: 'bands' must be a non-empty list"]
        ordered = sorted(bands, key=lambda b: (-math.inf if b.get("from") is None else b["from"]))
        if ordered[0].get("from") is not None:
            errors.append("bands: the lowest band must start at null (unbounded)")
        if ordered[-1].get("to") is not None:
            errors.append("bands: the highest band must end at null (unbounded)")
        for a, b in zip(ordered, ordered[1:]):
            if a.get("to") is None or b.get("from") is None or a["to"] != b["from"]:
                errors.append(f"bands: gap or overlap between {a} and {b}")
        for b in ordered:
            v = _number(b.get("value"))
            if v is None or not -1 <= v <= 1:
                errors.append(f"bands: value {b.get('value')!r} must be in [-1, 1]")
            if b.get("from") is not None and b.get("to") is not None and not b["from"] < b["to"]:
                errors.append(f"bands: empty band {b}")
    elif kind == "clip":
        low, high = _number(t.get("low")), _number(t.get("high"))
        if low is None or high is None or not low < high:
            errors.append("clip: low and high must be finite with low < high")
    elif kind == "events":
        ups = list(t.get("up_types") or []) + list(t.get("up_kinds") or [])
        downs = list(t.get("down_types") or []) + list(t.get("down_kinds") or [])
        if not ups and not downs:
            errors.append("events: give up_types/up_kinds and/or down_types/down_kinds")
    return errors


def _event_dir(event: dict, t: dict) -> int:
    up = event.get("type") in (t.get("up_types") or []) or (
        event.get("kind") in (t.get("up_kinds") or []) and event.get("direction") in (None, "bullish"))
    down = event.get("type") in (t.get("down_types") or []) or (
        event.get("kind") in (t.get("down_kinds") or []) and event.get("direction") in (None, "bearish"))
    return 1 if up and not down else -1 if down and not up else 0


def apply(t: dict, value, candles_since=None) -> tuple[object, list[str]]:
    """(number in [-1, 1] or UNKNOWN, flags). `candles_since(event)` supports `within_candles` for events."""
    kind = t["kind"]
    if kind == "events":
        if not isinstance(value, dict) or not isinstance(value.get("events"), list):
            return UNKNOWN, []
        events = [e for e in value["events"] if e.get("status", "confirmed") == "confirmed"]
        limit = t.get("within_candles")
        if limit is not None and candles_since is not None:
            events = [e for e in events if (candles_since(e) is not None and candles_since(e) <= limit)]
        dirs = {_event_dir(e, t) for e in events} - {0}
        if dirs == {1}:
            return 1.0, []
        if dirs == {-1}:
            return -1.0, []
        if dirs == {1, -1}:
            return 0.0, ["conflicting_events"]
        return 0.0, []
    found, x = resolve(value, t.get("field"))
    if not found:
        return UNKNOWN, []
    if kind == "map":
        if isinstance(x, bool) or not isinstance(x, (str, int, float)):
            return UNKNOWN, []
        mapped = t["map"].get(str(x)) if str(x) in t["map"] else None
        return (UNKNOWN, []) if mapped is None else (float(mapped), [])
    x = _number(x)
    if x is None:
        return UNKNOWN, []
    if kind == "bands":
        for band in t["bands"]:
            lo, hi = band.get("from"), band.get("to")
            if (lo is None or x >= lo) and (hi is None or x < hi):
                return float(band["value"]), []
        return UNKNOWN, []
    if kind == "clip":
        low, high = float(t["low"]), float(t["high"])
        if low == -1.0 and high == 1.0:     # the identity on -1..+1, without the rounding of the general formula
            c = max(-1.0, min(1.0, x))
        else:
            c = max(-1.0, min(1.0, 2 * (x - low) / (high - low) - 1))
        return (-c if t.get("invert") else c), []
    return UNKNOWN, []
