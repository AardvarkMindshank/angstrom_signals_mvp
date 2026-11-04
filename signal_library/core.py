"""
Signal Library core: what a signal is, what one evaluation returns, and the registry.

Layers (see docs/signal_library.md):
    Data Sources -> Signal Library -> Signal Groups -> Signal Sets -> Workspace / Strategies

This module is only the Signal Library layer. It knows nothing about Groups or Sets. A Group will
refer to signals through a SignalRef (definition id, pinned version, parameters, timeframe); the
library guarantees that the same SignalRef on the same data always gives the same result, and that
two Groups using the same SignalRef share one calculation.

Rules kept here so every signal follows them:
- Native units. A result carries its own value type and unit; nothing is forced onto -100..+100.
  Turning a value into a score is a Group's job, and must be stated explicitly there.
- Closed candles only for confirmed readings. A reading that can still change is marked
  "developing", never "confirmed".
- Timing. Every result says when the observation is about (observed_at) and when it could first
  have been known (available_at). Backfilled history is flagged.
- Provenance. Every result names its data sources.
- Versions. A definition's version changes whenever its calculation changes; parameters are part of
  the SignalRef, not the version.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

# --------------------------------------------------------------------------- vocab

# What kind of value a signal returns.
NUMERIC = "numeric"          # a number in native units (e.g. ADX 31.2, US$ 412m)
DIRECTION = "direction"      # "up" | "down" | "flat" (or "mixed"), with optional strength in native units
BOOLEAN = "boolean"          # a condition that holds or not
CATEGORY = "category"        # one of a declared set of labels (e.g. regime)
EVENTS = "events"            # a list of dated occurrences (e.g. confirmed divergences)
LEVELS = "levels"            # prices or price zones
OBSERVATION = "observation"  # a structured record (several named fields) for context
OUTPUT_TYPES = (NUMERIC, DIRECTION, BOOLEAN, CATEGORY, EVENTS, LEVELS, OBSERVATION)

# Status of one evaluation.
OK = "ok"
INSUFFICIENT = "insufficient_data"   # data exists but too little history for this calculation
MISSING = "missing_data"             # a required input could not be loaded
STALE = "stale"                      # the newest input is older than the signal allows
UNSUPPORTED = "unsupported"          # asset, market or timeframe not supported by this signal
ERROR = "error"
NOT_REPLAYABLE = "not_replayable"   # replays only: the signal or its data source cannot be reconstructed at T
STATUSES = (OK, INSUFFICIENT, MISSING, STALE, UNSUPPORTED, ERROR, NOT_REPLAYABLE)

# Confirmation of the value itself.
CONFIRMED = "confirmed"      # built only from closed candles / published data; will not change
DEVELOPING = "developing"    # includes something that can still change (forming candle, unconfirmed pivot)
NOT_APPLICABLE = "n/a"

TIMEFRAMES = ("15m", "1h", "4h", "1D", "1W")
MARKET_TIMEFRAME = "1D"      # market-level daily series (ETF flows, stablecoin supply)

# Scopes: which subjects a signal can be asked about.
SCOPE_ASSET = "asset"                    # any watchlist asset (crypto or equity)
SCOPE_CRYPTO_ASSET = "crypto_asset"      # crypto assets only (derivatives data)
SCOPE_MARKET_BTC = "market:bitcoin"      # one market-wide subject
SCOPE_MARKET_CRYPTO = "market:crypto"


# --------------------------------------------------------------------------- definitions

@dataclass(frozen=True)
class Param:
    """One adjustable parameter. Defaults are conventions, never tuned on future returns."""
    default: Any
    kind: str = "int"                 # int | float | choice | bool
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple = ()
    doc: str = ""

    def check(self, value):
        if self.kind == "int":
            value = int(value)
        elif self.kind == "float":
            value = float(value)
        elif self.kind == "bool":
            value = bool(value)
        elif self.kind == "choice" and value not in self.choices:
            raise ValueError(f"{value!r} is not one of {self.choices}")
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{value} is below {self.minimum}")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"{value} is above {self.maximum}")
        return value


@dataclass(frozen=True)
class SignalDefinition:
    """A versioned, documented calculation. Immutable: change the calculation -> new version."""
    id: str                            # stable dotted id, e.g. "ta.divergence.rsi"
    version: int
    name: str                          # short human name
    category: str                      # trend | momentum | structure | regime | volume | flows | positioning
    output: str                        # one of OUTPUT_TYPES
    unit: str                          # native unit ("points", "USD", "price", "%", "label", ...)
    scope: str                         # one of the SCOPE_* values
    timeframes: tuple                  # supported timeframes
    requires: tuple                    # data keys the DataContext must supply (see context.py)
    calculation: str                   # exact calculation, plain words
    interpretation: str                # what it does and does not mean
    limitations: str                   # when it misleads
    compute: Callable = field(compare=False, repr=False, default=None)
    params: dict = field(default_factory=dict, compare=False)
    labels: tuple = ()                 # for CATEGORY outputs: every possible label
    polarity: str = ""                 # for DIRECTION/EVENTS: what "up"/"bullish" refers to (descriptive only)
    max_age_bars: int | None = None    # older newest-input than this (in bars of the timeframe) -> STALE
    evidence_strength: str = "descriptive"   # descriptive | researched (only with out-of-sample evidence)

    @property
    def key(self) -> str:
        return f"{self.id}@{self.version}"

    def describe(self) -> dict:
        out = {k: v for k, v in asdict(self).items() if k not in ("compute", "params")}
        out["params"] = {name: asdict(p) for name, p in self.params.items()}
        out["key"] = self.key
        return out


@dataclass(frozen=True)
class SignalRef:
    """What a Group (later) stores to point at a signal: id, pinned version, parameters, timeframe.
    The subject (asset) is supplied when the Group is applied, so one Group works on any asset."""
    id: str
    version: int
    timeframe: str
    params: tuple = ()                 # sorted (name, value) pairs; use SignalRef.make()

    @staticmethod
    def make(definition: SignalDefinition, timeframe: str | None = None, **params) -> "SignalRef":
        timeframe = timeframe or definition.timeframes[0]
        if timeframe not in definition.timeframes:
            raise ValueError(f"{definition.key} does not support timeframe {timeframe}")
        full = {}
        for name, spec in definition.params.items():
            full[name] = spec.check(params.pop(name, spec.default))
        if params:
            raise ValueError(f"{definition.key} has no parameter(s) {sorted(params)}")
        return SignalRef(definition.id, definition.version, timeframe, tuple(sorted(full.items())))

    def as_dict(self) -> dict:
        return {"id": self.id, "version": self.version, "timeframe": self.timeframe, "params": dict(self.params)}

    @property
    def instance_key(self) -> str:
        """Stable across processes: the same reference always hashes the same."""
        raw = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), default=str)
        return f"{self.id}@{self.version}:{self.timeframe}:" + hashlib.sha1(raw.encode()).hexdigest()[:10]


# --------------------------------------------------------------------------- results

@dataclass
class SignalResult:
    ref: dict                          # SignalRef.as_dict()
    subject: str                       # e.g. "crypto:bitcoin", "equity:AAPL", "market:bitcoin"
    status: str
    confirmation: str = NOT_APPLICABLE
    value: Any = None                  # native value; shape depends on the definition's output type
    unit: str = ""
    observed_at: str | None = None     # ISO UTC: the bar/day the value describes (bar open time for candles)
    available_at: str | None = None    # ISO UTC: when it could first be known (bar close, publication, first seen)
    computed_at: str = ""
    backfilled: bool = False           # True when available_at is a history load, not a real-time observation
    evidence: dict = field(default_factory=dict)    # inputs and intermediate values for inspection
    provenance: list = field(default_factory=list)  # source names / attribution lines
    notes: list = field(default_factory=list)       # plain-language caveats for this evaluation
    instance_key: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iso(ts) -> str | None:
    if ts is None:
        return None
    try:
        import pandas as pd

        stamp = pd.Timestamp(ts)
        stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
        return stamp.isoformat()
    except Exception:
        return str(ts)


# --------------------------------------------------------------------------- registry

class Registry:
    """Every definition, every version. Old versions stay registered so pinned references keep working."""

    def __init__(self):
        self._defs: dict[tuple[str, int], SignalDefinition] = {}

    def register(self, definition: SignalDefinition) -> SignalDefinition:
        if definition.output not in OUTPUT_TYPES:
            raise ValueError(f"{definition.key}: unknown output type {definition.output}")
        for tf in definition.timeframes:
            if tf not in TIMEFRAMES:
                raise ValueError(f"{definition.key}: unknown timeframe {tf}")
        key = (definition.id, definition.version)
        if key in self._defs and self._defs[key] != definition:
            raise ValueError(f"{definition.key} is already registered with a different definition; bump the version")
        self._defs[key] = definition
        return definition

    def get(self, signal_id: str, version: int | None = None) -> SignalDefinition:
        if version is None:
            versions = [v for (i, v) in self._defs if i == signal_id]
            if not versions:
                raise KeyError(signal_id)
            version = max(versions)
        return self._defs[(signal_id, int(version))]

    def latest(self) -> list[SignalDefinition]:
        newest: dict[str, SignalDefinition] = {}
        for (signal_id, version), definition in self._defs.items():
            if signal_id not in newest or version > newest[signal_id].version:
                newest[signal_id] = definition
        return sorted(newest.values(), key=lambda d: (d.category, d.id))

    def catalogue(self) -> list[dict]:
        return [d.describe() for d in self.latest()]


REGISTRY = Registry()


def signal(**spec):
    """Decorator: register a compute function as a signal definition."""
    def wrap(fn):
        REGISTRY.register(SignalDefinition(compute=fn, **spec))
        return fn
    return wrap
