"""
Evaluating signals: one call for any list of SignalRefs on one subject.

- Duplicate references (the same signal in two Groups) are calculated once.
- Results are cached in-process, keyed by the reference, the subject and a fingerprint of the
  input data, so a rerun with unchanged candles costs nothing and a new candle refreshes them.
- A failing signal returns an ERROR result; it never stops the others.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

from .core import (
    ERROR, REGISTRY, UNSUPPORTED, SignalRef, SignalResult, now_iso,
)
from .context import DataContext

_CACHE: OrderedDict = OrderedDict()
_LOCK = threading.Lock()
CACHE_SIZE = 512
CACHE_SECONDS = 15 * 60


def _scope_ok(scope: str, ctx: DataContext) -> bool:
    if scope == "asset":
        return ctx.kind in ("crypto", "equity")
    if scope == "crypto_asset":
        return ctx.kind == "crypto"
    if scope.startswith("market:"):
        # "market:crypto|stocks" accepts either subject
        return ctx.kind == "market" and ctx.asset_id in scope.split(":", 1)[1].split("|")
    return False


def evaluate_one(ref: SignalRef, ctx: DataContext) -> SignalResult:
    definition = REGISTRY.get(ref.id, ref.version)
    base = dict(ref=ref.as_dict(), subject=ctx.subject, unit=definition.unit,
                computed_at=now_iso(), instance_key=ref.instance_key)
    if not _scope_ok(definition.scope, ctx):
        return SignalResult(status=UNSUPPORTED, notes=[f"{definition.name} does not apply to {ctx.subject}."], **base)
    if ref.timeframe not in definition.timeframes:
        return SignalResult(status=UNSUPPORTED, notes=[f"{definition.name} does not support {ref.timeframe}."], **base)
    # A replay (signal_library.replay) checks the signal may run at all, uses its own cache and verifies the
    # result against its cutoff. A live context has none of this, so live evaluation is unchanged.
    replay = getattr(ctx, "replay", None)
    if replay is not None:
        refused = replay.permit(definition, ref, ctx)
        if refused is not None:
            refused.computed_at = base["computed_at"]
            refused.unit = definition.unit
            return refused
    cache, cache_size = (_CACHE, CACHE_SIZE) if replay is None else (ctx.result_cache, replay_cache_size())
    # Signals built from other signals are not cached themselves: their parts are, and the parts'
    # data (other timeframes) is not in this signal's fingerprint.
    cacheable = "signals" not in definition.requires
    fingerprint = ctx.fingerprint(definition.requires, ref.timeframe) if cacheable else ""
    cache_key = (ref.instance_key, ctx.subject, fingerprint)
    if cacheable:
        with _LOCK:
            hit = cache.get(cache_key)
            if hit and (replay is not None or time.time() - hit[0] < CACHE_SECONDS):
                cache.move_to_end(cache_key)
                return hit[1]
    outer = getattr(ctx, "current_signal", None)
    if replay is not None:
        ctx.current_signal = definition.key
    try:
        result = definition.compute(ctx, ref.timeframe, dict(ref.params))
        if not isinstance(result, SignalResult):
            raise TypeError("compute must return a SignalResult")
        for name in ("ref", "subject", "computed_at", "instance_key"):
            setattr(result, name, base[name])
        result.unit = result.unit or definition.unit
    except Exception as exc:
        result = SignalResult(status=ERROR, notes=[f"Calculation failed: {exc}"], **base)
    finally:
        if replay is not None:
            ctx.current_signal = outer
    if replay is not None:
        result = replay.verify(result, ctx)
        replay.note_signal(definition, ref, ctx, result)
    if cacheable and result.status != ERROR:  # errors are retried next time
        with _LOCK:
            cache[cache_key] = (time.time(), result)
            while len(cache) > cache_size:
                cache.popitem(last=False)
    return result


def replay_cache_size() -> int:
    from .replay import RUN_CACHE_SIZE

    return RUN_CACHE_SIZE


def evaluate(refs, ctx: DataContext) -> dict[str, SignalResult]:
    """{instance_key: result}; each distinct reference is calculated once."""
    out: dict[str, SignalResult] = {}
    for ref in refs:
        if ref.instance_key not in out:
            out[ref.instance_key] = evaluate_one(ref, ctx)
    return out


def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()
