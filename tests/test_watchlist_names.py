"""One stored form for coin names, "Name (TICKER)", and the hourly tidy that keeps watchlists in it."""
import watchlist_names as wn
from crypto_universe import coin_label


def test_coin_label():
    assert coin_label("Solana", "sol") == "Solana (SOL)"
    assert coin_label("Aave", "AAVE") == "Aave (AAVE)"
    assert coin_label("XRP", "XRP") == "XRP"
    assert coin_label("Solana (SOL)", "SOL") == "Solana (SOL)"
    assert coin_label("Stacks", "") == "Stacks"


def test_fixed_uses_the_search_list_and_looks_up_others_once():
    known = {"polkadot": ("Polkadot", "DOT"), "ripple": ("XRP", "XRP"), "dogecoin": ("Dogecoin", "DOGE")}
    asked = []
    lookup = lambda cid: (asked.append(cid), ("maxxing", "MAXXING"))[1]  # noqa: E731
    got = wn.fixed({"polkadot": "Dot", "ripple": "XRP", "dogecoin": "Dogecoin", "maxxing": "maxxing",
                    "smallcoin": "Small Coin (SMC)"}, known, lookup)
    assert got == {"polkadot": "Polkadot (DOT)", "ripple": "XRP", "dogecoin": "Dogecoin (DOGE)",
                   "maxxing": "maxxing (MAXXING)", "smallcoin": "Small Coin (SMC)"}
    assert asked == ["maxxing"]                     # a saved name with a ticker is never looked up
