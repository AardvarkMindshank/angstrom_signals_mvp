"""Trade Log insights (tradelog_insights.py): each part worked out from a few hand-made trades."""
from datetime import date

import tradelog
import tradelog_insights as ti


def _t(i, net, cls="crypto", copied=False, opened="2026-01-05T10:00:00Z", closed="2026-01-20T10:00:00Z", **kw):
    return {"id": i, "connection_id": "c", "name": f"A{i % 3}", "asset_class": cls, "direction": "long",
            "opened_at": opened, "closed_at": closed, "invested_usd": 100.0, "leverage": 1, "net_result_usd": net,
            "copied": copied, "fees_usd": 0, **kw}


def test_account_compounds_daily_gain_and_finds_the_deepest_fall():
    gains = [["2026-01-%02d" % d, 0.10] for d in range(1, 11)] + [["2026-01-%02d" % d, -0.05] for d in range(11, 31)]
    bench = {"btc": [["2025-12-29", 100.0], ["2026-01-26", 150.0]]}
    a = ti.account(gains, bench, None)
    level = 1.1 ** 10 * 0.95 ** 20
    assert a["total_pct"] == round((level - 1) * 100, 1)
    assert a["deepest"]["pct"] == round((0.95 ** 20 - 1) * 100, 1) and a["deepest"]["from"] == "2026-01-10"
    assert a["bench"]["btc"]["total"] == 50.0
    assert a["months"]["2026-01"] == a["total_pct"]


def test_closed_stats_compare_and_whose():
    trips = [_t(1, 50), _t(2, -20), _t(3, 10, copied=True), _t(4, -40, copied=True)]
    doc = ti.build(trips, {}, [], [], {}, {}, "own", "all", date(2026, 11, 26))
    assert doc["closed"]["trades"] == 2 and doc["closed"]["net"] == 30.0 and doc["closed"]["win_rate"] == 50.0
    assert doc["compare"]["copied"]["net"] == -30.0
    assert doc["account"] is None and doc["open"] is None


def test_period_keeps_trades_closed_inside_it():
    trips = [_t(1, 50, closed="2026-06-01T00:00:00Z"), _t(2, -20, closed="2020-06-01T00:00:00Z")]
    doc = ti.build(trips, {}, [], [], {}, {}, "all", "1y", date(2026, 11, 26))
    assert doc["closed"]["trades"] == 1


def test_edge_ignores_a_box_holding_nearly_every_trade():
    trips = [_t(i, 10) for i in range(20)] + [_t(100 + i, -30, cls="stocks") for i in range(6)]
    e = ti.edge(trips, {})
    assert e["leak"]["label"] == "stocks" and e["edge"]["label"] == "crypto"
    longs = [_t(i, 5) for i in range(30)] + [dict(_t(50 + i, -1), direction="short") for i in range(2)]
    assert ti.edge(longs, {})["edge"] is None or ti.edge(longs, {})["edge"]["label"] != "long"


def test_market_state_takes_direction_from_trend():
    assert ti.market_state({"regime": "trending", "trend": 40}) == "up"
    assert ti.market_state({"regime": "trending", "trend": -10}) == "down"
    assert ti.market_state({"regime": "ranging", "trend": 40}) == "side"
    assert ti.market_state({}) is None


def test_exit_facts_real_stop_r_and_ending():
    first = {"openRate": 100.0, "isBuy": True, "leverage": 1}
    hit = tradelog.exit_facts(first, {"closeRate": 90.1, "stopLossRate": 90.0, "takeProfitRate": 0}, 1000.0, -99.0)
    assert hit["exit_kind"] == "stop_loss" and hit["risk_r"] == round(-99.0 / 100.0, 2)
    default = tradelog.exit_facts(first, {"closeRate": 120.0, "stopLossRate": 0, "takeProfitRate": 1000.0}, 1000.0, 200.0)
    assert default["exit_kind"] == "by_hand" and default["risk_r"] is None and default["stop_loss"] is None
    target = tradelog.exit_facts(first, {"closeRate": 130.0, "stopLossRate": 0, "takeProfitRate": 130.0}, 1000.0, 300.0)
    assert target["exit_kind"] == "take_profit"


def test_trade_moves_kept_and_after():
    candles = [["2026-01-%02d" % d, 0, 100 + d, 100, 100 + d] for d in range(1, 31)] + \
              [["2026-02-%02d" % d, 0, 140, 120, 140.0] for d in range(1, 26)]
    trip = {"opened_at": "2026-01-01T00:00:00Z", "closed_at": "2026-01-11T00:00:00Z", "direction": "long",
            "entry_price": 100.0, "exit_price": 105.5, "net_result_usd": 5.5}
    m = tradelog.trade_moves(trip, candles)
    assert m["kept_pct"] == 50.0                     # best high 111 → kept 5.5 of 11
    assert m["after20_pct"] == round((140 / 105.5 - 1) * 100, 2)   # the 20th trading day after: 1 Feb


def test_habits_need_enough_own_trades():
    assert ti.habits([_t(i, 1) for i in range(5)]) == []


def test_open_now_groups_by_asset_and_adds_cash():
    opened = [{"name": "Bitcoin", "invested_usd": 100, "value_usd": 80, "copied": False, "asset_key": "k",
               "stop_loss": 70, "current_price": 100, "direction": "long", "overnight_fees_usd": 2},
              {"name": "Bitcoin", "invested_usd": 50, "value_usd": 60, "copied": False, "asset_key": "k",
               "stop_loss": None, "current_price": 100, "direction": "long"}]
    o = ti.open_now(opened, [{"cash_usd": 10, "portfolio_at": "2026-11-26T00:00:00Z"}], {"k": {"regime": "ranging"}})
    assert o["account"] == 150.0 and o["pnl"] == -10.0 and o["rows"][0]["positions"] == 2
    assert o["rows"][0]["stop_pct"] is None and o["rows"][0]["stops_set"] == 1 and o["rows"][0]["now"] == "side"


def test_staking_rewards_are_not_trades():
    first = {"openTimestamp": "2026-06-08T08:54:18Z", "isBuy": True, "leverage": 1, "socialTradeId": 0}
    assert tradelog.is_reward(first, "ADA", "crypto", 2.34)
    assert not tradelog.is_reward(first, "ADA", "crypto", 400.0)                 # a real buy
    assert not tradelog.is_reward(dict(first, openTimestamp="2026-06-20T08:00:00Z"), "ADA", "crypto", 2.0)
    assert not tradelog.is_reward(first, "MANA", "crypto", 24.99)
    trips = [_t(1, 50), _t(2, -1, reward=True)]
    doc = ti.build(trips, {}, [], [], {}, {}, "own", "all", date(2026, 11, 26))
    assert doc["closed"]["trades"] == 1 and doc["rewards"]["count"] == 1
