"""Trade Log page (tradelog_view.py) drawn with Streamlit's test runner and sample rows: no errors, and the plan rules."""

from streamlit.testing.v1 import AppTest


def _app(plan, empty=False, setup=False):
    import tradelog_view

    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_a, **_k):
            return self

        def order(self, *_a, **_k):
            return self

        def limit(self, *_a):
            return self

        def eq(self, *_a):
            return self

        def upsert(self, *_a, **_k):
            return self

        def execute(self):
            return Result(self.rows)

    conn = {"id": "c1", "platform": "etoro", "label": "", "status": "ok", "last_sync_at": "2026-11-22T06:00:00Z",
            "last_error": "", "history_from": "2026-01-05", "created_at": "2026-11-22T05:00:00Z"}
    trips = [{"id": i, "user_id": "u", "connection_id": "c1", "platform": "etoro", "name": f"Asset {i % 3}",
              "symbol": "X", "asset_class": "stocks" if i % 2 else "crypto", "direction": "long",
              "opened_at": f"2026-11-{i + 1:02d}T10:00:00Z", "closed_at": f"2026-11-{i + 3:02d}T10:00:00Z",
              "entry_price": 10.0, "exit_price": 11.0, "invested_usd": 100.0, "leverage": 1,
              "net_result_usd": (5.0 if i % 3 else -3.0), "result_pct": 5.0, "copied": i == 4, "fees_usd": 0}
             for i in range(12)]
    snaps = [{"round_trip_id": 1, "moment": "entry", "source": "reconstructed",
              "readings": {"regime": "trending_up", "trend": 40, "stretch": 10, "flow": -5,
                           "fear": {"name": "VIX", "value": 16.2}, "asset_sentiment": {"value": None},
                           "market_sentiment": {"value": 55}}}]
    tables = {"trade_connections": [] if empty else [conn], "trade_round_trips": [] if empty else trips,
              "trade_snapshots": snaps, "trade_notes": []}

    class Db:
        def table(self, name):
            return Query(tables[name])

        def rpc(self, *_a):
            return Query(True)

    import streamlit as st

    (tradelog_view.render_setup if setup else tradelog_view.render)(st, Db(), plan)


def test_page_draws_for_pro_with_trades():
    at = AppTest.from_function(_app, args=("pro",)).run(timeout=30)
    assert not at.exception
    page = "".join(h.proto.body for h in at.get("html"))
    assert "Net result" in page and "tl-tiles" in page and "tl-bars" in page
    assert len(at.tabs) == 2                                       # Overview, eToro
    assert not at.text_input                                       # keys are set up in the sidebar, not here


def test_free_has_no_trade_log_and_empty_shows_the_connect_guide():
    at = AppTest.from_function(_app, args=("free",)).run(timeout=30)
    assert not at.exception and "comes with Plus" in at.info[0].value
    at = AppTest.from_function(_app, args=("plus", True)).run(timeout=30)
    assert not at.exception and not at.markdown and not at.tabs       # nothing in the main page until connected
    at = AppTest.from_function(_app, args=("plus", True, True)).run(timeout=30)
    assert not at.exception and any("Read" in m.value for m in at.markdown)
    assert len(at.text_input) == 3


def test_setup_lists_connections_and_stops_at_the_plan_limit():
    at = AppTest.from_function(_app, args=("plus", False, True)).run(timeout=30)
    assert not at.exception                                       # Plus: one connection, already used
    assert [w.key for w in at.text_input] == ["tl_name_c1"]       # only the tab name to edit, no new key form
    assert any("Disconnect" in b.label for b in at.button)


def _detail_app():
    import streamlit as st
    from zoneinfo import ZoneInfo

    import tradelog_view

    trip = {"id": 1, "user_id": "u", "name": "NVIDIA", "direction": "long", "net_result_usd": 212.0,
            "opened_at": "2026-11-17T08:32:00Z", "closed_at": "2026-11-21T14:04:00Z", "entry_price": 142.1,
            "exit_price": 148.08, "invested_usd": 5040.0, "leverage": 1}
    snaps = {(1, "entry"): {"regime": "trending_up", "trend": 40, "stretch": 10, "flow": -5, "_source": "observed",
                            "fear": {"name": "VIX", "value": 15.8}, "asset_sentiment": {"value": 64},
                            "market_sentiment": {"value": None}},
             (1, "exit"): {"regime": "ranging", "trend": 20, "stretch": 60, "flow": 2, "_source": "reconstructed",
                           "fear": {"name": "VIX", "value": 18.2}, "asset_sentiment": {"value": None},
                           "market_sentiment": {"value": 49}}}
    tradelog_view._detail(st, None, trip, snaps, {}, ZoneInfo("Asia/Bangkok"))


def test_trade_detail_draws_the_snapshot_table():
    at = AppTest.from_function(_detail_app).run(timeout=30)
    assert not at.exception
    page = "".join(h.proto.body for h in at.get("html"))
    assert "Average entry" in page and "tl-snap" in page and "NVIDIA" in page and "tl-up" in page
    assert len(at.text_area) == 1


def test_tab_names_use_the_given_name_else_the_platform_numbered():
    import tradelog_view

    names = tradelog_view.tab_names([{"id": "a", "platform": "etoro", "label": "", "created_at": "1"},
                                     {"id": "b", "platform": "etoro", "label": None, "created_at": "2"},
                                     {"id": "c", "platform": "etoro", "label": "eToro long-term", "created_at": "3"}])
    assert names == {"a": "eToro", "b": "eToro 2", "c": "eToro long-term"}
