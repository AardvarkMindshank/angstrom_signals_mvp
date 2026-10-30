from datetime import date

import options_levels as ol

TODAY = date(2026, 10, 30)
EXPIRY = date(2026, 11, 20)


def line(kind, strike, oi, iv=0.5, volume=0.0):
    return {"type": kind, "strike": strike, "oi": oi, "iv": iv, "volume": volume, "expiry": EXPIRY}


def test_gamma_peaks_at_the_money_and_is_zero_for_bad_inputs():
    atm = ol.bs_gamma(100, 100, 0.4, 0.1)
    assert atm > ol.bs_gamma(100, 130, 0.4, 0.1) > 0
    assert ol.bs_gamma(100, 100, 0, 0.1) == 0 and ol.bs_gamma(0, 100, 0.4, 0.1) == 0


def test_expiries_skip_today_and_far_dates():
    dates = ["2026-10-30", "2026-11-06", "2026-11-13", "2026-11-20", "2026-12-18", "2027-03-19"]
    assert ol.pick_expiries(dates, TODAY) == ["2026-11-06", "2026-11-13", "2026-11-20"]
    assert ol.pick_expiries(["2027-06-18"], TODAY) == []


def test_walls_ratios_and_gex_sign():
    rows = [
        line("call", 110, 5000, volume=300), line("call", 100, 1000, volume=100),
        line("put", 90, 4000, volume=200), line("put", 100, 500, volume=100),
        line("call", 200, 99999),  # far away: not a wall
    ]
    result = ol.summarize(rows, 100.0, TODAY)
    assert result["ok"] and result["call_wall"] == 110 and result["put_wall"] == 90
    assert abs(result["pcr_oi"] - 4500 / 105999) < 1e-9
    assert abs(result["pcr_volume"] - 300 / 400) < 1e-9
    by = {s["strike"]: s for s in result["strikes"]}
    assert by[110]["gex"] > 0 and by[90]["gex"] < 0
    assert 200 not in by


def test_gamma_flip_found_between_put_and_call_heavy_strikes():
    rows = [line("put", 95, 20000), line("call", 105, 20000)]
    flip = ol.gamma_flip(rows, 100.0, TODAY)
    assert flip is not None and 95 < flip < 105


def test_nothing_to_show_without_rows_or_price():
    assert ol.summarize([], 100.0, TODAY) == {"ok": False}
    assert ol.summarize([line("call", 100, 10)], 0, TODAY) == {"ok": False}
