"""✨ AI Navigator on Tides (navigator.py): what it is told, and Today's AI Passage Plan."""

import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "tests")

import advisor
import navigator as nv
import tides as td
from test_tides import _raw


def _snap():
    return json.loads(json.dumps(td.snapshot(_raw(), btc_dominance=57.0, fear_greed=30)))


def test_tides_context_carries_every_current_the_winds_and_the_calendar():
    text = nv.tides_context(_snap(), datetime(2026, 11, 12, tzinfo=timezone.utc))
    for c in td.CURRENTS:
        assert c[1] in text
    assert "Wind for Crypto longs" in text and "Sea state" in text and "Producer prices" in text
    assert "shown, does not vote" in text and "Fear & Greed" in text
    assert nv.tides_context(None) == "Tides readings: not available right now."


def test_the_navigator_gets_tides_only_when_opened_from_tides():
    shared, mine = advisor.system_parts([], "u1", "tides", extra=nv.TIDES_RULES)
    assert "🌊 Tides" in mine and "never bring in outside news" in mine and "AI Navigator" in shared
    _shared, plain = advisor.system_parts([], "u1", "app")
    assert "Tides (the macro layer)" not in plain


class _Q:
    def __init__(self, db, op=None, row=None):
        self.db, self.op, self.row = db, op, row

    def select(self, *a):
        self.op = "select"
        return self

    def insert(self, row):
        return _Q(self.db, "insert", row)

    def eq(self, *a):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a):
        return self

    def execute(self):
        if self.op == "insert":
            self.db.rows.append(self.row)
        data = [self.db.rows[-1]] if self.op == "select" and self.db.rows else []
        return type("R", (), {"data": data})()


class _DB:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "navigator_logbook"
        return _Q(self)


class _St:
    session_state = {}


def test_passage_plan_is_written_once_a_day_and_kept(monkeypatch):
    calls = []
    monkeypatch.setattr(advisor, "ask", lambda history, q, system, **k: calls.append((q, system)) or "PLAN")
    monkeypatch.setattr(nv, "portfolio_context", lambda *a: "This person's watchlist: Bitcoin")
    import signal_groups_inspector as gi

    monkeypatch.setattr(gi, "saved_configs", lambda supabase: ([], None))
    db = _DB()
    snap = _snap()
    assert nv.passage_plan(_St, db, "u1", {}, snap) == "PLAN"
    assert nv.passage_plan(_St, db, "u1", {}, snap) == "PLAN" and len(calls) == 1     # the second read is the logbook
    q, system = calls[0]
    assert "⚓ Conditions" in q and "Expectation" in q and "No buy or sell" in q
    assert "Tides readings" in system[1] and "Bitcoin" in system[1]
    row = db.rows[0]
    assert row["kind"] == "passage_plan" and row["readings"]["tide"] == snap["tide"]["label"]
