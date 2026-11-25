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


def test_fetch_reads_past_short_pages_until_an_empty_one():
    short = [_pos(i) for i in range(98)]                 # eToro's first page can be short with more to come
    s = _Session([_Resp(200, short), _Resp(200, [_pos(999)]), _Resp(200, [])])
    got = tl.fetch_closed_positions(s, KEYS, "2020-01-01")
    assert len(got) == 99
    assert [c[1]["page"] for c in s.calls] == [1, 2, 3] and s.calls[0][1]["minDate"] == "2020-01-01"
    assert s.calls[0][2]["x-api-key"] == "A" and s.calls[0][2]["x-user-key"] == "U"


def test_fetch_stops_when_a_page_repeats():
    page = [_pos(i) for i in range(5)]
    s = _Session([_Resp(200, page), _Resp(200, page)])
    assert len(tl.fetch_closed_positions(s, KEYS)) == 5 and len(s.calls) == 2


def test_fetch_stops_at_pages_older_than_stop_before():
    new = [_pos(i, closeTimestamp="2026-11-20T00:00:00Z") for i in range(3)]
    old = [_pos(10 + i, closeTimestamp="2026-10-01T00:00:00Z") for i in range(3)]
    s = _Session([_Resp(200, new), _Resp(200, old), _Resp(200, [_pos(99)])])
    assert len(tl.fetch_closed_positions(s, KEYS, stop_before="2026-11-01")) == 6 and len(s.calls) == 2


def test_fetch_side_by_side_reads_every_page():
    class Paged:
        def get(self, url, headers=None, params=None, timeout=None):
            n = params["page"]
            return _Resp(200, [_pos(n * 1000 + i) for i in range(98 if n == 1 else 100)] if n <= 7 else [])
    got = tl.fetch_closed_positions(Paged(), KEYS, workers=4)
    assert len(got) == 98 + 6 * 100 and len({p["positionId"] for p in got}) == len(got)


def test_fetch_asks_again_after_a_504(monkeypatch):
    monkeypatch.setattr(tl.time, "sleep", lambda s: None)
    s = _Session([_Resp(504, {}), _Resp(200, [_pos(1)]), _Resp(200, [])])
    assert len(tl.fetch_closed_positions(s, KEYS)) == 1


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


def _trip(day, net, hold_days, size=100.0, cls="stocks"):
    from datetime import datetime, timedelta, timezone
    o = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day * 10)
    return {"opened_at": o.isoformat(), "closed_at": (o + timedelta(days=hold_days)).isoformat(),
            "net_result_usd": net, "invested_usd": size, "asset_class": cls}


def test_patterns_need_enough_trades():
    assert tl.patterns([_trip(i, 5, 1) for i in range(9)]) == []


def test_holding_losers_longer_and_sizing_up_after_losses():
    trips = []
    for i in range(14):
        lose = i % 2 == 1
        trips.append(_trip(i, -5 if lose else 8, 6 if lose else 2, size=200 if i % 2 == 0 and i else 100))
    kinds = {p["kind"]: p for p in tl.patterns(trips)}
    assert kinds["hold_losers"]["times"] == 3.0 and kinds["hold_losers"]["trades"] == 14
    assert kinds["size_after_loss"]["times"] == 2.0


def test_asset_class_gap_only_with_ten_trades_each():
    trips = [_trip(i, 10, 1, cls="crypto") for i in range(10)] + [_trip(20 + i, -4, 1) for i in range(10)]
    gap = [p for p in tl.patterns(trips) if p["kind"] == "class_gap"]
    assert gap and gap[0]["better"] == "crypto" and gap[0]["worse"] == "stocks" and gap[0]["trades"] == 20
    assert not [p for p in tl.patterns(trips[:15]) if p["kind"] == "class_gap"]


def test_invested_by_day_rises_and_falls_with_open_trades():
    trips = [
        {"opened_at": "2026-01-01T10:00:00Z", "closed_at": "2026-01-03T10:00:00Z", "invested_usd": 100.0,
         "net_result_usd": 10.0},
        {"opened_at": "2026-01-02T10:00:00Z", "closed_at": "2026-01-04T10:00:00Z", "invested_usd": 50.0,
         "net_result_usd": -5.0},
        {"opened_at": "2026-01-02T10:00:00Z", "closed_at": "2026-01-02T12:00:00Z", "invested_usd": 999.0,
         "net_result_usd": 1.0, "copied": True},
    ]
    assert tl.invested_by_day(trips) == [("2026-01-01", 100.0, 0.0), ("2026-01-02", 150.0, 0.0),
                                         ("2026-01-03", 50.0, 10.0), ("2026-01-04", 0.0, 5.0)]
    assert tl.invested_by_day(trips, include_copied=True)[1] == ("2026-01-02", 150.0, 1.0)


def test_portfolio_open_positions_and_copied_funds():
    body = {"clientPortfolio": {"credit": 120.5, "unrealizedPnL": -40.0, "positions": [
        {"positionID": 1, "instrumentID": 1001, "isBuy": True, "amount": 500.0, "openRate": 10.0, "units": 50,
         "leverage": 1, "mirrorID": 0, "openDateTime": "2026-03-01T00:00:00Z",
         "unrealizedPnL": {"pnL": -50.0, "closeRate": 9.0}}],
        "mirrors": [{"mirrorID": 7, "positions": [{"positionID": 2, "instrumentID": 1001, "isBuy": False,
                                                   "amount": 20.0, "mirrorID": 7, "unrealizedPnL": {"pnL": 10.0}}]}]}}
    s = _Session([_Resp(200, body)])
    got = tl.fetch_portfolio(s, KEYS)
    assert got["cash"] == 120.5 and got["pnl"] == -40.0 and len(got["positions"]) == 2
    rows = tl.etoro_open_positions(got["positions"], {1001: {"symbolFull": "NVDA", "instrumentDisplayName": "NVIDIA",
                                                             "instrumentTypeID": 5}}, {5: "Stocks"})
    first = rows[0]
    assert first["value_usd"] == 450.0 and first["pnl_usd"] == -50.0 and first["current_price"] == 9.0
    assert first["name"] == "NVIDIA" and not first["copied"] and rows[1]["copied"] and rows[1]["direction"] == "short"


def test_invested_by_day_keeps_open_trades_to_today():
    from datetime import datetime, timezone
    opened = [{"opened_at": "2026-01-02T00:00:00Z", "invested_usd": 30.0}]
    trips = [{"opened_at": "2026-01-01T10:00:00Z", "closed_at": "2026-01-03T10:00:00Z", "invested_usd": 100.0,
              "net_result_usd": 10.0}]
    days = tl.invested_by_day(trips, open_positions=opened)
    assert days[1] == ("2026-01-02", 130.0, 0.0) and days[2] == ("2026-01-03", 30.0, 10.0)
    assert days[-1][0] == datetime.now(timezone.utc).date().isoformat() and days[-1][1] == 30.0
