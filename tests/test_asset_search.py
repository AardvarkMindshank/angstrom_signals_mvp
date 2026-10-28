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
