"""The Set editor's fixed-asset search uses the Watchlist editor's market search."""

import json

import lattice_set_view as v


def test_coins_by_coingecko_id_and_equities_by_ticker():
    ask = json.dumps({"slot": "trend", "kind": "crypto", "q": "bitc", "nonce": 7})
    got = v.fixed_asset_matches(ask, search_crypto=lambda q: [{"id": "bitcoin", "name": "Bitcoin", "symbol": "BTC"}])
    assert got == {"slot": "trend", "kind": "crypto", "q": "bitc", "nonce": 7,
                   "results": [{"id": "bitcoin", "label": "Bitcoin (BTC)"}]}
    ask = json.dumps({"slot": "trend", "kind": "equity", "q": "coinbase", "nonce": 8})
    got = v.fixed_asset_matches(ask, search_stock=lambda q: [{"symbol": "COIN", "name": "Coinbase Global",
                                                               "exchange": "NASDAQ", "type": "Stock"}])
    assert got["results"] == [{"id": "COIN", "label": "COIN · Coinbase Global · NASDAQ"}]


def test_bad_or_empty_asks_and_failed_searches():
    assert v.fixed_asset_matches("not json") is None
    assert v.fixed_asset_matches(json.dumps({"kind": "crypto", "q": " "})) is None
    assert v.fixed_asset_matches(json.dumps({"kind": "forex", "q": "eur"})) is None
    boom = v.fixed_asset_matches(json.dumps({"kind": "crypto", "q": "x1", "slot": "a"}),
                                 search_crypto=lambda q: 1 / 0)
    assert boom["results"] == []
