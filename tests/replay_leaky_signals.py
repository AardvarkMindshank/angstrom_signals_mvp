"""Deliberately broken signals that the replay certification suite must refuse (mutation checks).
Registered under "test." ids, which the app and the real certification run ignore."""

import pandas as pd

from signal_library.core import CONFIRMED, NUMERIC, OK, SCOPE_ASSET, SignalResult, signal
from signal_library.signals_basic import bar_times, closed_candles

_SEEN = {}


def _base(ctx, timeframe, value, evidence=None):
    frame, loaded, failed = closed_candles(ctx, timeframe, 20)
    if failed:
        return None, failed
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return frame, SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=value,
                               observed_at=observed, available_at=available, evidence=evidence or {})


SPEC = dict(category="test", output=NUMERIC, unit="price", scope=SCOPE_ASSET, timeframes=("1D",), requires=("candles",),
            calculation="test", interpretation="test", limitations="test")


@signal(id="test.leak_global_max", version=1, name="Leaks through a module-level memory", **SPEC)
def leak_global_max(ctx, timeframe, params):
    """Remembers the close from its previous call for the subject and reports the higher of the two: whatever was
    evaluated before (a later cutoff, another run) leaks into this result."""
    frame, loaded, failed = closed_candles(ctx, timeframe, 20)
    if failed:
        return failed
    close = float(frame["close"].iloc[-1])
    best = max(_SEEN.get(ctx.subject, float("-inf")), close)
    _SEEN[ctx.subject] = close
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED, value=round(best, 6),
                        observed_at=observed, available_at=available)


@signal(id="test.future_timestamp", version=1, name="Reports a timestamp after the cutoff", **SPEC)
def future_timestamp(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 20)
    if failed:
        return failed
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    nxt = (pd.Timestamp(available) + pd.Timedelta(days=3)).isoformat()
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED,
                        value=float(frame["close"].iloc[-1]), observed_at=observed, available_at=available,
                        evidence={"next_review_at": nxt})


@signal(id="test.honest_close", version=1, name="Honest: last close and its SMA 20", **SPEC)
def honest_close(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 20)
    if failed:
        return failed
    observed, available = bar_times(ctx, loaded, timeframe, frame.index[-1])
    return SignalResult(ref={}, subject=ctx.subject, status=OK, confirmation=CONFIRMED,
                        value=float(frame["close"].iloc[-1]), observed_at=observed, available_at=available,
                        evidence={"sma_20": round(float(frame["sma_20"].iloc[-1]), 8)})


def centred_indicators(raw):
    """A non-causal indicator set: sma_20 is centred, so it uses the next 10 candles."""
    from tests.replay_helpers import simple_indicators

    df = simple_indicators(raw)
    df["sma_20"] = df["close"].rolling(21, center=True, min_periods=1).mean()
    return df
