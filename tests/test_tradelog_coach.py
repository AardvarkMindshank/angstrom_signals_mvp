"""Weekly review guardrails (tradelog_coach.py): facts only, no advice, every claim tied to listed trades."""

import json
from datetime import date
from zoneinfo import ZoneInfo

import tradelog_coach as coach

ZONE = ZoneInfo("Asia/Bangkok")


def _trips():
    out = []
    for i in range(12):
        day = 10 + (i % 6)
        out.append({"id": i + 1, "name": f"Asset {i % 3}", "asset_class": "stocks", "direction": "long",
                    "platform": "etoro", "copied": i == 11,
                    "opened_at": f"2026-11-{day - 2:02d}T03:00:00Z", "closed_at": f"2026-11-{day:02d}T03:00:00Z",
                    "net_result_usd": 10.0 if i % 3 else -6.0, "result_pct": 2.0, "invested_usd": 500.0,
                    "leverage": 1})
    return out


def _fact():
    return coach.facts(_trips(), {(1, "entry"): {"regime": "trending_up", "trend": 30}},
                       coach.week_of(date(2026, 11, 22)), ZONE)


def test_the_week_is_the_last_finished_monday_to_sunday():
    assert coach.week_of(date(2026, 11, 22)) == (date(2026, 11, 9), date(2026, 11, 15))      # a Sunday
    assert coach.week_of(date(2026, 11, 23)) == (date(2026, 11, 16), date(2026, 11, 22))     # the Monday after


def test_facts_number_the_trades_and_leave_out_copied_ones():
    f = _fact()
    assert [t["id"] for t in f["trades"]] == [f"T{i}" for i in range(1, len(f["trades"]) + 1)]
    assert f["week_stats"]["trades"] == 11 and f["min_trades_for_a_pattern"] == 10
    assert "email" not in json.dumps(f) and "user_id" not in json.dumps(f)


GOOD = {"happened": "11 trades closed: 7 wins and 4 losses (T1, T2).",
        "pattern": "Your losing trades were held about as long as winners (T3, T4).",
        "question": "What made you close T1 when you did?", "cited": ["T1", "T2", "T3", "T4"]}


def test_a_clean_review_passes():
    assert coach.problems(GOOD, _fact()) == []


def test_advice_predictions_and_causes_are_rejected():
    f = _fact()
    for bad in ("You should buy more of Asset 1 (T1).", "Asset 2 will rise next week (T1).",
                "Set a stop at 5% below entry (T1).", "The trending regime caused your wins (T1).",
                "Consider selling Asset 0 (T2).", "I recommend going long (T1)."):
        assert coach.problems({**GOOD, "pattern": bad}, f), bad


def test_made_up_or_missing_citations_are_rejected():
    f = _fact()
    assert coach.problems({**GOOD, "happened": "A great week (T99).", "cited": ["T99"]}, f)
    assert coach.problems({"happened": "Fine.", "pattern": "Fine.", "question": "Why?", "cited": []}, f)


def test_one_retry_then_the_plain_summary():
    f = _fact()
    calls = []

    def chat_bad(system, msgs):
        calls.append(len(msgs))
        return json.dumps({**GOOD, "pattern": "You should buy now (T1)."})
    review = coach.write(f, "claude", chat=chat_bad)
    assert review["plain"] is True and calls == [1, 3]                 # asked twice, the second with the rules broken
    assert "11 trades closed" in review["happened"]


def test_a_good_answer_is_used_and_a_quiet_week_needs_no_ai():
    review = coach.write(_fact(), "claude", chat=lambda s, m: "Here you go: " + json.dumps(GOOD))
    assert review["plain"] is False and review["question"] == GOOD["question"]
    empty = coach.facts([], {}, coach.week_of(date(2026, 11, 22)), ZONE)
    assert coach.write(empty, "claude", chat=lambda s, m: 1 / 0)["happened"] == "No trades closed this week."


def test_the_ai_failing_falls_back_to_the_plain_summary():
    def broken(system, msgs):
        raise RuntimeError("provider down")
    assert coach.write(_fact(), "claude", chat=broken)["plain"] is True
