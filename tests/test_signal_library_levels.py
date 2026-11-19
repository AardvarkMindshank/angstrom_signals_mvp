"""Price levels made by trading (signal_library/signals_levels.py): fair value gaps, anchored VWAP, volume profile."""

import numpy as np
import pandas as pd

from signal_library import DataContext, REGISTRY, SignalRef, engine, evaluate
from signal_library.core import OK
from signal_library.signals_levels import gap_history, profile


def _frame(rows, volume=None, freq="1D"):
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], dtype=float)
    df["volume"] = volume if volume is not None else 100.0
    df.index = pd.date_range("2024-01-01", periods=len(df), freq=freq, tz="UTC")
    df["forming"] = False
    df.loc[df.index[-1], "forming"] = True                      # the newest candle is forming: ignored
    return df


def _run(sid, frame, **params):
    engine.clear_cache()
    ctx = DataContext("crypto", "bitcoin", candle_loader=lambda *a: {"frame": frame, "session": None, "source": "t"})
    ref = SignalRef.make(REGISTRY.get(sid, 1), "1D", **params)
    return evaluate([ref], ctx)[ref.instance_key]


def _flat(n, price=100.0):
    return [(price, price + 1, price - 1, price)] * n


def test_gap_forms_shrinks_tests_and_fills():
    high = np.array([101, 103, 108, 109, 107, 105, 99.0])
    low = np.array([99, 101, 104, 106, 103, 100.5, 97.0])
    close = np.array([100, 102, 107, 108, 106, 104, 98.0])
    h = gap_history(high, low, close, 0.1, start=2)
    # up gaps 101..104 (candle 2) and 103..106 (candle 3); candle 4 dips to 103: tests the first (closes above it),
    # fills the second; candle 5 dips to 100.5 and fills the first
    assert h["last"]["new_up"] == 3 and h["last"]["test_up"] == 4 and h["last"]["filled_up"] == 5
    assert [g for g in h["open"] if g["up"]] == [] and h["last"]["new_down"] == 6   # the drop leaves down gaps


def test_fvg_signal_reports_an_open_gap_below():
    rows = _flat(40) + [(100, 101, 99.5, 100.5), (101, 106, 100.8, 105.5), (106, 110, 103, 109)] + \
        [(109, 111, 107, 110)] * 5 + _flat(1, 110)
    r = _run("level.fvg", _frame(rows), lookback=30)
    assert r.status == OK
    v = r.value
    # two up gaps (101..103 and 106..107); the nearest is 106..107, 4 closed candles ago
    assert v["below_count"] == 2 and v["nearest_below_bottom"] == 106 and v["nearest_below_top"] == 107
    assert abs(v["nearest_below_distance_pct"] - 2.727273) < 1e-6 and v["above_count"] == 0 and v["new_up_ago"] == 4
    assert v["test_up_ago"] == 30 and v["nearest_above_top"] is None


def test_anchored_vwap_from_the_last_swing_low():
    closes = list(np.linspace(120, 100, 20)) + list(np.linspace(101, 115, 15))
    rows = [(c, c + 1, c - 1, c) for c in closes] + [(115, 116, 114, 115)]
    r = _run("level.avwap", _frame(rows), anchor="swing_low", swing=3)
    assert r.status == OK
    v = r.value
    assert v["anchor_price"] == 99 and v["position"] == "above" and 100 < v["vwap"] < 115
    assert v["anchor_ago"] == 15


def test_anchored_vwap_month_start_and_weights():
    rows = _flat(45)
    vol = np.full(45, 100.0)
    r = _run("level.avwap", _frame(rows, vol), anchor="month")
    assert r.status == OK and r.value["vwap"] == 100 and r.value["position"] == "on"


def test_volume_profile_busiest_price_and_value_area():
    vp = profile(np.array([101, 101, 101, 111.0]), np.array([99, 99, 99, 109.0]), np.array([100, 100, 100, 10.0]),
                 24, 0.7)
    assert 99 <= vp["poc"] <= 101 and vp["value_high"] <= 102
    rows = _flat(50) + [(100, 112, 99, 111)] + _flat(1, 111)
    r = _run("level.volume_profile", _frame(rows), lookback=30)
    assert r.status == OK and r.value["position"] == "above_value" and r.value["poc_side"] == "above"


def test_new_signals_are_offered_with_settings():
    import lattice_editor as le
    import plans
    import signal_families
    from signal_library import fields

    by_id = {s["id"]: s for s in le.catalogue()}
    for sid in ("level.fvg", "level.avwap", "level.volume_profile"):
        assert sid in by_id and by_id[sid]["params"], sid
        assert sid in signal_families.all_ids() and sid in plans.SIGNAL_PLAN and f"{sid}@1" in fields.FIELDS
    assert by_id["level.avwap"]["params"]["anchor"]["choices"] == ["swing_low", "swing_high", "week", "month", "year"]
