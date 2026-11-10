"""
Checks a funnel before it is saved (docs/design/funnels_v2_spec.md, part 4): what blocks saving and what only warns.
Used by the Funnels editor and by the tests; the database repeats the structural checks (funnel_save).
"""

from __future__ import annotations

import signal_groups as sg

TIMEFRAMES = ("15m", "30m", "1h", "4h", "12h", "1D", "1W")
ORDER = {tf: i for i, tf in enumerate(TIMEFRAMES)}
WORDS = {"15m": "15-minute", "30m": "30-minute", "1h": "1-hour", "4h": "4-hour", "12h": "12-hour", "1D": "daily",
         "1W": "weekly"}
POOL_SIZES = (50, 100, 200, 500)


def set_timeframes(doc: dict) -> set[str]:
    refs = [m.get("ref") or {} for m in doc.get("standalone") or []]
    for g in doc.get("groups") or []:
        refs += [m.get("ref") or {} for m in (g.get("snapshot") or {}).get("members") or []]
    return {str(r.get("timeframe") or "1D") for r in refs}


def validate(funnel: dict) -> tuple[list[str], list[str]]:
    """(blocks, warnings) in plain words. A funnel saves only without blocks."""
    blocks: list[str] = []
    warns: list[str] = []
    stages = funnel.get("stages") or []
    market = funnel.get("market") or "crypto"
    if funnel.get("direction") not in ("long", "short"):
        blocks.append("Choose long or short.")
    if not 3 <= len(stages) <= 5:
        blocks.append(f"A funnel has 3 to 5 stages (this one has {len(stages)}).")
    for n, stage in enumerate(stages, 1):
        label = stage.get("label") or f"Stage {n}"
        tf = stage.get("timeframe")
        if tf not in TIMEFRAMES:
            blocks.append(f"{label}: choose when it is checked (15 minutes to weekly).")
            continue
        if market == "equity" and tf == "12h":
            blocks.append(f"{label}: shares trade 6½ hours a day, so a 12-hour check is the daily one; use daily.")
        doc = stage.get("set_body")
        if not isinstance(doc, dict):
            blocks.append(f"{label}: choose a Set.")
            continue
        errors = sg.validate_set(doc)
        if errors:
            blocks.append(f"{label}: the Set is not valid ({errors[0]}).")
            continue
        if not sg.scannable(doc):
            blocks.append(f"{label}: the Set has no Yes/No decision, so it cannot be checked.")
            continue
        reads = set_timeframes(doc)
        if reads and reads != {tf}:
            words = ", ".join(WORDS.get(t, t) for t in sorted(reads, key=lambda t: ORDER.get(t, 9)))
            warns.append(f"{label} is checked at each {WORDS[tf]} close, and its Set reads {words} candles. That's "
                         "allowed: the stage sets when it is checked, not what the Set reads.")
    tfs = [s.get("timeframe") for s in stages if s.get("timeframe") in ORDER]
    if any(ORDER[a] < ORDER[b] for a, b in zip(tfs, tfs[1:])):
        warns.append("The stages don't run from the longest timeframe to the shortest. A funnel usually narrows from "
                     "weekly or daily down to the hour.")
    pool = funnel.get("pool") or {}
    if pool.get("top") is not None and pool.get("top") not in POOL_SIZES:
        blocks.append("Pool size: choose the top 50, 100, 200 or 500.")
    if pool.get("min_volume") is not None and not (0 <= float(pool.get("min_volume")) <= 1e10):
        blocks.append("Minimum daily volume: choose a value from 0 to $10 billion.")
    return blocks, warns
