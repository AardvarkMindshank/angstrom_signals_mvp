"""
Replay certification records (design section 4): which signal versions may run in a replay, per timeframe.

The record is signal_library/certification.json, written by the certification suite (replay_certify.py, run in
CI on every change) and committed. It is only trusted for the exact code it was produced from: it stores a hash
of the replay-relevant source files, and if the code differs nothing counts as certified until the suite is
re-run. A signal with no record is not certified.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = Path(__file__).resolve().parent / "certification.json"
SUITE_VERSION = 2   # 2: slice equivalence within a stated tolerance (point_in_time.md §13)

# Everything a replayed signal's result depends on. Changing any of these requires re-certification.
CODE_FILES = ("signal_library/core.py", "signal_library/context.py", "signal_library/engine.py",
              "signal_library/signals_basic.py", "signal_library/signals_ta.py", "signal_library/signals_market.py",
              "signal_library/swings.py", "signal_library/replay.py", "signal_library/signals_components.py",
              "signal_library/signals_sentiment.py", "signal_library/signals_candles.py", "signal_library/signals_oscillators.py", "signals_v2.py", "score_colours.py", "scoring.py", "regime.py",
              "chart_data.py")


@lru_cache(maxsize=1)
def code_hash() -> str:
    digest = hashlib.sha256()
    for name in CODE_FILES:
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


@lru_cache(maxsize=1)
def load() -> dict:
    try:
        return json.loads(RECORD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def reset() -> None:
    load.cache_clear()
    code_hash.cache_clear()


def current() -> bool:
    record = load()
    return bool(record) and record.get("suite_version") == SUITE_VERSION and record.get("code_sha256") == code_hash()


def status(signal_key: str, timeframe: str) -> dict:
    """{"algorithm": "certified"|"not_certified", "slice_equivalent": bool, "reason": text}."""
    record = load()
    if not record:
        return {"algorithm": "not_certified", "slice_equivalent": False, "reason": "no certification record"}
    if not current():
        return {"algorithm": "not_certified", "slice_equivalent": False,
                "reason": "the certification record is for different code; the suite must be re-run"}
    entry = ((record.get("signals") or {}).get(signal_key) or {}).get(timeframe)
    if not entry:
        return {"algorithm": "not_certified", "slice_equivalent": False,
                "reason": f"{signal_key} on {timeframe} has not been through the certification suite"}
    return {"algorithm": entry.get("algorithm", "not_certified"),
            "slice_equivalent": bool(entry.get("slice_equivalent")),
            "reason": entry.get("reason")}


def suite_reference() -> dict:
    record = load()
    return {"suite_version": record.get("suite_version"), "code_sha256": record.get("code_sha256"),
            "generated_by": record.get("generated_by"), "current": current()}
