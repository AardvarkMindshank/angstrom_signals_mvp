"""
Plain-words summaries of Signal Library results and the lists of signals to run per asset or market, used by the
live checks in CI (signal_library_live.py, tests/live_golden.py). The admin panel that showed these was removed.
"""

from __future__ import annotations


import signal_library as sl
from signal_library.core import EVENTS, LEVELS, OBSERVATION, OK



def summary(result) -> str:
    """One line for the table; the full value is in the details."""
    if result.status != OK and result.value is None:
        return (result.notes or [result.status])[0]
    value = result.value
    if not isinstance(value, dict):
        return str(value)
    if "summary" in value:
        return value["summary"]
    if "events" in value:
        latest = (value.get("events") or [])[-1:] or [None]
        dev = value.get("developing") or []
        text = "no recent events" if latest[0] is None else (
            f"latest {latest[0].get('type') or latest[0].get('kind')} {latest[0].get('direction', '')} "
            f"({latest[0].get('status', 'confirmed')}) at {latest[0].get('confirmed_at') or latest[0].get('time')}")
        return text + (f"; developing: {', '.join(d['type'] for d in dev)}" if dev else "")
    if "support" in value:
        s = value.get("support") or []
        r = value.get("resistance") or []
        fmt = lambda z: f"{z['low']:.6g}–{z['high']:.6g} ({z['touches']}×)"  # noqa: E731
        return f"support {', '.join(map(fmt, s)) or '–'} | resistance {', '.join(map(fmt, r)) or '–'}"
    if "structure" in value:
        return f"{value['structure']}; last high {value.get('last_swing_high')}, last low {value.get('last_swing_low')}"
    if "state" in value:
        return (f"{value['state']} ({value.get('direction')}), ADX {value.get('adx')}, ER {value.get('efficiency_ratio_20')}, "
                f"volatility {value.get('volatility')}")
    keys = list(value)[:4]
    return ", ".join(f"{k} {value[k]}" for k in keys)


def asset_refs(kind: str, timeframe: str) -> list:
    refs = []
    for definition in sl.REGISTRY.latest():
        if definition.id.startswith("test."):
            continue
        if definition.scope == "asset" or (definition.scope == "crypto_asset" and kind == "crypto"):
            tf = timeframe if timeframe in definition.timeframes else definition.timeframes[0]
            refs.append(sl.SignalRef.make(definition, tf))
    return refs


def market_refs() -> list:
    return [sl.SignalRef.make(d, d.timeframes[0]) for d in sl.REGISTRY.latest() if d.scope.startswith("market:")]


