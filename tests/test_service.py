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
