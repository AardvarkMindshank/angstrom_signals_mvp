"""Every coin is named the same way: "Name (TICKER)", or just the name when it is the ticker."""
from service import coin_names as cn


def test_label_rules():
    assert cn.label("solana", "Solana (SOL)", "Solana", "SOL") == "Solana (SOL)"
    assert cn.label("ripple", "XRP", "XRP", "XRP") == "XRP"
    assert cn.label("midnight-3", "Midnight", "Midnight", "NIGHT") == "Midnight (NIGHT)"
    assert cn.label("x", "Stacks (STX)", "", "") == "Stacks"                      # no ticker known: no bracket
    assert cn.label("aave", "Aave", "Aave", "AAVE") == "Aave (AAVE)"
    assert cn._ticker_in("Stacks (STX)") == "STX"


def test_labels_without_coingecko(monkeypatch):
    monkeypatch.setattr(cn, "_fetch", lambda ids: None)
    got = cn.labels({"blockstack": "Stacks (STX)", "midnight": "Midnight"})
    assert got == {"blockstack": "Stacks (STX)", "midnight": "Midnight"}
