from datetime import datetime, timezone

from market_store import asset_market_key, market_stats_from_rows


def test_saved_caps_are_found_from_the_shared_key():
    now = datetime.now(timezone.utc).isoformat()
    shared = {
        asset_market_key("Crypto", "sui"): {
            "asset_key": asset_market_key("Crypto", "sui"),
            "market_cap": 3.1e9, "market_rank": 25, "market_stats_updated_at": now,
        },
        asset_market_key("Stock", "aapl"): {
            "asset_key": asset_market_key("Stock", "aapl"),
            "market_cap": 3.5e12, "market_rank": None, "market_stats_updated_at": now,
        },
    }
    stats = market_stats_from_rows(shared)
    assert stats["crypto"]["sui"]["cap"] == 3.1e9 and stats["crypto"]["sui"]["rank"] == 25
    assert stats["stock"]["AAPL"]["cap"] == 3.5e12


def test_saved_earnings_dates_found_from_the_key_alone():
    from datetime import datetime, timezone
    import market_store as ms
    now = datetime.now(timezone.utc).isoformat()
    rows = {
        "Stock|TSLA": {"asset_key": "Stock|TSLA", "next_earnings": "2027-01-28", "earnings_checked_at": now},
        "Stock|SPY": {"asset_key": "Stock|SPY", "next_earnings": None, "earnings_checked_at": now},
        "Crypto|sui": {"asset_key": "Crypto|sui", "earnings_checked_at": now},
    }
    assert ms.earnings_from_rows(rows) == {"TSLA": "2027-01-28", "SPY": None}
