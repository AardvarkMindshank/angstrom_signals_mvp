import ladder_helper as L


class _St:
    def __init__(self, state):
        self.session_state = state


def test_plan_long_orders_sit_below_with_the_stop_beyond():
    p = L.plan(100, 5, "long", "consolidating", 3)
    prices = [r["price"] for r in p["rows"]]
    assert prices == sorted(prices, reverse=True) and prices[0] < 100
    assert p["stop"] < prices[-1] and abs(sum(r["share"] for r in p["rows"]) - 1) < 1e-9


def test_chart_lines_only_when_switched_on():
    assert L.chart_lines(_St({}), "k", 100, 5) == []
    lines = L.chart_lines(_St({"ladder_show_k": True}), "k", 100, 5)
    assert [x["style"] for x in lines] == ["dashed"] * 3 + ["solid", "dotted"]
    assert lines[3]["label"] == "Stop" and lines[3]["price"] == 95.0


def test_short_trending_lines_go_up_and_thicken():
    st = _St({"ladder_show_k": True, "ladder_side_k": "short", "ladder_style_k": "trending", "ladder_n_k": 4})
    orders = L.chart_lines(st, "k", 100, 5)[:4]
    assert all(x["price"] > 100 for x in orders)
    assert orders[0]["width"] < orders[-1]["width"]


def test_fib_plan_long_orders_on_retracement_levels():
    p = L.fib_plan(110, 2, low=100, high=120, side="long", orders=4)
    assert p["ok"]
    # 50% = 110 is not below the price, so 61.8, 65 and 78.6 are used
    assert [r["fib"] for r in p["rows"]] == [0.618, 0.65, 0.786]
    assert abs(p["rows"][0]["price"] - 107.64) < 1e-9 and abs(p["stop"] - (100 - 0.4)) < 1e-9


def test_fib_plan_short_and_past_levels():
    p = L.fib_plan(101, 2, low=100, high=120, side="short", orders=3)
    assert p["ok"] and all(r["price"] > 101 for r in p["rows"]) and p["stop"] > 120
    assert L.fib_plan(99, 2, low=100, high=120, side="long")["reason"] == "past_levels"


def test_swing_and_drawing_sources():
    import numpy as np
    import pandas as pd

    closes = list(np.linspace(120, 100, 15)) + list(np.linspace(101, 130, 15))
    frame = pd.DataFrame({"high": [c + 1 for c in closes], "low": [c - 1 for c in closes]})
    sw = L.last_swing(frame, "long", swing=3)
    assert sw == {"low": 99.0, "high": 131.0}
    items = [{"tool": "trend", "pts": [{"p": 1}, {"p": 2}]}, {"tool": "fib", "pts": [{"t": 1, "p": 130}, {"t": 2, "p": 100}]}]
    assert L.drawn_fib(items) == {"low": 100.0, "high": 130.0}


def test_fib_lines_carry_the_level():
    st = _St({"ladder_show_k": True, "ladder_place_k": "fib", "ladder_n_k": 3})
    lines = L.chart_lines(st, "k", 125, 2, swing={"low": 100, "high": 130, "origin": "swing"})
    assert lines[0]["label"].endswith("50%") and lines[2]["label"].endswith("78.6%")


def test_market_choice_starts_from_the_regime():
    import ladder_helper as lh

    assert lh.auto_style("trending_up") == "trending" and lh.auto_style("trending_down") == "trending"
    assert lh.auto_style("ranging") == "consolidating" and lh.auto_style("transitional") == "consolidating"
    assert lh.auto_style(None) == "consolidating"

    class St:
        session_state = {}

    st = St()
    lh.note_regime(st, "Crypto_bitcoin", {"label": "trending_up"})
    assert lh.settings(st, "Crypto_bitcoin", 100.0, 5.0)["style"] == "trending"
    st.session_state["ladder_style_Crypto_bitcoin"] = "consolidating"          # the member's own choice wins
    assert lh.settings(st, "Crypto_bitcoin", 100.0, 5.0)["style"] == "consolidating"
