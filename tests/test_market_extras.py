"""market_extras: which stocks are due an earnings lookup, and that a 'no date' never wipes a date still ahead."""
import market_extras as mx


def test_due_is_never_checked_or_stale_oldest_first():
    now = 1_800_000_000
    iso = lambda t: __import__("datetime").datetime.fromtimestamp(t, __import__("datetime").timezone.utc).isoformat()
    catalog = {("Stock", "AAPL"): "", ("Stock", "msft"): "", ("Stock", "NVDA"): "", ("Crypto", "bitcoin"): ""}
    rows = {"Stock|AAPL": {"earnings_checked_at": iso(now - 3600)},
            "Stock|MSFT": {"earnings_checked_at": iso(now - 13 * 3600)}}
    from market_store import asset_market_key
    rows = {asset_market_key("Stock", k.split("|")[1]): v for k, v in rows.items()}
    assert mx.earnings_due(catalog, rows, now) == ["NVDA", "MSFT"]


def test_keep_known_date_ahead():
    from market_store import asset_market_key
    rows = {asset_market_key("Stock", "AAPL"): {"next_earnings": "2099-01-01"},
            asset_market_key("Stock", "OLD"): {"next_earnings": "2000-01-01"}}
    got = mx.keep_known({"AAPL": None, "OLD": None, "NEW": "2099-02-02"}, rows, "2026-11-28")
    assert got == {"AAPL": "2099-01-01", "OLD": None, "NEW": "2099-02-02"}
