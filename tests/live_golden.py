"""Snapshot of live (not replayed) results on fixed synthetic data, used to prove that replay work leaves live
evaluation byte for byte unchanged. Administrative timestamps (when something was computed) are removed.

Regenerate only when a live result is meant to change:  python -m tests.live_golden --write
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ADMIN_KEYS = {"computed_at", "evaluated_at", "as_of"}
GOLDEN = Path(__file__).resolve().parent / "fixtures" / "live_golden.json"


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in ADMIN_KEYS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def snapshot() -> dict:
    import signal_groups as sg
    import signal_inspector
    from signal_library import REGISTRY, DataContext, SignalRef, engine, evaluate
    from tests import test_signal_library_market as mk
    from tests.test_signal_library_ta import _ctx

    engine.clear_cache()
    out = {"signals": {}, "market": {}, "derivatives": {}, "groups": {}, "set": None}
    ctx = _ctx()
    for tf in ("15m", "1h", "4h", "1D", "1W"):
        refs = [r for r in signal_inspector.asset_refs("crypto", tf) if r.timeframe == tf]
        for key, result in evaluate(refs, ctx).items():
            out["signals"][key] = result.as_dict()
    flows = mk._flows_ctx(mk._etf_rows())
    for d in REGISTRY.latest():
        if d.scope == "market:bitcoin":
            ref = SignalRef.make(d, d.timeframes[0])
            out["market"][ref.instance_key] = evaluate([ref], flows)[ref.instance_key].as_dict()
    deriv = mk._deriv_ctx(mk._record())
    for d in REGISTRY.latest():
        if d.scope == "crypto_asset":
            ref = SignalRef.make(d, d.timeframes[0])
            out["derivatives"][ref.instance_key] = evaluate([ref], deriv)[ref.instance_key].as_dict()
    engine.clear_cache()
    for alias in sg.STARTERS:
        out["groups"][alias] = sg.evaluate_group(sg.starter(alias), _ctx())
    import signal_groups_inspector as gi
    out["set"] = sg.evaluate_set(gi.example_set(), _ctx(), market_context=lambda scope: mk._flows_ctx(mk._etf_rows()))
    engine.clear_cache()
    return _strip(json.loads(json.dumps(out, default=str)))


if __name__ == "__main__":
    if "--write" in sys.argv:
        GOLDEN.write_text(json.dumps(snapshot(), indent=1, sort_keys=True) + "\n")
        print("written", GOLDEN)
