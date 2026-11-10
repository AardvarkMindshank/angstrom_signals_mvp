"""The funnel's crypto universe (crypto_universe.py): who is in, who is left out and why, with every source faked."""

import crypto_universe as cu


def _coin(cid, sym, price, name=None):
    return {"id": cid, "symbol": sym, "name": name or cid.title(), "current_price": price}


def test_rules_and_reasons():
    coins = [_coin("bitcoin", "btc", 70000), _coin("tether", "usdt", 1.0), _coin("wrapped-bitcoin", "wbtc", 70000,
             "Wrapped Bitcoin"), _coin("monero", "xmr", 150), _coin("pepe-impostor", "pepe", 0.5),
             _coin("newcoin", "new", 2.0), _coin("thincoin", "thin", 1.5), _coin("solana", "sol", 150)]
    pairs = {"BTC": "BTCUSDT", "PEPE": "PEPEUSDT", "NEW": "NEWUSDT", "THIN": "THINUSDT", "SOL": "SOLUSDT",
             "WBTC": "WBTCUSDT"}
    prices = {"BTCUSDT": 70100, "PEPEUSDT": 0.00001, "NEWUSDT": 2.0, "THINUSDT": 1.5, "SOLUSDT": 151}
    q = {"BTCUSDT": (2500, 9e8, 0), "NEWUSDT": (40, 5e7, 0), "THINUSDT": (900, 1e5, 0), "SOLUSDT": (1800, 3e8, 0)}

    def quality(pair):
        days, vol, gaps = q[pair]
        return {"listed_since": "2020-01-01", "days": days, "volume_usd": vol, "gap_days": gaps}

    u = cu.build(coins=coins, excluded_ids={"tether": cu.REASON["stablecoins"]}, pairs=pairs,
                 price_of=prices.get, quality_of=quality)
    assert [c["id"] for c in u["included"]] == ["bitcoin", "solana"]
    why = {e["id"]: e["reason"] for e in u["excluded"]}
    assert why["tether"].startswith("stablecoin") and why["wrapped-bitcoin"].startswith("wrapped")
    assert why["monero"].startswith("not traded on Binance")
    assert "different price" in why["pepe-impostor"]
    assert why["newcoin"].startswith("only 40 days") and why["thincoin"].startswith("thin trading")
    assert len(u["included"]) + len(u["excluded"]) == len(coins)          # every coin accounted for
    assert "2 coins usable of the top 8" in cu.summary(u)


def test_gappy_hourly_candles_are_left_out():
    coins = [_coin("gappy", "gap", 1.0)]
    u = cu.build(coins=coins, excluded_ids={}, pairs={"GAP": "GAPUSDT"}, price_of={"GAPUSDT": 1.0}.get,
                 quality_of=lambda p: {"listed_since": "2020-01-01", "days": 900, "volume_usd": 5e5, "gap_days": 0,
                                       "quiet_hours": 0.2})
    assert u["excluded"][0]["reason"].startswith("gappy hourly candles (20%")


def test_yahoo_fallback_for_coins_binance_does_not_list():
    import pandas as pd

    now = pd.Timestamp("2026-11-10", tz="UTC")
    coins = [_coin("monero", "xmr", 300), _coin("leo-token", "leo", 9), _coin("tiny", "tiny", 1),
             _coin("impostor", "imp", 5)]
    for c, vol in zip(coins, (5e7, 5e7, 2e5, 5e6)):
        c["total_volume"] = vol
    closes = {"XMR-USD": 301.0, "IMP-USD": 50.0}

    def check(ticker, now):
        return {"days": 3000, "close": closes[ticker], "listed_since": "2017-11-09", "missing_hours": 0.0}

    u = cu.build(coins=coins, excluded_ids={}, pairs={}, price_of=lambda p: None, quality_of=None, now=now,
                 kinds={"leo-token": "another exchange's own token"},
                 yahoo=lambda coin, now: cu.yahoo_fallback(coin, now, check=check))
    assert [(c["id"], c["pair"]) for c in u["included"]] == [("monero", "yahoo:XMR-USD")]
    why = {e["id"]: e["reason"] for e in u["excluded"]}
    assert "another exchange's own token" in why["leo-token"]
    assert "thin trading elsewhere" in why["tiny"] and "another coin" in why["impostor"]
    assert "1 from Yahoo" in cu.summary(u)


def test_register_points_the_loaders_at_the_checked_source():
    import binance_data as bn
    import data_fetchers

    cu.register([{"coin_id": "monero-x", "pair": "yahoo:XMR-USD"}, {"coin_id": "solana-x", "pair": "SOLUSDT"}])
    assert bn.pair_for("crypto", "monero-x") is None and bn.coingecko_coin("monero-x") is None
    assert bn.pair_for("crypto", "solana-x", pairs={}) == "SOLUSDT"
    assert data_fetchers.YF_BY_COINGECKO_ID["monero-x"] == "XMR-USD"
