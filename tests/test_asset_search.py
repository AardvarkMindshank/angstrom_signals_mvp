"""Asset search answers are read correctly, whatever else is in them."""
import data_fetchers as df


def test_crypto_matches_largest_first_and_skip_junk():
    payload = {"coins": [
        {"id": "stellar-classic", "name": "Stellar Classic", "symbol": "xlmc", "market_cap_rank": None},
        {"id": "stellar", "name": "Stellar", "symbol": "xlm", "market_cap_rank": 24},
        {"name": "No id"},
        "junk",
    ]}
    found = df.parse_crypto_matches(payload)
    assert [item["id"] for item in found] == ["stellar", "stellar-classic"]
    assert found[0]["symbol"] == "XLM" and found[0]["rank"] == 24
    assert df.parse_crypto_matches(None) == [] and df.parse_crypto_matches({"coins": None}) == []


def test_yahoo_matches_keep_stocks_and_etfs_only():
    payload = {"quotes": [
        {"symbol": "sie.de", "shortname": "SIEMENS AG NA O.N.", "quoteType": "EQUITY", "exchDisp": "XETRA"},
        {"symbol": "SPY", "shortname": "SPDR S&P 500", "quoteType": "ETF", "exchDisp": "NYSEArca"},
        {"symbol": "BTC-USD", "shortname": "Bitcoin USD", "quoteType": "CRYPTOCURRENCY"},
        {"symbol": "", "quoteType": "EQUITY"},
    ]}
    found = df.parse_yahoo_matches(payload)
    assert [item["symbol"] for item in found] == ["SIE.DE", "SPY"]
    assert found[0]["exchange"] == "XETRA" and found[1]["type"] == "ETF"
    assert df.parse_yahoo_matches({}) == []


def test_finnhub_matches_filter_by_type():
    payload = {"result": [
        {"symbol": "AAPL", "description": "APPLE INC", "type": "Common Stock"},
        {"symbol": "AAPL.SW", "description": "APPLE INC", "type": "Common Stock"},
        {"symbol": "XYZ", "description": "A WARRANT", "type": "Warrant"},
    ]}
    found = df.parse_finnhub_matches(payload)
    assert [item["symbol"] for item in found] == ["AAPL", "AAPL.SW"]
    assert found[0]["name"] == "Apple Inc"


def test_short_queries_search_nothing(monkeypatch=None):
    assert df.search_crypto_matches("x") == []
    assert df.search_stock_matches("") == []


def test_crypto_stats_read_cap_and_rank():
    payload = [
        {"id": "Stellar", "market_cap": 3.1e9, "market_cap_rank": 24},
        {"id": "newcoin", "market_cap": None, "market_cap_rank": None},
        {"id": "ranked-only", "market_cap": 0, "market_cap_rank": 800},
        {"id": "bad", "market_cap": "x", "market_cap_rank": True},
        "junk",
    ]
    found = df.parse_crypto_stats(payload)
    assert found["stellar"] == {"cap": 3.1e9, "rank": 24}
    assert found["ranked-only"] == {"cap": None, "rank": 800}
    assert "newcoin" not in found and "bad" not in found
    assert df.parse_crypto_stats(None) == {}


def test_saved_stats_come_back_and_old_ones_do_not():
    import market_store as ms
    from datetime import datetime, timedelta, timezone
    fresh = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
    rows = {
        "crypto:stellar": {"asset_key": "crypto:stellar", "kind": "Crypto", "asset_id": "stellar",
                           "market_cap": 3e9, "market_rank": 24, "market_stats_updated_at": fresh},
        "crypto:oldcoin": {"asset_key": "crypto:oldcoin", "kind": "Crypto", "asset_id": "oldcoin",
                           "market_cap": 1e9, "market_rank": 90, "market_stats_updated_at": old},
        "stock:aapl": {"asset_key": "stock:aapl", "kind": "Stock", "asset_id": "AAPL",
                       "market_cap": 3e12, "market_rank": None, "market_stats_updated_at": fresh},
        "crypto:empty": {"asset_key": "crypto:empty", "kind": "Crypto", "asset_id": "empty"},
    }
    got = ms.market_stats_from_rows(rows)
    assert got["crypto"] == {"stellar": {"cap": 3e9, "rank": 24}}
    assert got["stock"]["AAPL"]["cap"] == 3e12 and got["stock"]["AAPL"]["rank"] is None


def test_earnings_picks_the_next_future_date():
    from datetime import date
    today = date(2026, 10, 28)
    payload = {"earningsCalendar": [
        {"date": "2026-08-01", "symbol": "AAPL"},
        {"date": "2026-11-12", "symbol": "AAPL"},
        {"date": "2026-10-30", "symbol": "AAPL"},
        {"symbol": "AAPL"},
    ]}
    assert df.parse_finnhub_earnings(payload, today) == "2026-10-30"
    assert df.parse_finnhub_earnings({"earningsCalendar": []}, today) is None
    assert df.parse_finnhub_earnings(None, today) is None
    assert df.earliest_upcoming(["2026-10-28", "junk", None], today) == "2026-10-28"


def test_saved_earnings_come_back_with_none_meaning_checked():
    import market_store as ms
    from datetime import datetime, timedelta, timezone
    fresh = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    rows = {
        "stock:aapl": {"kind": "Stock", "asset_id": "AAPL", "next_earnings": "2026-10-30", "earnings_checked_at": fresh},
        "stock:spy": {"kind": "Stock", "asset_id": "SPY", "next_earnings": None, "earnings_checked_at": fresh},
        "stock:old": {"kind": "Stock", "asset_id": "OLD", "next_earnings": "2026-11-01", "earnings_checked_at": old},
        "crypto:btc": {"kind": "Crypto", "asset_id": "bitcoin", "next_earnings": None, "earnings_checked_at": fresh},
        "stock:never": {"kind": "Stock", "asset_id": "NEVER"},
    }
    assert ms.earnings_from_rows(rows) == {"AAPL": "2026-10-30", "SPY": None}
