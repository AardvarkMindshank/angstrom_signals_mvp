"""The AI Navigator's tools (navigator_tools.py) and the look-up loop in advisor._ask."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import advisor  # noqa: E402
import navigator_tools as nt  # noqa: E402


class _St:
    session_state: dict = {}


class _Table:
    def __init__(self, db):
        self.db = db

    def upsert(self, row, **k):
        self.db.rows.append(row)
        return self

    def execute(self):
        return self


class _Db:
    def __init__(self):
        self.rows = []

    def table(self, name):
        assert name == "editor_drafts"
        return _Table(self)


def _box(db=None):
    return nt.ToolBox(_St(), db or _Db(), "me", [], {"crypto": {"ripple": "XRP"}, "stock": {"AAPL": "Apple"}})


def test_tool_definitions_are_well_formed():
    names = [t["name"] for t in nt.TOOLS]
    assert len(names) == len(set(names)) == 5
    for t in nt.TOOLS:
        assert t["input_schema"]["type"] == "object" and t["description"]
    json.dumps(nt.TOOLS)


def test_assets_resolve_from_the_watchlist_first():
    box = _box()
    assert box._resolve("xrp") == ("crypto", "ripple", "XRP")
    assert box._resolve("AAPL") == ("equity", "AAPL", "Apple")


def test_draft_set_checks_and_stores_a_new_set_draft():
    db = _Db()
    box = _box(db)
    out = box.run("draft_set", {
        "name": "Dip entry", "purpose": "Stoch RSI up from low with a big green dot",
        "lines": [{"signal": "osc.stoch_rsi", "field": "cross_up_from_low_ago", "op": "within", "value": 3},
                  {"signal": "sonar.markers", "field": "big_green_dot_ago", "op": "within", "value": 3}],
        "any_of": [[{"signal": "osc.wavetrend", "field": "zone", "op": "is", "value": "oversold"},
                    {"signal": "osc.wavetrend", "field": "turned_up_from_oversold", "op": "yes"}]]})
    got = json.loads(out)
    assert got["built"] is True, got
    row = db.rows[-1]
    assert row["kind"] == "set" and row["draft_key"] == "new" and len(row["body"]["standalone"]) == 3
    assert any("any" in line for line in row["body"]["lines"])
    assert box.notes == ["draft_set"]


def test_draft_set_refuses_unknown_signals_and_bad_values():
    box = _box()
    assert "unknown signal" in box.run("draft_set", {"name": "x", "lines": [
        {"signal": "made.up", "field": "", "op": "is", "value": "up"}]})
    bad = json.loads(box.run("draft_set", {"name": "x", "lines": [
        {"signal": "rsi.level", "field": "", "op": "gte", "value": 250}]}))
    assert bad["built"] is False and bad["problems"]


def test_soundings_results_and_tool_errors_are_plain_text():
    box = _box()
    got = json.loads(box.run("soundings_results", {"market": "crypto", "move": "rise"}))
    assert got["results"] and {"condition", "verdict", "later_lift"} <= set(got["results"][0])
    assert box.run("nope", {}).startswith("Unknown tool")
    assert "wrong inputs" in box.run("soundings_results", {"bogus": 1})


def test_the_navigator_loop_runs_tools_then_answers():
    calls = []

    class Reply:
        status_code = 200

        def __init__(self, data):
            self._data = data

        def json(self):
            return self._data

    def post(url, timeout, headers, data):
        body = json.loads(data)
        calls.append(body)
        if len(calls) == 1:
            return Reply({"stop_reason": "tool_use", "content": [
                {"type": "text", "text": "Let me look."},
                {"type": "tool_use", "id": "t1", "name": "soundings_results",
                 "input": {"market": "crypto", "move": "fall"}}]})
        return Reply({"stop_reason": "end_turn", "content": [{"type": "text", "text": "Here is what I found."}]})

    advisor.os.environ["ANTHROPIC_API_KEY"] = "test"
    try:
        answer = advisor.ask([], "what came before falls?", ("shared", "mine"), post=post, tools=_box())
    finally:
        del advisor.os.environ["ANTHROPIC_API_KEY"]
    assert answer == "Here is what I found."
    assert calls[0]["tools"] and "tool_choice" not in calls[0]
    second = calls[1]["messages"]
    assert second[-1]["content"][0]["type"] == "tool_result" and second[-1]["content"][0]["tool_use_id"] == "t1"
    assert second[-2]["role"] == "assistant"
