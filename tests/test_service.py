"""The data service for the new app (service/app.py), with the database and the AI replaced by stand-ins."""
import math

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import service.app as svc  # noqa: E402


class _Q:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    @property
    def not_(self):
        return self

    def execute(self):
        class R:
            pass
        r = R()
        r.data = self.rows
        return r


class _DB:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return _Q(self.tables.get(name, []))


def _client(tables=None):
    db = _DB(tables or {})
    svc.app.dependency_overrides[svc.member] = lambda: svc.Member("u1", db, "tok")
    return TestClient(svc.app)


def teardown_function(_):
    svc.app.dependency_overrides.clear()
    svc._news.update(at=0.0, items=[])
    svc._asked.clear()


def test_health_needs_no_sign_in():
    assert TestClient(svc.app).get("/health").json()["ok"] is True


def test_every_other_call_needs_a_sign_in():
    c = TestClient(svc.app)
    assert c.get("/asset/sets?key=Crypto|bitcoin").status_code == 401
    assert c.get("/search?q=inflation").status_code == 401


def test_sonar_follows_the_candles():
    n = 200
    close = [100 + 10 * math.sin(i / 8) for i in range(n)]
    body = {"time": [1700000000 + 86400 * i for i in range(n)], "open": close, "high": [x + 1 for x in close],
            "low": [x - 1 for x in close], "close": close, "volume": [1000.0] * n}
    got = _client().post("/sonar", json=body).json()
    assert len(got["wt1"]) == n and len(got["buy"]) == n
    assert any(got["cross"]) and all(v in (-1, 0, 1) for v in got["cross"])


def test_sonar_refuses_too_few_candles():
    body = {"time": [1, 2], "open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1, 1], "volume": [1, 1]}
    assert _client().post("/sonar", json=body).status_code == 400


def test_search_finds_headlines_assets_and_logbook():
    rep = {"headlines": [{"id": "a", "title": "Inflation cools, Bitcoin rises", "score": 70, "published_at": "2026-11-26T10:00:00+00:00"},
                         {"id": "b", "title": "Something else", "score": 40, "published_at": "2026-11-26T11:00:00+00:00"}]}
    c = _client({"asset_market": [{"asset_key": "Crypto|bitcoin", "sentiment_report": rep}],
                 "market_mood": [{"market_key": "crypto", "sentiment_report": {"headlines": [
                     {"id": "c", "title": "US inflation data due", "score": 50, "published_at": "2026-11-27T01:00:00+00:00"}]}}],
                 "navigator_logbook": [{"day": "2026-11-26", "kind": "passage_plan", "body": "Watch inflation this week."}]})
    got = c.get("/search?q=inflation").json()
    assert [n["id"] for n in got["news"]] == ["c", "a"]
    assert got["assets"] == [{"key": "Crypto|bitcoin", "articles": 1}]
    assert got["mood"] == 60.0 and got["logbook"][0]["day"] == "2026-11-26"


def test_sets_are_checked_on_the_asset(monkeypatch):
    import prism

    saved = [{"id": "s1", "kind": "set", "owner_id": "u1", "name": "My breakout", "versions": [{"body": {"name": "My breakout"}}]},
             {"id": "s2", "kind": "set", "owner_id": "someone-else", "name": "Not mine", "versions": [{"body": {}}]}]
    monkeypatch.setattr(svc, "saved_configs", lambda db: saved)
    monkeypatch.setattr(prism, "run_now", lambda doc, assets, **k: [{"answer": "yes", "reason": "Every line holds.", "how_sure": "Sure", "lines": {}}])
    got = _client().get("/asset/sets?key=Crypto|ripple").json()
    assert [(s["name"], s["answer"]) for s in got["sets"]] == [("My breakout", "yes")]


def test_sets_refuse_an_unknown_asset():
    assert _client().get("/asset/sets?key=Nonsense").status_code == 400


def test_navigator_answers_and_counts(monkeypatch):
    import advisor
    import ai_providers

    monkeypatch.setattr(ai_providers, "available", lambda p: True)
    monkeypatch.setattr(svc, "saved_configs", lambda db: [])
    seen = {}

    def ask(history, question, system, **k):
        seen["q"], seen["tools"] = question, k.get("tools")
        return "Here is how."
    monkeypatch.setattr(advisor, "ask", ask)
    c = _client({"user_plans": [{"plan": "free"}]})
    got = c.post("/navigator", json={"question": "What is Stretch?", "language": "th"}).json()
    assert got["answer"] == "Here is how." and got["used"] == 1 and got["limit"] == 5
    assert seen["q"] == "What is Stretch?" and seen["tools"] is not None
    for _ in range(4):
        c.post("/navigator", json={"question": "again"})
    assert c.post("/navigator", json={"question": "one more"}).status_code == 429


# ---- the Pro chart ------------------------------------------------------------------------------------------------

def _fake_candles(monkeypatch, error=None):
    import numpy as np
    import pandas as pd

    from service import pro_chart

    def load(kind, aid, interval, range_key, now=None, fetch=None):
        if error:
            return {"candles": None, "start": None, "session": None, "source": "", "error": error}
        idx = pd.date_range(end=pd.Timestamp("2026-11-27", tz="UTC"), periods=300, freq="1D")
        rng = np.random.default_rng(3)
        close = 100 + rng.normal(0, 1, len(idx)).cumsum()
        c = pd.DataFrame({"open": np.r_[close[0], close[:-1]], "close": close, "volume": rng.integers(1000, 5000, len(idx)).astype(float)}, index=idx)
        c["high"] = c[["open", "close"]].max(axis=1) + 0.5
        c["low"] = c[["open", "close"]].min(axis=1) - 0.5
        c["forming"] = [False] * (len(idx) - 1) + [True]
        return {"candles": c, "start": idx[-90], "session": None, "source": "Test candles", "error": None}

    monkeypatch.setattr(pro_chart.chart_candles, "load_candles", load)
    monkeypatch.setattr(pro_chart, "_events", lambda: [])
    pro_chart._frames.clear()


def test_chart_needs_a_sign_in():
    c = TestClient(svc.app)
    assert c.post("/chart", json={"key": "Crypto|bitcoin"}).status_code == 401
    assert c.get("/chart/options?key=Crypto|bitcoin").status_code == 401


def test_chart_builds_the_classic_payload(monkeypatch):
    _fake_candles(monkeypatch)
    out = _client().post("/chart", json={"key": "Crypto|bitcoin", "interval": "1D", "range": "3M",
                                          "indicators": ["cipher", "sonar_marks", "rsi", "macd", "fvg"]}).json()
    p = out["payload"]
    assert len(p["times"]) == 300 and p["forming"] is True
    titles = [x["title"] for x in p["panes"]]
    assert titles[1] == "Sonar" and "Volume" in titles and "RSI (14)" in titles and "MACD" in titles
    assert any(s["id"] == "mc_wt1" for s in p["series"]) and p["fvg"] is True
    assert "lib" not in p                         # the new app bundles the chart library itself


def test_chart_says_when_a_range_does_not_fit_the_candle_size(monkeypatch):
    _fake_candles(monkeypatch)
    out = _client().post("/chart", json={"key": "Crypto|bitcoin", "interval": "15m", "range": "All"}).json()
    assert out["error"] and out["nearest"] in ("7D", "1M")


def test_chart_passes_on_a_candle_error(monkeypatch):
    _fake_candles(monkeypatch, error="No candles for this coin.")
    out = _client().post("/chart", json={"key": "Stock|ZZZZ", "interval": "1h", "range": "1M"}).json()
    assert out == {"error": "No candles for this coin."}


def test_chart_rejects_unknown_assets():
    assert _client().post("/chart", json={"key": "Bonds|x"}).status_code == 400


def test_chart_options_list_what_the_chart_can_show(monkeypatch):
    from service import pro_chart

    monkeypatch.setattr(pro_chart, "set_options", lambda db, uid: {"p1": ("Oversold bounce (provided)", {})})
    crypto = _client().get("/chart/options?key=Crypto|bitcoin").json()
    stock = _client().get("/chart/options?key=Stock|AAPL").json()
    assert "5m" in crypto["intervals"] and "1Mo" in crypto["intervals"]
    assert any(k == "liq" for k, _ in crypto["indicators"]) and not any(k == "liq" for k, _ in stock["indicators"])
    assert crypto["sets"] == [{"key": "p1", "name": "Oversold bounce (provided)"}]
    assert crypto["sonar_default"] and len(crypto["sonar_marks"]) == 9


# ---- 📸 Quick Snapshot ----------------------------------------------------------------------------------------------

def _row(kind, key, trend, parts=None, **extra):
    return {"type": kind, "key": key, "symbol": key.upper(), "logo": "", "trend": trend, "trend_parts": parts or {},
            "price": 10.0, "change_1d": 1.0, "closes": [1, 2, 3], "mood": None, "next_earnings": "", **extra}


def test_snapshot_what_changed_finds_crossings_and_moves():
    from service import snapshot as snap

    rows = [_row("Crypto", "xrp", -43.0, {"Price vs 50-day average": -20.0}), _row("Stock", "AAPL", 18.0),
            _row("Crypto", "btc", 12.0)]
    base = {"Crypto:xrp": {"trend": -12.0, "factors": {"Price vs 50-day average": -1.8}},
            "Stock:AAPL": {"trend": 10.0, "factors": {}}, "Crypto:btc": {"trend": 11.0, "factors": {}}}
    out = snap.what_changed(rows, base, {})
    assert out["seen"] and [c["pick"] for c in out["crossings"]] == ["Crypto|xrp"]
    assert "moved it most" in out["crossings"][0]["detail"]
    assert [m["pick"] for m in out["moves"]] == ["Stock|AAPL"]          # BTC moved 1 point: too small to list
    assert snap.what_changed(rows, {}, {}) == {"seen": False, "crossings": [], "moves": []}


def test_snapshot_extremes_and_visit_record():
    from service import snapshot as snap

    rows = [_row("Crypto", "a", 30.0), _row("Crypto", "b", -5.0), _row("Stock", "X", 2.0), _row("Stock", "Y", None)]
    x = snap.extremes(rows)
    assert x["crypto"]["top"]["pick"] == "Crypto|a" and x["crypto"]["bottom"]["pick"] == "Crypto|b"
    assert x["equity"]["bottom"] is None
    v = snap.visit_snapshot(rows)
    assert set(v) == {"Crypto:a", "Crypto:b", "Stock:X"} and v["Crypto:a"]["trend"] == 30.0


def test_snapshot_endpoint_keeps_going_when_a_part_fails(monkeypatch):
    from service import snapshot as snap

    monkeypatch.setattr(snap, "_asset_rows", lambda db, s, c, k: [_row("Crypto", "a", 30.0)])
    monkeypatch.setattr(snap, "tides_card", lambda db: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(snap, "moods", lambda db, s: [])
    monkeypatch.setattr(snap, "funnel_tiles", lambda db, uid, s: ([], {}))
    monkeypatch.setattr(snap, "markets", lambda db, s: {"groups": [], "cards": []})
    saved = {}
    monkeypatch.setattr(snap, "_save_settings", lambda db, uid, u: saved.update(u))
    out = _client({"user_preferences": [{"settings": {}, "crypto_watchlist": {"a": "A"}, "stock_watchlist": {}}]}) \
        .get("/snapshot?save=true").json()
    assert out["tides"] is None and out["errors"] == ["tides"]
    assert out["extremes"]["crypto"]["top"]["pick"] == "Crypto|a"
    assert "Crypto:a" in saved["score_visit"]
