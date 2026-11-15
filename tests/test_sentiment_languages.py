"""🌐 AI sentiment text in the languages accounts use (15 Nov 2026): asked for in the same call, kept under "tr",
shown in the visit's language, and never at the cost of the English score."""

import json

import sentiment as se

HEADS = [{"title": f"Bitcoin story {i}", "source": "S", "id": f"id{i}"} for i in range(1, 5)]


class _Reply:
    status_code = 200

    def __init__(self, content):
        self.payload = {"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}

    def json(self):
        return self.payload


def _reply(with_tr=True):
    body = {"articles": [{"index": i, "score": 60, "note": f"note {i}"} for i in range(1, 5)],
            "summary": "Two sentences.", "positive": "Good.", "negative": "Bad.", "drivers": ["ETF flows"]}
    if with_tr:
        body["tr"] = {"th": {"summary": "สรุป", "positive": "ดี", "negative": "ไม่ดี", "drivers": ["กระแสเงิน ETF"],
                             "notes": {"1": "บันทึก 1", "2": "บันทึก 2"}},
                      "xx": {"summary": "not asked for"}}
    return _Reply(json.dumps(body))


def _grok(monkeypatch, replies, seen):
    monkeypatch.setattr(se, "_api_key", lambda: "k")
    monkeypatch.setattr(se, "_KEY_REJECTED", False)
    monkeypatch.setattr(se, "scoring_provider", lambda: "grok")

    def post(key, prompt, attempt, structured=True, langs=()):
        seen.append((prompt, tuple(langs)))
        return next(replies)
    monkeypatch.setattr(se, "_post_grok", post)


def test_only_used_languages_are_asked_for_and_english_is_skipped(monkeypatch):
    se.set_languages({"en", "th", None})
    try:
        assert se.languages() == ("th",)
        seen = []
        _grok(monkeypatch, iter([_reply()]), seen)
        report = se._summarize("q-lang", HEADS)
        assert '"tr"' in seen[0][0] and "th (Thai)" in seen[0][0] and seen[0][1] == ("th",)
        assert report["ok"] and report["tr"] == {"th": {"summary": "สรุป", "positive": "ดี", "negative": "ไม่ดี",
                                                        "drivers": ["กระแสเงิน ETF"]}}
        assert report["headlines"][0]["tr"] == {"th": "บันทึก 1"} and "tr" not in report["headlines"][2]
        assert report["summary"] == "Two sentences."                # the English stays the English
    finally:
        se.set_languages(())


def test_no_languages_means_the_prompt_is_unchanged(monkeypatch):
    seen = []
    _grok(monkeypatch, iter([_reply(with_tr=False)]), seen)
    report = se._summarize("q-nolang", HEADS)
    assert report["ok"] and "tr" not in report and '"tr"' not in seen[0][0] and seen[0][1] == ()


def test_a_failed_translated_reply_falls_back_to_english(monkeypatch):
    se.set_languages(["th"])
    try:
        seen = []
        bad = [_Reply("not json")] * len(se._MODELS)
        _grok(monkeypatch, iter(bad + [_reply(with_tr=False)]), seen)
        report = se._summarize("q-fallback", HEADS)
        assert report["ok"] and report["score"] == 60 and "tr" not in report
        assert seen[-1][1] == () and '"tr"' not in seen[-1][0]
    finally:
        se.set_languages(())


def test_localised_shows_the_visit_language_and_falls_back():
    report = {"ok": True, "summary": "S", "positive": "P", "negative": "N", "drivers": ["d"],
              "tr": {"th": {"summary": "ส", "drivers": ["ด"]}},
              "headlines": [{"id": "a", "note": "n1", "tr": {"th": "น1"}}, {"id": "b", "note": "n2"}],
              "gauges": [{"title": "G", "items": [{"name": "VIX", "note": "calm", "tr": {"th": "สงบ"}}]}]}
    th = se.localised(report, "th")
    assert th["summary"] == "ส" and th["positive"] == "P" and th["drivers"] == ["ด"]
    assert [h["note"] for h in th["headlines"]] == ["น1", "n2"] and th["gauges"][0]["items"][0]["note"] == "สงบ"
    assert report["summary"] == "S" and report["headlines"][0]["note"] == "n1"     # the stored report is untouched
    assert se.localised(report, "ja")["summary"] == "S" and se.localised(report, "en") is report
    assert se.localised(None, "th") is None


def test_a_report_missing_a_new_language_is_asked_again(monkeypatch):
    heads = [dict(h) for h in HEADS]
    previous = {"ok": True, "model": "m", "score": 55, "headlines": [dict(h, score=55) for h in heads]}
    monkeypatch.setattr(se, "gather_headlines", lambda q, market=False, limit=8: ([dict(h) for h in heads], {}))
    calls = []
    monkeypatch.setattr(se, "_summarize", lambda *a, **k: calls.append(1) or {"ok": True, "score": 60, "model": "m",
                                                                              "headlines": [dict(h, score=60) for h in heads]})
    se.set_languages(["th"])
    try:
        se.analyze_market_sentiment("q-newlang", True, force=True, previous=previous)
        assert calls                                        # Thai was missing: asked again
        calls.clear()
        previous["tr"] = {"th": {"summary": "ส"}}
        report = se.analyze_market_sentiment("q-newlang2", True, force=True, previous=previous)
        assert not calls and report["reused_report"]       # has Thai: reused as before
    finally:
        se.set_languages(())


def test_reused_notes_keep_their_translations():
    previous = {"ok": True, "model": "m", "headlines": [{"id": "id1", "score": 80, "note": "old", "tr": {"th": "เก่า"}}]}
    report = {"ok": True, "model": "m", "score": 50,
              "headlines": [{"id": "id1", "score": 30, "note": "new", "tr": {"th": "ใหม่", "ja": "新"}}]}
    se.reuse_scores(report, previous)
    row = report["headlines"][0]
    assert row["note"] == "old" and row["tr"] == {"th": "เก่า", "ja": "新"}
