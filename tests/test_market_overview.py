from datetime import datetime, timezone

import market_overview as mo


def test_series_item_change_and_spark():
    item = mo.series_item([100, 102, None, 101], "index")
    assert item["value"] == 101 and abs(item["change"] - (101 / 102 - 1) * 100) < 1e-9
    assert mo.series_item([4.10, 4.15], "yield")["change"] == 4.15 - 4.10
    assert mo.series_item([], "usd") is None


def test_market_open_hours_and_weekends():
    # Thursday 29 Oct 2026, 14:00 UTC = 10:00 New York, 14:00 London, 23:00 Tokyo.
    now = datetime(2026, 10, 29, 14, 0, tzinfo=timezone.utc)
    assert mo.market_open("nyse", now) is True
    assert mo.market_open("lse", now) is True
    assert mo.market_open("tse", now) is False
    assert mo.market_open("nyse", datetime(2026, 10, 31, 15, 0, tzinfo=timezone.utc)) is False  # Saturday
    # Tokyo lunch break: 12:00 Tokyo = 03:00 UTC.
    assert mo.market_open("tse", datetime(2026, 10, 29, 3, 0, tzinfo=timezone.utc)) is False
    assert mo.market_open("nowhere", now) is None


def overview():
    items = {k: {"value": 100.0, "change": 1.0, "spark": [99, 100]} for k, *_ in mo.SPECS}
    items["crypto_cap"] = {"value": 2.4e12, "change": -1.2, "spark": []}
    items["fng"] = {"value": 30, "change": -4, "spark": [34, 30]}
    return {"items": items, "fetched_at": 0}


def test_cards_follow_the_markets_traded():
    stocks_only = [c["key"] for c in mo.card_list(overview(), crypto=False, stocks=True)]
    assert "spx" in stocks_only and "vix" in stocks_only and "btc" not in stocks_only and "fng" not in stocks_only
    crypto_only = [c["key"] for c in mo.card_list(overview(), crypto=True, stocks=False)]
    assert "btc" in crypto_only and "fng" in crypto_only and "spx" not in crypto_only
    assert "vix" in crypto_only and "dxy" in crypto_only and "gold" not in crypto_only
    assert mo.card_list(overview(), crypto=False, stocks=False) == []


def test_html_values_and_vix_colours():
    page = mo.overview_html(overview(), crypto=True, stocks=True)
    assert "S&amp;P 500" in page and "$2.40T" in page and "Fear" in page
    # VIX rising is shown red; an index rising green.
    assert "#b91c1c" in mo.change_pill(2.0, "index", invert=True)
    assert "#15803d" in mo.change_pill(2.0, "index")
    assert "0.05 pt" in mo.change_pill(0.05, "yield")
    assert mo.overview_html(None, True, True) == ""


def test_cards_come_in_groups_in_order():
    keys = [c["key"] for c in mo.card_list(overview(), crypto=True, stocks=True)]
    assert keys[:7] == ["spx", "ndx", "dji", "ftse", "dax", "n225", "hsi"]
    assert keys[7:] == ["us10y", "dxy", "gold", "oil", "btc", "eth", "crypto_cap", "vix", "fng"]
    page = mo.overview_html(overview(), crypto=True, stocks=True)
    assert page.index("Stock markets") < page.index("Rates") < page.index("Commodities") < page.index("Crypto<") < page.index("Sentiment &amp; risk")


def test_daily_history_for_bitcoin_share_and_crypto_cap():
    first = mo.carry_history({"items": {"btc_dom": {"value": 59.0, "change": None, "spark": []},
                                         "crypto_cap": {"value": 2.5e12, "change": -1.0, "spark": []}}}, None, "2026-10-29")
    assert first["history"]["btc_dom"] == {"2026-10-29": 59.0} and first["items"]["btc_dom"]["spark"] == []
    later = mo.carry_history({"items": {"btc_dom": {"value": 59.6, "change": None, "spark": []}}}, first, "2026-10-30")
    item = later["items"]["btc_dom"]
    assert item["spark"] == [59.0, 59.6] and abs(item["change"] - 0.6) < 1e-9
    # Same day again: replaces today's value, keeps the other days.
    again = mo.carry_history({"items": {"btc_dom": {"value": 59.8, "change": None, "spark": []}}}, later, "2026-10-30")
    assert again["history"]["btc_dom"] == {"2026-10-29": 59.0, "2026-10-30": 59.8}
    assert again["history"]["crypto_cap"] == {"2026-10-29": 2.5e12}   # kept even when today's fetch missed it
    assert "0.60 pt" in mo.change_pill(0.6, "pct")
