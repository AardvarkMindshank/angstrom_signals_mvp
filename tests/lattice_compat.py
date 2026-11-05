"""Compatibility snapshot for Lattice stage 1 (docs/design/lattice_prism.md §4.5, fixture 20).

`snapshot()` evaluates every starter and design example on fixed synthetic data and records content hashes and
results. The committed fixture was written with the code as it was before the stage 1 extensions; the test compares
today's code with it, so documents without the new keys must hash and evaluate exactly as before.

    python -m tests.lattice_compat --write     # only when a deliberate, approved change requires it
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

import signal_groups as sg
from signal_library import DataContext, engine
from signal_library import certify as cf
from tests.replay_helpers import full_indicators

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "lattice_compat.json"
EXAMPLES = ROOT / "docs" / "design" / "examples"


def documents() -> dict:
    docs = {alias: sg.starter(alias) for alias in sorted(sg.STARTERS)}
    for name in ("group_trend_confirmation", "group_reversal_evidence", "set_multi_timeframe"):
        docs[f"example:{name}"] = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return docs


def _ctx(seed: int):
    frame = full_indicators(cf.synthetic_crypto(days=420, seed=seed).histories["1D"].raw)
    data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
    return DataContext("crypto", "x", candle_loader=lambda k, a, tf: data, now=frame.index[-1] + pd.Timedelta(days=1))


def _round(x):
    return None if x is None else round(float(x), 12)


def _group_summary(r: dict) -> dict:
    return {"status": r.get("status"), "score": _round((r.get("score") or {}).get("value")),
            "withheld": (r.get("score") or {}).get("withheld"),
            "conditions": {c["key"]: c["state"] for c in r.get("conditions") or []},
            "members": {m["key"]: [m["signal"]["status"], m.get("state")] for m in r.get("members") or []},
            "keys": sorted(r)}


def snapshot() -> dict:
    out = {"hashes": {}, "valid": {}, "results": {}}
    for name, doc in documents().items():
        out["hashes"][name] = sg.content_sha256(doc)
        is_set = doc.get("schema") == "angstrom.set/1"
        out["valid"][name] = (sg.validate_set if is_set else sg.validate_group)(doc)
        for seed in (1, 2):
            engine.clear_cache()
            if is_set:
                r = sg.evaluate_set(doc, _ctx(seed))
                summary = {"status": r.get("status"), "keys": sorted(r),
                           "groups": {g["key"]: _group_summary(g["result"]) for g in r.get("groups") or []},
                           "standalone": {s["key"]: s["signal"]["status"] for s in r.get("standalone") or []},
                           "shared": (r.get("diagnostics") or {}).get("shared_signals")}
            else:
                summary = _group_summary(sg.evaluate_group(doc, _ctx(seed)))
            out["results"][f"{name}|seed{seed}"] = summary
    return out


if __name__ == "__main__":
    if "--write" in sys.argv:
        FIXTURE.write_text(json.dumps(snapshot(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {FIXTURE}")
    else:
        print(json.dumps(snapshot(), indent=1, sort_keys=True)[:3000])
