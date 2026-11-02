"""Asset alerts follow the signals v2 Trend reading, with their own alert types, so a v1 0-100 score line or
latch can never act on a v2 reading."""

import alerts as al


def rows(**trend):
    return [{"key": k, "symbol": k.upper(), "trend": v} for k, v in trend.items()]


def plan(results, latched=(), level=50):
    return al.plan_alert_actions(results, set(latched), level, -level, describe=al.trend_message, field="trend",
                                 types=(al.TREND_UP, al.TREND_DOWN), rearm=al.TREND_REARM)


def test_trend_crossings_open_trend_alerts():
    actions = plan(rows(btc=62, eth=-70, sol=10))
    opened = {(a[1], a[3]) for a in actions if a[0] == "open"}
    assert opened == {("btc", al.TREND_UP), ("eth", al.TREND_DOWN)}
    message = next(a[4] for a in actions if a[1] == "btc")
    assert "Trend turned up" in message and "+62" in message and "not a forecast" in message


def test_rows_without_a_trend_reading_never_alert_even_with_a_v1_score():
    assert plan([{"key": "btc", "symbol": "BTC", "score": 95}]) == []


def test_rearm_needs_twenty_points_back():
    latched = {("btc", al.TREND_UP)}
    assert plan(rows(btc=35), latched) == []                       # 50 - 15: still latched
    assert ("resolve", "btc", al.TREND_UP) in plan(rows(btc=29), latched)


def test_v1_latches_do_not_block_v2_alerts():
    actions = plan(rows(btc=80), latched={("btc", al.BULLISH)})
    assert ("open", "btc", "BTC", al.TREND_UP) == actions[0][:4]


def test_trend_types_are_latched_hidden_and_mapped():
    assert al.canonical_alert(al.HELD_TREND_UP) == al.TREND_UP
    assert al.stored_types(al.TREND_DOWN) == [al.TREND_DOWN, al.HELD_TREND_DOWN]
    assert set(al.LATCH_TYPES) >= {al.TREND_UP, al.TREND_DOWN, al.HELD_TREND_UP, al.HELD_TREND_DOWN}


def test_evaluate_ignores_old_score_lines_for_assets():
    import inspect

    source = inspect.getsource(al.evaluate_alerts)
    assert 'field="trend"' in source and "min_score_alert" not in source.split("market_high")[0].split("trend_level")[1]


class _DB:
    """Tiny stand-in for the notifications table: filters selects by asset_symbol, records inserts."""

    def __init__(self, rows=()):
        self.rows, self.inserted = list(rows), []

    def table(self, _name):
        db = self

        class Q:
            def __init__(self):
                self.mode, self.symbol = "select", None

            def insert(self, rows):
                db.inserted += rows if isinstance(rows, list) else [rows]
                self.mode = "insert"
                return self

            def update(self, *_a, **_k):
                self.mode = "update"
                return self

            def eq(self, column, value):
                if column == "asset_symbol":
                    self.symbol = value
                return self

            def __getattr__(self, _name):
                return lambda *a, **k: self

            def execute(self):
                data = []
                if self.mode == "select":
                    data = [r for r in db.rows if self.symbol in (None, r["asset_symbol"])]
                return type("R", (), {"data": data})()

        return Q()


def test_first_v2_run_latches_silently_once():
    db = _DB()
    results = [{"key": "Crypto|btc", "symbol": "BTC", "trend": 80}, {"key": "Stock|aapl", "symbol": "AAPL", "trend": -70}]
    opened = al.evaluate_alerts(db, "u", results, {"enabled": True})
    assert opened == []
    held = {r["asset_symbol"]: r for r in db.inserted}
    assert set(held) == {"crypto|btc", "stock|aapl", al.V2_START_SYMBOL}
    for r in held.values():
        assert r["alert_type"] in (al.HELD_TREND_UP, al.HELD_TREND_DOWN)
        assert r["is_read"] and r["emailed_at"] and r["digested_at"]


def test_after_the_start_marker_trend_alerts_open_normally():
    marker = {"asset_symbol": al.V2_START_SYMBOL, "alert_type": al.HELD_TREND_UP}
    db = _DB([marker])
    opened = al.evaluate_alerts(db, "u", [{"key": "Crypto|eth", "symbol": "ETH", "trend": 75}], {"enabled": True})
    assert [o["alert_type"] for o in opened] == [al.TREND_UP]
