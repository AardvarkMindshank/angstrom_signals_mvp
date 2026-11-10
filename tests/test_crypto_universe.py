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
    q = {"BTCUSDT": (2500, 9e8, 0), "NEWUSDT": (40, 5e7, 0), "THINUSDT": (900, 4e5, 0), "SOLUSDT": (1800, 3e8, 0)}

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
