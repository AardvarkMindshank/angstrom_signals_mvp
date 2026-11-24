"""🧭 The member-focused Passage Plan (24 Nov 2026): facts about the member's own assets, not the market report."""
import json
from datetime import datetime, timezone

import pandas as pd

import passage


class _Q:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    def execute(self):
        return type("R", (), {"data": self.rows})()


class _DB:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Q(self.tables.get(name, []))


def _load(kind, aid, interval, rng):
    idx = pd.date_range("2026-11-12", periods=9, freq="B", tz="UTC")       # ends Monday 23 Nov
    closes = [100.0] * 8 + ([110.0] if aid == "bitcoin" else [99.0])
    return {"candles": pd.DataFrame({"close": closes, "forming": [False] * 9}, index=idx)}


def test_facts_are_the_members_assets_biggest_move_first(monkeypatch):
    import tides

    monkeypatch.setattr(tides, "latest", lambda db: None)
    readings = {"fields": {"signals": {"as_of": "2026-11-23", "clusters": {"trend": {"percent": 40},
                                                                         "stretch": {"percent": 70},
                                                                         "flow": {"percent": -5}}}}}
    db = _DB({"asset_market": [{"asset_key": "crypto:bitcoin", "readings": readings, "sentiment_score": 80,
                                "sentiment_updated_at": datetime.now(timezone.utc).isoformat(),
                                "sentiment_report": {"headlines": [{"title": "ETF inflows return", "source": "X",
                                                                    "score": 85}]}}],
              "readings_daily": [{"asset_key": "crypto:bitcoin", "day": "2026-11-23", "trend": 40, "stretch": 70,
                                  "flow": -5},
                                 {"asset_key": "crypto:bitcoin", "day": "2026-11-20", "trend": 10, "stretch": 66,
                                  "flow": -5}]})
    import market_store
    monkeypatch.setattr(market_store, "asset_market_key", lambda k, i: f"{'crypto' if k == 'Crypto' else 'stock'}:{i}")
    row = {"crypto_watchlist": {"ethereum": "Ether", "bitcoin": "Bitcoin"}, "stock_watchlist": {}}
    f = passage.facts(db, "u1", row, datetime(2026, 11, 24, 1, tzinfo=timezone.utc), load=_load)
    names = [a["name"] for a in f["watchlist"]]
    assert names == ["Bitcoin", "Ether"]                                 # +10% first, then -1%
    btc = f["watchlist"][0]
    assert btc["change_1d"] == 10.0 and btc["readings_now"] == {"trend": 40, "stretch": 70, "flow": -5}
    assert btc["readings_change_since"] == {"day": "2026-11-20", "trend": 30, "stretch": 4, "flow": 0}
    assert btc["news_mood"] == 60 and btc["top_story"]["title"] == "ETF inflows return"
    assert "markets" not in f and f["tide_context"] == {}                # no market report in it


def test_the_plan_needs_both_versions_and_ends_with_the_fixed_close(monkeypatch):
    import ai_providers

    monkeypatch.setattr(ai_providers, "available", lambda p: True)
    monkeypatch.setattr(ai_providers, "app_choice", lambda db, k: "grok")
    good = json.dumps({"written": "**🧭 Your morning in brief**\\nx", "spoken": "Good morning. " + "word " * 80})
    plan, who = passage.write(None, {}, datetime(2026, 11, 24), chat=lambda *a, **k: good)
    assert who == "grok" and plan["spoken"].endswith("Fair winds and following seas.")
    plan, who = passage.write(None, {}, datetime(2026, 11, 24), chat=lambda *a, **k: json.dumps({"written": "x"}))
    assert plan is None
    system, _ = passage.prompt({}, datetime(2026, 11, 24), "Angus")
    assert "NOT a market report" in system and "Good morning, Angus." in system
