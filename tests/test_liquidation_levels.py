import liquidation_levels as liq


def bar(t, h, l, c):
    return {"t": t, "h": h, "l": l, "c": c}


def test_rising_open_interest_puts_longs_below_and_shorts_above():
    bars = [bar(0, 101, 99, 100), bar(1, 101, 99, 100)]
    oi = [{"t": 0, "c": 1_000_000}, {"t": 1, "c": 2_000_000}]
    result = liq.estimate_levels(bars, oi)
    assert result["price"] == 100
    assert result["longs"] and all(level["price"] < 99 for level in result["longs"])
    assert result["shorts"] and all(level["price"] > 101 for level in result["shorts"])
    # 10x is the biggest share, so its level (about 9.5% away) is the strongest.
    assert 89 < result["longs"][0]["price"] < 92
    assert 108 < result["shorts"][0]["price"] < 111
    # 100x positions sit 0.5% away, inside that hour's own range, so they are already gone.
    total = sum(l["usd"] for l in result["longs"]) + sum(s["usd"] for s in result["shorts"])
    assert abs(total - 850_000) < 1


def test_long_short_ratio_splits_the_new_positions():
    bars = [bar(0, 101, 99, 100), bar(1, 101, 99, 100)]
    oi = [{"t": 0, "c": 0.0 + 1}, {"t": 1, "c": 1_000_001}]
    result = liq.estimate_levels(bars, oi, [{"t": 1, "r": 3.0}])
    longs = sum(l["usd"] for l in result["longs"])
    shorts = sum(s["usd"] for s in result["shorts"])
    assert abs(longs / (longs + shorts) - 0.75) < 0.01


def test_price_trading_through_a_level_removes_it():
    bars = [bar(0, 101, 99, 100), bar(1, 101, 99, 100), bar(2, 100, 85, 88)]
    oi = [{"t": 0, "c": 1_000_000}, {"t": 1, "c": 2_000_000}, {"t": 2, "c": 2_000_000}]
    result = liq.estimate_levels(bars, oi)
    # The drop to 85 liquidated the 10x and tighter longs; nothing is left above 85.
    assert all(level["price"] < 85 for level in result["longs"])


def test_falling_open_interest_shrinks_every_level():
    bars = [bar(0, 101, 99, 100), bar(1, 101, 99, 100), bar(2, 101, 99, 100)]
    grow = [{"t": 0, "c": 1_000_000}, {"t": 1, "c": 2_000_000}]
    half = grow + [{"t": 2, "c": 1_500_000}]
    before = liq.estimate_levels(bars[:2], grow)
    after = liq.estimate_levels(bars, half)
    assert abs(after["longs"][0]["usd"] - before["longs"][0]["usd"] * 0.75) < 1


def test_open_interest_uses_only_hours_every_market_reported():
    a = [{"t": 1, "c": 10}, {"t": 2, "c": 12}]
    b = [{"t": 2, "c": 5}]
    assert liq.combine_open_interest([a, b]) == [{"t": 2, "c": 17.0}]
    assert liq.combine_open_interest([]) == []


def test_pick_markets_prefers_big_exchanges_and_usdt_perpetuals():
    exchanges = [{"code": "A", "name": "Binance"}, {"code": "6", "name": "Bybit"}, {"code": "Z", "name": "Tiny"}]
    markets = [
        {"symbol": "SUIUSDC_PERP.A", "exchange": "A", "base_asset": "SUI", "quote_asset": "USDC", "is_perpetual": True, "margined": "STABLE"},
        {"symbol": "SUIUSDT_PERP.A", "exchange": "A", "base_asset": "SUI", "quote_asset": "USDT", "is_perpetual": True, "margined": "STABLE"},
        {"symbol": "SUIUSDT.6", "exchange": "6", "base_asset": "SUI", "quote_asset": "USDT", "is_perpetual": True, "margined": "STABLE"},
        {"symbol": "SUIUSD_PERP.A", "exchange": "A", "base_asset": "SUI", "quote_asset": "USD", "is_perpetual": True, "margined": "COIN"},
        {"symbol": "SUIUSDT.Z", "exchange": "Z", "base_asset": "SUI", "quote_asset": "USDT", "is_perpetual": True, "margined": "STABLE"},
        {"symbol": "BTCUSDT_PERP.A", "exchange": "A", "base_asset": "BTC", "quote_asset": "USDT", "is_perpetual": True, "margined": "STABLE"},
    ]
    chosen = [m["symbol"] for m in liq.pick_markets(markets, exchanges, "sui")]
    assert chosen == ["SUIUSDT_PERP.A", "SUIUSDT.6"]


def test_bad_rows_are_skipped():
    bars = [{"t": 0, "h": None, "l": 1, "c": 1}, bar(1, 101, 99, 100)]
    oi = [{"t": 0, "c": "x"}, {"t": 1, "c": 5}]
    result = liq.estimate_levels(bars, oi)
    assert result["price"] == 100 and result["longs"] == [] and result["shorts"] == []
