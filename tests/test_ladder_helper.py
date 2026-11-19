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
