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
