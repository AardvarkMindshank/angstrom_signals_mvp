"""Checks on every market sentiment refresh (24 Nov 2026): out-of-date readings, scores that contradict their own
sentence, translations that change the meaning, and readings measured the way their labels say."""
import json
from datetime import date

import market_gauges as mg
import sentiment


def test_readings_older_than_their_publishing_delay_are_out_of_date():
    today = date(2026, 11, 24)                                         # a Tuesday
    assert not mg.is_stale({"published": "2026-11-20", "cadence": "day"}, today)      # Friday: 2 working days
    assert mg.is_stale({"published": "2026-11-17", "cadence": "day"}, today)
    assert not mg.is_stale({"published": "2026-10-01", "cadence": "month"}, today)   # a month's survey, 54 days
    assert not mg.is_stale({"published": "2026-09-01", "cadence": "month"}, today)   # money supply lags 2 months
    assert mg.is_stale({"published": "2026-08-01", "cadence": "month"}, today)
    assert not mg.is_stale({"published": ""}, today)
    groups = mg.mark_stale([{"title": "g", "items": [{"name": "old", "published": "2026-11-10"},
                                                     {"name": "new", "published": "2026-11-23"}]}], today)
    assert [i.get("stale") for i in groups[0]["items"]] == [True, None]
    assert "old" not in mg.gauge_brief(groups) and "new" in mg.gauge_brief(groups)


def test_spy_moves_from_the_prior_close_and_counts_read_as_one():
    body = {"results": [{"c": 690.0, "t": 1763683200000}, {"c": 722.29, "t": 1763942400000}]}
    item = mg._polygon_items(mg._spy_from_range(body))[0]
    assert item["detail"].startswith("Up 4.7% from the prior close")
    active = mg._alpha_items({"kind": "active", "higher": 15, "lower": 5, "date": "2026-11-23"})
    assert len(active) == 1 and active[0]["value"] == "15 ▲ · 5 ▼"


def _report():
    return {"ok": True, "summary": "Stocks rose.", "tr": {"th": {"summary": "หุ้นร่วง"}},
            "headlines": [{"title": "Nasdaq jumps 7%", "note": "Stocks rallied.", "score": 85.0},
                          {"title": "Fewer stocks fell", "note": "Only 5 falling is mildly bullish.", "score": 35.0,
                           "tr": {"th": "บวกเล็กน้อย"}}],
            "gauges": [{"title": "g", "items": [{"name": "VIX", "value": "26", "note": "Fear is high.",
                                                 "score": 70.0}]}]}


def test_a_score_that_contradicts_its_sentence_is_rescored_or_left_out():
    answers = iter([
        json.dumps({"directions": {"0": "up", "1": "up", "2": "down"}, "wrong_facts": [],
                    "bad_translations": ["th:summary"]}),
        json.dumps({"items": {"1": {"note": "Few falling is mildly bullish.", "score": 60},
                              "2": {"note": "x", "score": 65}}}),
    ])
    report = sentiment.review_report(_report(), chat=lambda ask: next(answers))
    rows = report["headlines"] + report["gauges"][0]["items"]
    assert rows[0]["score"] == 85.0                     # agreed: untouched
    assert rows[1]["score"] == 60.0                     # rescored in line with its sentence
    assert rows[2]["score"] is None                     # still contradicts: left out of the average
    assert "summary" not in report["tr"]["th"]          # the wrong translation goes; the English shows
    assert report["checks"] == {"rows": 3, "rescored": 1, "unscored": 1, "translations": 2,
                                "translations_dropped": 1, "wrong_facts": 0}


def test_a_note_that_contradicts_its_own_facts_is_rewritten():
    report = {"ok": True, "headlines": [], "gauges": [{"title": "g", "items": [
        {"name": "CBOE VIX", "value": "26.62", "detail": "Down 9.27 points from the prior day",
         "note": "Sharp VIX spike reflects heightened risk.", "score": 20.0, "tr": {"th": "x"}}]}]}
    answers = iter([json.dumps({"directions": {"0": "down"}, "wrong_facts": [0], "bad_translations": []}),
                    json.dumps({"items": {"0": {"note": "Fear eased as the VIX fell sharply, though it is still high.",
                                                "score": 55}}})])
    sentiment.review_report(report, chat=lambda ask: next(answers))
    item = report["gauges"][0]["items"][0]
    assert item["score"] == 55.0 and item["note"].startswith("Fear eased") and "tr" not in item


def test_no_answer_changes_nothing():
    report = sentiment.review_report(_report(), chat=lambda ask: "busy")
    assert report["headlines"][1]["score"] == 35.0 and report["checks"].get("skipped")


def test_the_prior_day_is_the_close_before_the_latest_day():
    day = 86400
    t0 = 1795392000                                                      # 23 Nov 2026 00:00 UTC
    result = {"timestamp": [t0 - 4 * day + 50000, t0 - 3 * day + 50000, t0 + 50000],
              "indicators": {"quote": [{"close": [28.5, 35.89, 26.62]}]}}
    assert mg._close_before(result, "2026-11-23") == 35.89
