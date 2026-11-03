import json

import numpy as np
import pandas as pd
import pytest

import chart_data
from signal_library import REGISTRY, DataContext, SignalRef, evaluate
from signal_library import engine
from signal_library.core import (
    CATEGORY, CONFIRMED, INSUFFICIENT, MISSING, OK, UNSUPPORTED, Param, Registry, SignalDefinition,
)


def _frame(n=260, seed=1, freq="4h", end="2026-11-03 08:00", forming=True):
    index = pd.date_range(end=end, periods=n, freq=freq, tz="UTC")
    rng = np.random.default_rng(seed)
    close = 100 + rng.normal(0.2, 1, n).cumsum()
    df = pd.DataFrame({"open": close - 0.3, "high": close + 1, "low": close - 1, "close": close,
                       "volume": 1000.0}, index=index)
    df["sma_50"] = df["close"].rolling(50).mean()
    df["sma_200"] = df["close"].rolling(200).mean()
    df["adx"] = 30.0
    df["forming"] = False
    if forming:
        df.iloc[-1, df.columns.get_loc("forming")] = True
    return df


def _ctx(frame=None, error=None, kind="crypto"):
    def loader(k, a, tf):
        if error:
            return {"error": error}
        return {"frame": frame if frame is not None else _frame(), "session": None, "source": "test candles"}
    return DataContext(kind, "bitcoin", candle_loader=loader, now="2026-11-03 10:00")


def setup_function(_):
    engine.clear_cache()


def test_refs_are_stable_and_validate_parameters():
    d = REGISTRY.get("regime.state")
    a = SignalRef.make(d, "4h", confirm=3)
    b = SignalRef.make(d, "4h")
    assert a == b and a.instance_key == b.instance_key
    assert SignalRef.make(d, "4h", confirm=5).instance_key != a.instance_key
    with pytest.raises(ValueError):
        SignalRef.make(d, "4h", confirm=99)
    with pytest.raises(ValueError):
        SignalRef.make(d, "4h", nonsense=1)
    with pytest.raises(ValueError):
        SignalRef.make(d, "2h")
    json.dumps(a.as_dict())  # a Group can store it as JSON


def test_versions_are_immutable():
    reg = Registry()
    spec = dict(id="x.y", version=1, name="X", category="trend", output=CATEGORY, unit="label", scope="asset",
                timeframes=("1D",), requires=(), calculation="c", interpretation="i", limitations="l")
    reg.register(SignalDefinition(**spec))
    reg.register(SignalDefinition(**spec))  # same definition again is fine
    with pytest.raises(ValueError):
        reg.register(SignalDefinition(**{**spec, "calculation": "changed"}))
    reg.register(SignalDefinition(**{**spec, "version": 2, "calculation": "changed"}))
    assert reg.get("x.y").version == 2 and reg.get("x.y", 1).calculation == "c"


def test_result_uses_closed_candles_and_carries_timing():
    frame = _frame()
    out = evaluate([SignalRef.make(REGISTRY.get("trend.direction"), "4h")], _ctx(frame))
    result = next(iter(out.values()))
    assert result.status == OK and result.confirmation == CONFIRMED
    assert result.value in ("up", "down", "mixed")
    last_closed = frame.index[-2]
    assert result.observed_at == last_closed.isoformat()
    assert pd.Timestamp(result.available_at) == last_closed + pd.Timedelta(hours=4)
    assert result.provenance == ["test candles"]
    json.dumps(result.as_dict())


def test_shared_signal_is_calculated_once_for_two_groups():
    calls = []
    frame = _frame()

    def loader(k, a, tf):
        calls.append(tf)
        return {"frame": frame, "session": None, "source": "t"}

    ctx = DataContext("crypto", "bitcoin", candle_loader=loader)
    ref = SignalRef.make(REGISTRY.get("regime.state"), "4h")
    group_a = [ref, SignalRef.make(REGISTRY.get("trend.direction"), "4h")]
    group_b = [ref]
    out = evaluate(group_a + group_b, ctx)
    assert len(out) == 2 and calls == ["4h"]  # one candle load for both signals


def test_cache_reuses_until_data_changes():
    ref = SignalRef.make(REGISTRY.get("regime.state"), "4h")
    first = evaluate([ref], _ctx(_frame()))[ref.instance_key]
    again = evaluate([ref], _ctx(_frame()))[ref.instance_key]
    assert again is first
    newer = evaluate([ref], _ctx(_frame(end="2026-11-03 12:00")))[ref.instance_key]
    assert newer is not first


def test_missing_insufficient_and_unsupported_are_explicit():
    ref = SignalRef.make(REGISTRY.get("trend.direction"), "1D")
    assert evaluate([ref], _ctx(error="Yahoo down"))[ref.instance_key].status == MISSING
    short = evaluate([ref], _ctx(_frame(n=20)))[ref.instance_key]
    assert short.status == INSUFFICIENT and "needed" in short.notes[0]
    market = DataContext("market", "bitcoin", candle_loader=lambda *a: {})
    assert evaluate([ref], market)[ref.instance_key].status == UNSUPPORTED


def test_one_failing_signal_does_not_stop_others():
    def boom(ctx, tf, params):
        raise RuntimeError("bad")
    reg_id = "test.boom"
    REGISTRY.register(SignalDefinition(id=reg_id, version=1, name="Boom", category="trend", output=CATEGORY,
                                       unit="label", scope="asset", timeframes=("4h",), requires=("candles",),
                                       calculation="-", interpretation="-", limitations="-", compute=boom))
    refs = [SignalRef.make(REGISTRY.get(reg_id), "4h"), SignalRef.make(REGISTRY.get("regime.state"), "4h")]
    out = evaluate(refs, _ctx(_frame()))
    statuses = sorted(r.status for r in out.values())
    assert statuses == ["error", "ok"]


def test_regime_signal_matches_existing_regime_rules():
    import regime
    frame = _frame()
    ref = SignalRef.make(REGISTRY.get("regime.state"), "4h")
    result = evaluate([ref], _ctx(frame))[ref.instance_key]
    expected = regime.regime_series(frame.iloc[:-1].iloc[-120:])["state"].iloc[-1]
    assert result.value == expected == "trending"


def test_catalogue_documents_every_signal():
    for entry in REGISTRY.catalogue():
        for field in ("calculation", "interpretation", "limitations", "unit", "output", "timeframes", "requires"):
            assert entry[field], (entry["id"], field)
        assert entry["evidence_strength"] == "descriptive"


def test_a_future_group_can_be_built_on_refs_alone():
    """Sketch of the Groups layer: refs + weights + roles, scores derived explicitly from native values."""
    group = {
        "name": "Trend confirmation", "version": 1,
        "members": [
            {"ref": SignalRef.make(REGISTRY.get("trend.direction"), "1D").as_dict(), "weight": 1.0, "role": "score",
             "map": {"up": 1, "down": -1, "mixed": 0}},
            {"ref": SignalRef.make(REGISTRY.get("regime.state"), "1D").as_dict(), "weight": 0.0, "role": "context"},
        ],
    }
    text = json.dumps(group)  # storable, shareable, version-pinned
    loaded = json.loads(text)
    refs = [SignalRef(m["ref"]["id"], m["ref"]["version"], m["ref"]["timeframe"],
                      tuple(sorted(m["ref"]["params"].items()))) for m in loaded["members"]]
    out = evaluate(refs, _ctx(_frame(freq="1D", end="2026-11-02")))
    assert all(r.status == OK for r in out.values())
