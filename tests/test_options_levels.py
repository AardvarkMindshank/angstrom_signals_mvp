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


class _Frame:
    def __init__(self, data):
        self._data = data
        self.columns = list(data)
        self.empty = not data or not len(next(iter(data.values())))

    def __getitem__(self, name):
        return self._data[name]

    def __len__(self):
        return len(next(iter(self._data.values()))) if self._data else 0


class _Chain:
    def __init__(self, calls, puts):
        self.calls, self.puts = _Frame(calls), _Frame(puts)


def test_chain_lines_keep_only_open_contracts_and_survive_missing_columns():
    found = _Chain(
        {"strike": [100.0, 110.0], "openInterest": [50, 0], "impliedVolatility": [0.4, 0.5]},
        {"strike": [90.0], "openInterest": [float("nan")]},
    )
    lines = ol.chain_lines(found)
    assert lines == [{"type": "call", "strike": 100.0, "oi": 50.0, "iv": 0.4, "volume": 0.0}]


def test_short_interest_reads_yahoo_fields():
    info = {"sharesShort": 80_000_000, "sharesShortPriorMonth": 100_000_000, "shortPercentOfFloat": 0.031,
            "shortRatio": 0.9, "dateShortInterest": 1760486400}
    si = ol.short_interest_from_info(info)
    assert si["pct_float"] == 0.031 and si["days_to_cover"] == 0.9
    assert abs(si["change"] + 0.2) < 1e-9 and si["as_of"].year == 2025
    assert ol.short_interest_from_info({}) == {} and ol.short_interest_from_info(None) == {}


def test_blank_chain_falls_back_to_last_good(monkeypatch):
    import sys, types
    good = _Chain({"strike": [100.0], "openInterest": [500], "impliedVolatility": [0.4]}, {})
    blank = _Chain({"strike": [100.0], "openInterest": [0]}, {})
    state = {"chain": good}

    class Ticker:
        def __init__(self, _):
            self.options = ["2026-11-06"]

        def option_chain(self, _):
            return state["chain"]

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    ol._cache.clear(); ol._last_good.clear()
    rows, _, error = ol.load_rows("ZZZ", TODAY)
    assert rows and error is None and ol.last_stale_from() is None
    ol._cache.clear()
    state["chain"] = blank
    rows, _, error = ol.load_rows("ZZZ", TODAY)
    assert rows and error is None and ol.last_stale_from() is not None
    ol._cache.clear(); ol._last_good.clear()
    rows, _, error = ol.load_rows("ZZZ", TODAY)
    assert not rows and "no open contracts" in error


def test_half_blank_chain_uses_last_good_and_thin_chain_is_refused(monkeypatch):
    import sys, types
    good = _Chain({"strike": [100.0], "openInterest": [5000], "impliedVolatility": [0.4]}, {})
    thin = _Chain({"strike": [60.0], "openInterest": [150], "impliedVolatility": [0.4]}, {})
    state = {"chain": good}

    class Ticker:
        def __init__(self, _):
            self.options = ["2026-11-06"]

        def option_chain(self, _):
            return state["chain"]

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    ol._cache.clear(); ol._last_good.clear()
    ol.load_rows("YYY", TODAY)
    ol._cache.clear()
    state["chain"] = thin
    rows, _, error = ol.load_rows("YYY", TODAY)
    assert error is None and rows[0]["oi"] == 5000 and ol.last_stale_from()
    ol._cache.clear(); ol._last_good.clear()
    rows, _, error = ol.load_rows("YYY", TODAY)
    assert not rows and "handful" in error
