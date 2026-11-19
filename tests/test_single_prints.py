import pandas as pd

import single_prints as sp


def _day(start, rows):
    idx = pd.date_range(start, periods=len(rows), freq="30min", tz="UTC")
    return pd.DataFrame([{"open": o, "high": h, "low": lo, "close": c} for o, h, lo, c in rows], index=idx)


def _rising_day(start):
    # 6 candles chop around 100, one fast candle runs 101 -> 110, then 6 candles chop around 110: 101..109 is thin
    slow = [(100, 101, 99, 100.5)] * 6
    fast = [(101, 110.5, 100.8, 110)]
    top = [(110, 111, 109.5, 110.5)] * 6
    return _day(start, slow + fast + top)


def test_a_fast_move_inside_the_day_leaves_one_zone():
    found = sp.day_zones(_rising_day("2026-11-10"))
    assert len(found) == 1
    z = found[0]
    assert 101 <= z["bottom"] < 102 and 108 < z["top"] <= 109.5 and z["up"]


def test_tails_and_short_days_are_left_out():
    assert sp.day_zones(_rising_day("2026-11-10").iloc[:5]) == []
    spike = _day("2026-11-10", [(100, 101, 99, 100)] * 10 + [(100, 120, 99.5, 100)])
    assert sp.day_zones(spike) == []          # the spike's top is the day's high: a tail, not a single print


def test_later_trading_shrinks_then_fills():
    day = _rising_day("2026-11-10")
    later = _day("2026-11-11", [(110, 110.5, 105, 106)])
    both = pd.concat([day, later])
    z = sp.zones(both)
    assert len(z) == 1 and z[0]["top"] == 105
    filled = pd.concat([both, _day("2026-11-12", [(106, 106.5, 100, 101)])])
    assert sp.zones(filled) == []


def test_payload_maps_to_chart_candles():
    day = _rising_day("2026-11-10")
    frame = pd.date_range("2026-11-10", periods=4, freq="4h", tz="UTC")
    out = sp.payload(sp.zones(day), frame)
    assert out and out[0]["from"] == 0
