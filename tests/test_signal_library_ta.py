import json

import numpy as np
import pandas as pd
import pytest

from signal_library import REGISTRY, DataContext, SignalRef, evaluate
from signal_library import engine, swings as sw
from signal_library.core import CONFIRMED, INSUFFICIENT, OK
from signal_library.signals_ta import chaikin_money_flow, efficiency_ratio, percentile_rank


def setup_function(_):
    engine.clear_cache()


def _vee(points, length=10):
    """Piecewise-linear path through (index, value) points."""
    xs, ys = zip(*points)
    return np.interp(np.arange(length), xs, ys)


# ----------------------------------------------------------------------------- swing points

def test_pivot_is_found_and_confirmed_right_bars_later():
    high = _vee([(0, 10), (10, 20), (20, 10)], 21)
    low = high - 1
    found = sw.pivots(high, low, 5, 5)
    highs = [p for p in found if p["kind"] == "high"]
    assert highs == [{"kind": "high", "index": 10, "price": 20.0, "confirmed_index": 15}]


def test_unconfirmed_pivot_is_only_a_candidate():
    high = _vee([(0, 10), (10, 20), (13, 18)], 14)  # only 3 bars after the top
    low = high - 1
    assert not [p for p in sw.pivots(high, low, 5, 5) if p["kind"] == "high"]
    cand = sw.candidate(high, low, "high", 5, 5)
    assert cand["index"] == 10 and cand["bars_to_confirm"] == 2


def test_equal_highs_count_once():
    high = np.array([1, 2, 3, 5, 5, 3, 2, 1, 1, 1, 1, 1], dtype=float)
    found = [p for p in sw.pivots(high, high - 1, 2, 2) if p["kind"] == "high"]
    assert [p["index"] for p in found] == [3]


# ----------------------------------------------------------------------------- divergences

def _divergence_case(kind="regular_bullish"):
    n = 70
    if kind == "regular_bullish":
        price = _vee([(0, 100), (20, 90), (30, 97), (40, 85), (55, 95), (69, 96)], n)
        osc = _vee([(0, 50), (20, 20), (30, 45), (40, 30), (55, 55), (69, 55)], n)
    elif kind == "hidden_bullish":
        price = _vee([(0, 100), (20, 85), (30, 97), (40, 90), (55, 99), (69, 100)], n)
        osc = _vee([(0, 50), (20, 30), (30, 50), (40, 20), (55, 55), (69, 55)], n)
    elif kind == "regular_bearish":
        price = _vee([(0, 80), (20, 90), (30, 84), (40, 95), (55, 85), (69, 84)], n)
        osc = _vee([(0, 50), (20, 80), (30, 55), (40, 70), (55, 45), (69, 45)], n)
    else:  # hidden bearish
        price = _vee([(0, 80), (20, 95), (30, 84), (40, 90), (55, 82), (69, 81)], n)
        osc = _vee([(0, 50), (20, 70), (30, 50), (40, 80), (55, 45), (69, 45)], n)
    return price + 0.5, price - 0.5, price, osc


@pytest.mark.parametrize("kind", ["regular_bullish", "hidden_bullish", "regular_bearish", "hidden_bearish"])
def test_each_divergence_type_is_found_at_the_right_swings(kind):
    high, low, close, osc = _divergence_case(kind)
    found = sw.divergences(high, low, close, osc, 5, 5, 5, 60)
    events = [e for e in found["events"] if e["type"] == kind]
    assert len(events) == 1
    e = events[0]
    assert [p["index"] for p in e["price_pivots"]] == [20, 40]
    assert e["confirmed_index"] == 45 and e["delay_bars"] == 5
    assert e["status"] == "confirmed"


def test_divergence_is_invalidated_by_close_beyond_second_swing():
    high, low, close, osc = _divergence_case("regular_bullish")
    close = close.copy()
    close[60] = 80  # closes below the second swing low (84.5)
    found = sw.divergences(high, low, close, osc, 5, 5, 5, 60)
    e = [x for x in found["events"] if x["type"] == "regular_bullish"][0]
    assert e["status"] == "invalidated" and e["invalidated_index"] == 60


def test_developing_divergence_is_separate_until_confirmed():
    high, low, close, osc = _divergence_case("regular_bullish")
    cut = 43  # second low at 40; bars 41 and 42 exist, so 3 more are needed
    found = sw.divergences(high[:cut], low[:cut], close[:cut], osc[:cut], 5, 5, 5, 60)
    assert not [e for e in found["events"] if e["type"] == "regular_bullish"]
    dev = [e for e in found["developing"] if e["type"] == "regular_bullish"]
    assert dev and dev[0]["status"] == "developing" and dev[0]["bars_to_confirm"] == 3


def _walk(n=600, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 + rng.normal(0, 1, n).cumsum()
    high = close + rng.random(n)
    low = close - rng.random(n)
    osc = pd.Series(close).diff().rolling(14).mean().fillna(0).to_numpy() * 10 + 50
    return high, low, close, osc


def test_divergences_do_not_repaint():
    """Every divergence confirmed by bar c is found identically using only data up to bar c."""
    high, low, close, osc = _walk()
    full = sw.divergences(high, low, close, osc)["events"]
    assert len(full) > 5
    for e in full:
        c = e["confirmed_index"]
        part = sw.divergences(high[:c + 1], low[:c + 1], close[:c + 1], osc[:c + 1])["events"]
        same = [x for x in part if x["confirmed_index"] == c and x["type"] == e["type"]]
        assert same and same[0]["price_pivots"] == e["price_pivots"] and same[0]["indicator_pivots"] == e["indicator_pivots"]


def test_structure_breaks_do_not_repaint():
    high, low, close, _ = _walk(seed=11)
    full = sw.structure_breaks(high, low, close)
    assert len(full) > 5
    for cut in (150, 300, 450):
        part = sw.structure_breaks(high[:cut], low[:cut], close[:cut])
        assert part == [e for e in full if e["index"] < cut]


# ----------------------------------------------------------------------------- structure

def test_swing_labels_and_structure_state():
    # Higher highs and higher lows.
    path = _vee([(0, 10), (10, 20), (20, 15), (30, 25), (40, 18), (50, 30), (60, 22), (70, 28)], 71)
    labelled = sw.label_swings(sw.pivots(path + 0.2, path - 0.2, 5, 5))
    assert [p["label"] for p in labelled if p["label"]][-3:] == ["HL", "HH", "HL"]
    assert sw.structure_state(labelled) == "up"


def test_bullish_choch_after_downtrend():
    path = _vee([(0, 50), (10, 40), (20, 46), (30, 35), (40, 42), (50, 30), (60, 44), (70, 50)], 71)
    events = sw.structure_breaks(path + 0.2, path - 0.2, path)
    bull = [e for e in events if e["direction"] == "bullish"]
    assert bull and bull[0]["kind"] == "CHoCH" and bull[0]["structure_before"] == "down"


# ----------------------------------------------------------------------------- zones

def test_zones_cluster_repeated_turns_and_keep_prices():
    # Price bounces off ~90 three times and turns down at ~110 twice, ending near 100.
    path = _vee([(0, 100), (10, 90), (20, 110), (30, 90.4), (40, 109.6), (50, 90.2), (60, 100)], 61)
    out = sw.zones(path + 0.3, path - 0.3, path, atr=2.0, left=5, right=5, width_atr=0.5, min_touches=2)
    support, resistance = out["support"], out["resistance"]
    assert len(support) == 1 and support[0]["touches"] == 3
    assert 89.5 < support[0]["low"] <= support[0]["high"] < 90.5
    assert len(resistance) == 1 and resistance[0]["touches"] == 2
    assert resistance[0]["distance_atr"] == pytest.approx((resistance[0]["low"] - 100) / 2, rel=1e-3)


def test_zone_retest_after_break():
    path = _vee([(0, 100), (10, 110), (20, 100), (30, 110.2), (40, 101), (50, 118), (60, 111), (70, 120)], 71)
    out = sw.zones(path + 0.3, path - 0.3, path, atr=2.0, left=5, right=5, min_touches=2)
    zone = out["support"][0]
    assert zone["broken_direction"] == "up" and zone["retest_index"] is not None


def test_weak_levels_are_dropped():
    path = _vee([(0, 100), (10, 90), (20, 110), (30, 95), (40, 105), (50, 100)], 51)
    out = sw.zones(path + 0.3, path - 0.3, path, atr=1.0, min_touches=2)
    assert out["support"] == [] and out["resistance"] == []


# ----------------------------------------------------------------------------- small formulas

def test_cmf_known_values():
    frame = pd.DataFrame({"high": [10.0] * 20, "low": [0.0] * 20, "close": [10.0] * 20, "volume": [5.0] * 20})
    assert chaikin_money_flow(frame, 20).iloc[-1] == pytest.approx(1.0)
    frame["close"] = 0.0
    assert chaikin_money_flow(frame, 20).iloc[-1] == pytest.approx(-1.0)
    frame["close"] = 5.0
    assert chaikin_money_flow(frame, 20).iloc[-1] == pytest.approx(0.0)


def test_efficiency_ratio_and_percentile():
    assert efficiency_ratio(pd.Series(np.arange(30.0)), 20) == pytest.approx(1.0)
    assert efficiency_ratio(pd.Series([1.0, 2.0] * 15), 20) == pytest.approx(0.0)
    assert percentile_rank(pd.Series(np.arange(100.0)), 100) == pytest.approx(99.0)


# ----------------------------------------------------------------------------- signals end to end

def _frame(freq="4h", n=400, seed=3):
    high, low, close, _ = _walk(n, seed)
    index = pd.date_range(end="2026-11-03 08:00", periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                       "volume": np.random.default_rng(seed).integers(100, 1000, n).astype(float)}, index=index)
    s = df["close"]
    df["sma_50"], df["sma_200"] = s.rolling(50).mean(), s.rolling(200).mean()
    delta = s.diff()
    gain, loss = delta.clip(lower=0).rolling(14).mean(), (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss)
    macd = s.ewm(span=12).mean() - s.ewm(span=26).mean()
    df["MACD_12_26_9"], df["MACDs_12_26_9"] = macd, macd.ewm(span=9).mean()
    df["MACDh_12_26_9"] = macd - df["MACDs_12_26_9"]
    df["adx"] = 22 + 8 * np.sin(np.arange(n) / 30)
    df["atr"] = (df["high"] - df["low"]).rolling(14).mean()
    mid = s.rolling(20).mean()
    df["BBM_20_2.0"], df["BBU_20_2.0"], df["BBL_20_2.0"] = mid, mid + 2 * s.rolling(20).std(), mid - 2 * s.rolling(20).std()
    df["vol_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["vol_sma_20"]
    df["obv"] = (np.sign(s.diff().fillna(0)) * df["volume"]).cumsum()
    df["forming"] = False
    df.iloc[-1, df.columns.get_loc("forming")] = True
    return df


def _ctx(missing=()):
    frames = {tf: _frame(f) for tf, f in (("15m", "15min"), ("1h", "1h"), ("4h", "4h"), ("1D", "1D"), ("1W", "7D"))}

    def loader(kind, asset, tf):
        if tf in missing:
            return {"error": f"no {tf}"}
        return {"frame": frames[tf], "session": None, "source": "test"}
    return DataContext("crypto", "bitcoin", candle_loader=loader)


ALL_TA = ["momentum.direction", "ta.divergence.rsi", "ta.divergence.macd", "structure.swings", "structure.breaks",
          "levels.zones", "regime.observation", "volume.cmf", "volume.relative", "trend.direction", "regime.state"]


@pytest.mark.parametrize("signal_id", ALL_TA)
@pytest.mark.parametrize("tf", ["15m", "4h", "1D"])
def test_every_ta_signal_runs_and_is_json(signal_id, tf):
    ref = SignalRef.make(REGISTRY.get(signal_id), tf)
    result = evaluate([ref], _ctx())[ref.instance_key]
    assert result.status == OK, result.notes
    assert result.confirmation == CONFIRMED and result.available_at and result.provenance
    json.dumps(result.as_dict())


def test_signals_never_use_the_forming_candle():
    ctx = _ctx()
    frame = ctx.candles("4h")["frame"]
    frame.iloc[-1, frame.columns.get_loc("close")] = 1e9  # an absurd forming candle
    for signal_id in ALL_TA:
        ref = SignalRef.make(REGISTRY.get(signal_id), "4h")
        text = json.dumps(evaluate([ref], ctx)[ref.instance_key].as_dict())
        assert "1000000000" not in text, signal_id


def test_mtf_alignment_lists_each_timeframe_and_no_score():
    ref = SignalRef.make(REGISTRY.get("mtf.alignment"), "1D")
    result = evaluate([ref], _ctx(missing=("15m",)))[ref.instance_key]
    assert result.status == OK
    rows = {r["timeframe"]: r for r in result.value["timeframes"]}
    assert rows["15m"]["trend"] is None and rows["15m"]["status"] == "missing_data"
    assert set(rows) == {"15m", "1h", "4h", "1D", "1W"}
    assert "score" not in json.dumps(result.value)
    assert sum(result.value["trend_counts"].values()) == 4


def test_mtf_reuses_component_results():
    ctx = _ctx()
    t_ref = SignalRef.make(REGISTRY.get("trend.direction"), "4h")
    first = evaluate([t_ref], ctx)[t_ref.instance_key]
    evaluate([SignalRef.make(REGISTRY.get("mtf.alignment"), "1D")], ctx)
    assert evaluate([t_ref], ctx)[t_ref.instance_key] is first


def test_insufficient_history_is_reported():
    short = _frame(n=30)
    ctx = DataContext("crypto", "bitcoin", candle_loader=lambda *a: {"frame": short, "session": None, "source": "t"})
    ref = SignalRef.make(REGISTRY.get("levels.zones"), "1D")
    assert evaluate([ref], ctx)[ref.instance_key].status == INSUFFICIENT


def test_zone_signal_keeps_native_prices():
    ref = SignalRef.make(REGISTRY.get("levels.zones"), "4h")
    value = evaluate([ref], _ctx())[ref.instance_key].value
    close = value["close"]
    assert all(z["high"] < close for z in value["support"]) and all(z["low"] > close for z in value["resistance"])
    assert len(value["support"]) <= 3 and len(value["resistance"]) <= 3
