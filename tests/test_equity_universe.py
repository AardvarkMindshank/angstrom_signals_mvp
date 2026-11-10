"""The equity funnels' universe (equity_universe.py), with Yahoo faked."""

import equity_universe as eu


def test_gate_reasons_and_rank():
    shares = [{"ticker": "AAPL", "name": "Apple", "sector": "IT"}, {"ticker": "PENNY", "name": "Penny"},
              {"ticker": "THIN", "name": "Thin"}, {"ticker": "NEW", "name": "New"}, {"ticker": "GONE", "name": "Gone"},
              {"ticker": "MSFT", "name": "Microsoft"}]
    q = {"AAPL": (200.0, 9e9, 1800, 3e12), "PENNY": (3.0, 5e7, 1800, 1e9), "THIN": (50.0, 5e6, 1800, 1e9),
         "NEW": (40.0, 5e7, 90, 1e10), "MSFT": (400.0, 8e9, 1800, 3.5e12)}

    def quality(t):
        if t == "GONE":
            return None
        price, vol, days, cap = q[t]
        return {"price": price, "volume_usd": vol, "days": days, "market_cap": cap, "next_earnings": "2026-11-20"}

    u = eu.build(shares=shares, quality_of=quality)
    assert [(c["ticker"], c["rank"]) for c in u["included"]] == [("MSFT", 1), ("AAPL", 2)]
    why = {e["ticker"]: e["reason"] for e in u["excluded"]}
    assert why["PENNY"].startswith("price under") and why["THIN"].startswith("thin trading")
    assert why["NEW"].startswith("only 90 days") and why["GONE"] == "no prices on Yahoo Finance"
    assert eu.yahoo_ticker("BRK.B") == "BRK-B"
    assert "2 usable of 6" in eu.summary(u)
