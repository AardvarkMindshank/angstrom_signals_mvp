"""Trade Log core (tradelog.py): eToro positions into round trips, and the stats."""

import pytest

import tradelog as tl


def _pos(pid, **kw):
    base = {"positionId": pid, "instrumentId": 1001, "isBuy": True, "leverage": 1, "openRate": 100.0,
            "closeRate": 110.0, "units": 2.0, "initialInvestment": 200.0, "investment": 200.0, "netProfit": 20.0,
            "fees": 0.0, "socialTradeId": 0, "parentPositionId": 0,
            "openTimestamp": "2026-11-01T10:00:00Z", "closeTimestamp": "2026-11-05T10:00:00Z"}
    return {**base, **kw}


INSTRUMENTS = {1001: {"instrumentID": 1001, "instrumentDisplayName": "NVIDIA", "symbolFull": "NVDA",
                      "instrumentTypeID": 5}}
TYPES = {5: "Stocks", 10: "Crypto", 6: "ETF", 2: "Commodities", 1: "Currencies", 4: "Indices"}


def test_a_closed_position_becomes_one_round_trip():
    [t] = tl.etoro_round_trips([_pos(1)], INSTRUMENTS, TYPES, {("stocks", "NVDA"): "equity:NVDA"})
    assert t["name"] == "NVIDIA" and t["symbol"] == "NVDA" and t["asset_class"] == "stocks"
    assert t["asset_key"] == "equity:NVDA" and t["direction"] == "long"
    assert t["net_result_usd"] == 20.0 and t["result_pct"] == 10.0
    assert t["entry_price"] == 100.0 and t["exit_price"] == 110.0 and t["parts"] == 1
    assert t["copied"] is False


def test_partial_closes_merge_into_one_position_with_average_prices():
    parent = _pos(1, units=1.0, closeRate=120.0, netProfit=20.0, initialInvestment=100.0,
                  closeTimestamp="2026-11-07T10:00:00Z")
    part = _pos(2, units=3.0, closeRate=104.0, netProfit=12.0, initialInvestment=300.0, parentPositionId=1)
    [t] = tl.etoro_round_trips([parent, part], INSTRUMENTS, TYPES)
    assert t["parts"] == 2 and t["units"] == 4.0
    assert t["exit_price"] == pytest.approx((120 * 1 + 104 * 3) / 4)
    assert t["net_result_usd"] == 32.0 and t["result_pct"] == 8.0
    assert t["closed_at"].startswith("2026-11-07")


def test_copied_and_short_positions_are_marked():
    [t] = tl.etoro_round_trips([_pos(1, socialTradeId=555, isBuy=False)], INSTRUMENTS, TYPES)
    assert t["copied"] is True and t["direction"] == "short"


def test_unknown_instrument_still_imports():
    [t] = tl.etoro_round_trips([_pos(1, instrumentId=999)])
    assert t["name"] == "Instrument 999" and t["asset_class"] == "other" and t["asset_key"] is None


@pytest.mark.parametrize("text,cls", [("Stocks", "stocks"), ("ETF", "etfs"), ("Crypto", "crypto"),
                                      ("Commodities", "commodities"), ("Currencies", "currencies"),
                                      ("Indices", "indices"), ("", "other")])
def test_asset_classes(text, cls):
    assert tl.asset_class_of(text) == cls


def test_stats_leave_out_copied_trades_and_flag_small_samples():
    trips = tl.etoro_round_trips([
        _pos(1, netProfit=30.0),
        _pos(2, netProfit=-10.0, closeTimestamp="2026-11-11T10:00:00Z"),
        _pos(3, netProfit=50.0, socialTradeId=7),
    ], INSTRUMENTS, TYPES)
    s = tl.stats(trips)
    assert s["trades"] == 2 and s["net"] == 20.0 and s["wins"] == 1 and s["losses"] == 1
    assert s["win_rate"] == 50.0 and s["profit_factor"] == 3.0 and s["enough"] is False
    assert s["avg_hold_win_days"] == 4.0 and s["avg_hold_loss_days"] == 10.0
    assert tl.stats(trips, include_copied=True)["net"] == 70.0


def test_stats_by_group_and_equity_curve():
    trips = [{"closed_at": "2026-11-02", "net_result_usd": 5, "asset_class": "crypto", "opened_at": "2026-11-01"},
             {"closed_at": "2026-11-01", "net_result_usd": -2, "asset_class": "stocks", "opened_at": "2026-10-30"},
             {"closed_at": "2026-11-03", "net_result_usd": 4, "asset_class": "crypto", "opened_at": "2026-11-02"}]
    by = tl.stats_by(trips, "asset_class")
    assert by["crypto"]["net"] == 9 and by["stocks"]["net"] == -2
    assert tl.equity_curve(trips) == [("2026-11-01", -2.0), ("2026-11-02", 3.0), ("2026-11-03", 7.0)]


class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


class _Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, dict(params or {}), dict(headers or {})))
        return self.responses.pop(0)


KEYS = {"api_key": "A", "user_key": "U"}


def test_fetch_pages_until_a_short_page():
    full = [_pos(i) for i in range(tl.PAGE_SIZE)]
    s = _Session([_Resp(200, full), _Resp(200, [_pos(999)])])
    got = tl.fetch_closed_positions(s, KEYS, "2020-01-01")
    assert len(got) == tl.PAGE_SIZE + 1
    assert [c[1]["page"] for c in s.calls] == [1, 2] and s.calls[0][1]["minDate"] == "2020-01-01"
    assert s.calls[0][2]["x-api-key"] == "A" and s.calls[0][2]["x-user-key"] == "U"


def test_refused_key_message_never_contains_the_key():
    s = _Session([_Resp(401, {"message": "bad"})])
    with pytest.raises(tl.EtoroError) as err:
        tl.fetch_closed_positions(s, {"api_key": "SECRET-A", "user_key": "SECRET-U"})
    assert "SECRET" not in str(err.value) and "Read key" in str(err.value)


def test_fetch_instruments_and_types():
    s = _Session([_Resp(200, {"instrumentDisplayDatas": [INSTRUMENTS[1001]]})])
    assert tl.fetch_instruments(s, KEYS, [1001, 1001])[1001]["symbolFull"] == "NVDA"
    assert s.calls[0][1]["instrumentIds"] == "1001"
    s = _Session([_Resp(200, {"instrumentTypes": [{"instrumentTypeID": 5, "instrumentTypeDescription": "Stocks"}]})])
    assert tl.fetch_instrument_types(s, KEYS) == {5: "Stocks"}
