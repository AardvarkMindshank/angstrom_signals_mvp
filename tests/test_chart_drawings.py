"""✏️ Chart drawings: one record per account and asset, shared by every candle size."""

from pathlib import Path

import market_store as ms

ROOT = Path(__file__).resolve().parents[1]


def test_drawing_key_is_per_asset():
    assert ms.drawing_key("Crypto", "Bitcoin") == "crypto:bitcoin"
    assert ms.drawing_key("Stock", "aapl") == "equity:AAPL"
    assert ms.drawing_key("crypto", " ethereum ") == "crypto:ethereum"


def test_every_tool_has_a_tip_and_the_chart_calls_the_layer_safely():
    draw = (ROOT / "lw_draw.js").read_text(encoding="utf-8")
    chart = (ROOT / "lw_chart.js").read_text(encoding="utf-8")
    for tool in ("pen", "hl", "erase", "trend", "ray", "hline", "vline", "channel", "arrow", "box", "circle",
                 "marker", "text", "fib", "measure", "position"):
        assert f'["{tool}",' in draw
    assert "try { setupDrawing(" in chart and "try { refreshDrawing(" in chart     # Prism's chart has no layer


def test_sql_keeps_drawings_private_and_shares_to_members_only():
    sql = (ROOT / "sql" / "2026-11-27_chart_drawings.sql").read_text(encoding="utf-8")
    assert "using (auth.uid() = user_id)" in sql
    assert "choose a community you belong to" in sql and "where people.person <> me" in sql
