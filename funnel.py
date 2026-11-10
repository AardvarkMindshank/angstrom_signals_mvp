"""
The funnel: a dynamic watchlist in stages (decided 10 Nov 2026; docs/research/funnel_brief_2026-11-10.md, "Decision
after review"). This module is the bookkeeping only: what a coin's place is after each stage check. It knows nothing
about candles, storage or alerts, so every rule here is tested on its own.

A funnel is an ordered list of stages, each a saved Set (pinned to a version) on its own timeframe, and a direction
(long or short; each direction is its own funnel). The last stage is the entry check: a coin that holds every stage is
a **Candidate**; one that holds every stage but the last is **Flagged** ("on the shortlist, waiting for the entry
conditions").

Rules (numbers refer to the decision):
* (2) A stage is checked only for coins that hold the stage before; the others show "not checked", never No.
* (4) Entry is immediate on a Yes. With the flicker rule on (the default), a coin stops holding a stage only after
  NO_CLOSES_TO_LEAVE No answers in a row on that stage's timeframe; with it off, one No is enough.
* (3) When a stage stops holding, every stage after it is dropped at once (not at its own next close).
* (5) Unknown (missing data) never promotes: a stage that has never said Yes stays not held. A held stage stays held
  but is shown as ❔ Pending, and no Candidate is counted or alerted while any stage is pending. After
  PENDING_CLOSES_TO_LEAVE Unknown closes in a row the stage stops holding.
* (9) Alerts: only on newly becoming a Candidate, latched until the coin stops being a Candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

YES, NO, UNKNOWN = "yes", "no", "unknown"
NO_CLOSES_TO_LEAVE = 2
PENDING_CLOSES_TO_LEAVE = 3

POOL, STAGE, FLAGGED, CANDIDATE, PENDING = "pool", "stage", "flagged", "candidate", "pending"
ICONS = {POOL: "⚪", FLAGGED: "🚩", CANDIDATE: "✅", PENDING: "❔"}
STAGE_ICONS = ("👁", "🔷", "📋", "📋")            # stage 1, 2, 3 (... the shortlist), by position
DIRECTION_ICONS = {"long": "▲", "short": "▼"}
FLAGGED_HOVER = "On the shortlist: the {stages} agree; waiting for the {entry} entry conditions."
CANDIDATE_HOVER = "Every stage holds, including the {entry} entry conditions. A coin to look at now, not a recommendation."


@dataclass
class StageState:
    held: bool = False
    answer: str | None = None            # the last answer at a close: yes, no, unknown; None = not checked
    no_run: int = 0                      # No answers in a row
    unknown_run: int = 0                 # Unknown answers in a row
    checked_at: str | None = None        # the close it was last checked at (ISO, UTC)
    line: str | None = None              # the deciding line, in words, from the Set's decision


@dataclass
class CoinState:
    stages: list[StageState] = field(default_factory=list)
    latched: bool = False                # a Candidate alert went out and the coin is still a Candidate

    @classmethod
    def new(cls, n: int) -> "CoinState":
        return cls(stages=[StageState() for _ in range(n)])

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None, n: int) -> "CoinState":
        if not d:
            return cls.new(n)
        stages = [StageState(**s) for s in (d.get("stages") or [])][:n]
        stages += [StageState() for _ in range(n - len(stages))]
        return cls(stages=stages, latched=bool(d.get("latched")))


def reachable(state: CoinState, k: int) -> bool:
    """Is stage k checked at all? Only when every stage before it holds."""
    return all(s.held for s in state.stages[:k])


def record(state: CoinState, k: int, answer: str, at: str, line: str | None = None, flicker: bool = True) -> CoinState:
    """The answer of stage k at one of its closes. Ignored (returns the state unchanged) when the stage is not
    reachable; a coin must hold the stages before it to be checked."""
    if not reachable(state, k):
        return state
    s = state.stages[k]
    s.answer, s.checked_at, s.line = answer, at, line
    if answer == YES:
        s.held, s.no_run, s.unknown_run = True, 0, 0
    elif answer == NO:
        s.no_run, s.unknown_run = s.no_run + 1, 0
        if s.no_run >= (NO_CLOSES_TO_LEAVE if flicker else 1):
            s.held = False
    else:
        s.unknown_run += 1
        if s.unknown_run >= PENDING_CLOSES_TO_LEAVE:
            s.held = False
    if not s.held:                                  # (3) the stages after it drop at once
        for later in state.stages[k + 1:]:
            later.held, later.answer, later.no_run, later.unknown_run = False, None, 0, 0
    return state


def place(state: CoinState) -> dict:
    """Where the coin is: {"status", "depth" (stages held in a row), "pending": bool, "leaving": bool}.
    status: pool (no stage held), stage (part way), flagged (all but the last), candidate (all)."""
    n = len(state.stages)
    depth = 0
    for s in state.stages:
        if not s.held:
            break
        depth += 1
    pending = any(s.held and s.answer == UNKNOWN for s in state.stages[:depth])
    leaving = any(s.held and s.answer == NO for s in state.stages[:depth])      # one No; one more and it leaves
    if depth == 0:
        status = POOL
    elif depth == n:
        status = CANDIDATE
    elif depth == n - 1:
        status = FLAGGED
    else:
        status = STAGE
    return {"status": status, "depth": depth, "pending": pending, "leaving": leaving}


def icon(state: CoinState) -> str:
    p = place(state)
    if p["pending"]:
        return ICONS[PENDING]
    if p["status"] == STAGE:
        return STAGE_ICONS[min(p["depth"], len(STAGE_ICONS)) - 1]
    return ICONS[p["status"]]


def alert_due(state: CoinState) -> bool:
    """(9) Alert once on becoming a Candidate; the latch holds until the coin stops being one. Call after each run;
    it updates the latch. A pending Candidate is not alerted (and does not release the latch)."""
    p = place(state)
    if p["status"] == CANDIDATE and not p["pending"]:
        if not state.latched:
            state.latched = True
            return True
        return False
    if p["status"] != CANDIDATE:
        state.latched = False
    return False


def counts(states: dict[str, CoinState], n_stages: int) -> dict:
    """Coins per place, for the stage picker. They always add up to the pool: every coin is counted once."""
    out = {"pool": len(states), "reached": [0] * n_stages, "flagged": 0, "candidate": 0, "pending": 0}
    for st in states.values():
        p = place(st)
        for k in range(p["depth"]):
            out["reached"][k] += 1
        if p["pending"]:
            out["pending"] += 1
        elif p["status"] == CANDIDATE:
            out["candidate"] += 1
        elif p["status"] == FLAGGED:
            out["flagged"] += 1
    return out
