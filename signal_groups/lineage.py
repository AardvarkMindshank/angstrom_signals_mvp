"""Lineage tables (design section 3.6): analytical inputs per signal, by version. Not editable by users."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURRENT = 2


@lru_cache(maxsize=None)
def table(version: int = CURRENT) -> dict[str, frozenset]:
    path = HERE / f"lineage_v{int(version)}.json"
    if not path.exists():
        raise KeyError(f"lineage version {version} does not exist")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {sid: frozenset(roots) for sid, roots in doc["roots"].items()}


def roots(signal_id: str, version: int = CURRENT) -> frozenset:
    return table(version)[signal_id]
