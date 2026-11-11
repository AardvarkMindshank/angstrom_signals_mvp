"""The funnel on the page (funnel_view.py): picker counts, the coins each choice shows, and the stage hover."""

import pandas as pd

import funnel as fn
import funnel_templates as ft
import funnel_view as fv
from funnel import NO, YES

_CRYPTO = ft.trend_funnel("long")
# The four-stage shape these tests were written for (the crypto funnel before its wide daily-trend stage).
F = {**_CRYPTO, "stages": _CRYPTO["stages"][1:], "id": "f", "stages_version": 1}


def _coin(answers):
    st = fn.CoinState.new(4)
    for k, a in answers:
        fn.record(st, k, a, "2026-11-10T00:00:00+00:00", "EMA 20 vs 50: fast_below")
    return st


STATES = {"btc": _coin([(0, YES), (1, YES), (2, YES), (3, YES)]), "sol": _coin([(0, YES), (1, YES), (2, YES)]),
          "eth": _coin([(0, YES), (1, NO), (1, NO)]), "doge": _coin([(0, NO)])}


def test_picker_and_choices():
    labels = dict(fv.picks(F, STATES, 4))
    assert labels["stage:0"].endswith("· 3") and labels["stage:2"].endswith("· 2")
    assert labels["flagged"] == "🚩 Flagged · 1" and labels["candidate"] == "✅ Candidates · 1"
    assert fv.coins_for("stage:0", STATES) == ["btc", "sol", "eth"]
    assert fv.coins_for("candidate", STATES) == ["btc"] and fv.coins_for("flagged", STATES) == ["sol"]
    assert fv.counts_line(F, STATES, 4) == "4 → 3 → 2 → 2 → 1 ✅ / 1 🚩"


def test_stage_hover_explains():
    icon, hover, _ = fv.stage_cell(F, STATES["sol"])
    assert icon == "▲🚩" and "waiting for the 1-hour entry conditions" in hover
    icon, hover, _ = fv.stage_cell(F, STATES["eth"])
    assert icon == "▲👁" and "12-hour: No" in hover and "fast_below" in hover
    _, hover, _ = fv.stage_cell(F, STATES["doge"])
    assert hover.startswith("In the pool")


def test_health_warns_on_failed_or_late_runs():
    now = pd.Timestamp("2026-11-10 12:00", tz="UTC")
    ok = [{"cutoff": "2026-11-10T00:00:00+00:00", "status": "ok"}, None, None, None]
    assert fv.health(ok, F, now) is None
    bad = [{"cutoff": "2026-11-10T00:00:00+00:00", "status": "failed", "error": "Binance down"}, None, None, None]
    assert "failed" in fv.health(bad, F, now)
    late = [{"cutoff": "2026-11-07T00:00:00+00:00", "status": "ok"}, None, None, None]
    assert "has not been checked" in fv.health(late, F, now)


def test_the_hover_names_the_candle_source():
    _, hover, _ = fv.stage_cell(F, STATES["btc"], "BTCUSDT")
    assert hover.endswith("Candles: Binance spot (BTCUSDT).")
    _, hover, _ = fv.stage_cell(F, STATES["btc"], "yahoo:XMR-USD")
    assert "Yahoo Finance (XMR-USD)" in hover


def test_share_hover_names_yahoo_and_earnings():
    eq = {**ft.trend_funnel("long", "equity"), "id": "e", "stages_version": 1}
    now = pd.Timestamp("2026-11-10", tz="UTC")
    _, hover, _ = fv.stage_cell(eq, STATES["btc"], "yahoo:AAPL", earnings="2026-11-13", now=now)
    assert "Reports earnings in 3 days (2026-11-13)" in hover and "Yahoo Finance (AAPL), New York" in hover
    _, hover, _ = fv.stage_cell(eq, STATES["btc"], "yahoo:AAPL", earnings="2026-12-30", now=now)
    assert "earnings" not in hover


class _Q:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    def execute(self):
        return type("R", (), {"data": self.rows})()


class _DB:
    def __init__(self, funnels, coins, universe):
        self.t = {"funnels": funnels, "funnel_coins": coins, "crypto_universe": universe}

    def table(self, name):
        return _Q(self.t[name])


def test_price_refresh_takes_candidates_then_the_largest_of_the_rest(monkeypatch):
    monkeypatch.setattr(fv, "PRICE_LIMIT", 2)
    funnels = [{"id": "f", "market": "crypto", "stages": [{}] * 4, "stages_version": 1}]
    coins = [{"coin_id": c, "depth": d, "stages_version": 1} for c, d in
             (("tiny", 3), ("btc", 3), ("eth", 3), ("sol", 4), ("doge", 3))]
    universe = [{"coin_id": c, "name": c.upper(), "rank": r, "included": True, "pair": None} for c, r in
                (("btc", 1), ("eth", 2), ("sol", 5), ("doge", 8), ("tiny", 400))]
    got = fv.watched_by_funnels(_DB(funnels, coins, universe))
    assert set(got) == {("Crypto", "sol"), ("Crypto", "btc"), ("Crypto", "eth")}


def test_daily_summary_shows_each_funnel():
    import digest

    funnels = [{"name": "Trend crypto shorts ▼", "candidates": ["Bitcoin", "Aptos"], "more": 0, "count": 2,
                "flagged": 7, "line": "197 → 40 → 12 → 9 → 2 ✅ / 7 🚩"}]
    subject, page, plain = digest.render_digest([], [], {"digest_tz": "Asia/Bangkok"}, "https://x", funnels=funnels)
    assert subject == "Angstrom daily summary: 2 funnel Candidates"
    assert "Your funnels today" in plain and "2 Candidates: Bitcoin, Aptos · 7 Flagged" in plain
    assert "not a recommendation to trade" in page


def test_chart_view_opens_on_the_deepest_stage_timeframe():
    tfs = [s["timeframe"] for s in F["stages"]]
    assert fv.chart_view(F, STATES["doge"]) is None                              # holds no stage yet
    assert fv.chart_view(F, STATES["eth"]) == (tfs[0], fv.fr.FUNNEL_RANGE[tfs[0]])
    assert fv.chart_view(F, STATES["sol"])[0] == tfs[2]
    cand = fv.chart_view(F, STATES["btc"])
    assert cand == (tfs[-1], fv.fr.FUNNEL_RANGE[tfs[-1]]) and tfs[-1] == "1h"   # a Candidate: the entry stage
