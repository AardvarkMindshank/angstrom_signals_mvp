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


def test_every_entry_point_gets_the_same_knowledge():
    """Wherever the Navigator is opened (top bar, Lattice, Tides, the passage plan), it is told the same things: only
    the line about what to expect first differs."""
    market = nv.market_context(_snap())
    briefs = {start: advisor.system_parts([], "u1", start, extra="watchlist: Bitcoin", market=market)
              for start in advisor.START}
    shared = {b[0] for b in briefs.values()}
    assert len(shared) == 1                                   # one cached part for every entry point
    (one,) = shared
    assert "Tides (the macro layer)" in one and "never bring in outside news" in one and "Tide:" in one
    for start, (_s, mine) in briefs.items():
        assert advisor.ANY_QUESTION in mine and "watchlist: Bitcoin" in mine and advisor.START[start] in mine


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
    monkeypatch.setattr(advisor, "ask", lambda history, q, system, **k: calls.append((q, system)) or "PLAN.")
    monkeypatch.setattr(nv, "portfolio_context", lambda *a: "This person's watchlist: Bitcoin")
    import signal_groups_inspector as gi

    monkeypatch.setattr(gi, "saved_configs", lambda supabase: ([], None))
    db = _DB()
    snap = _snap()
    assert nv.passage_plan(_St, db, "u1", {}, snap) == "PLAN."
    assert nv.passage_plan(_St, db, "u1", {}, snap) == "PLAN." and len(calls) == 1     # the second read is the logbook
    q, system = calls[0]
    assert "⚓ Conditions" in q and "Expectation" in q and "No buy or sell" in q
    assert "Tides readings" in system[1] and "Bitcoin" in system[1]
    row = db.rows[0]
    assert row["kind"] == "passage_plan" and row["readings"]["tide"] == snap["tide"]["label"]


def test_an_answer_that_runs_out_of_room_is_continued(monkeypatch):
    replies = [{"content": [{"type": "text", "text": "the tide changes to slack only if the score stays above"}],
                "stop_reason": "max_tokens"},
               {"content": [{"type": "text", "text": " -0.20 for 5 closes."}], "stop_reason": "end_turn"}]
    sent = []

    class R:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    def post(url, timeout, headers, data):
        sent.append(json.loads(data))
        return R(replies[len(sent) - 1])

    monkeypatch.setattr(advisor, "api_key", lambda: "k")
    out = advisor.ask([], "plan", ("a", "b"), post=post, max_tokens=50)
    assert out == "the tide changes to slack only if the score stays above -0.20 for 5 closes."
    assert sent[1]["messages"][-1]["role"] == "assistant"          # it carried on from its own words


def test_a_plan_cut_mid_sentence_is_written_again():
    assert nv.complete("**🔭 Things to watch**\n- Expectation: the tide holds for 5 closes.")
    assert not nv.complete("- **Expectation:** the tide changes to slack only if the score stays above")
