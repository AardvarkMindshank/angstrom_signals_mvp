"""Whole-market news (24 Nov 2026): several searches, price pages dropped, the day's most widely reported story
first, and the story of the day checked against the market's moves."""
import json
import time
from datetime import datetime, timezone

import sentiment


def _item(title, source, hours_ago, now):
    when = datetime.fromtimestamp(now - hours_ago * 3600, timezone.utc)
    return {"title": title, "source": source, "link": "https://example.com/" + title.replace(" ", "-"),
            "published": when.strftime("%a, %d %b %Y %H:%M:%S GMT")}


def test_the_widely_reported_story_of_the_day_comes_first(monkeypatch):
    now = time.time()
    feeds = {
        "a": [_item("Weekly market commentary", "BlackRock", 1, now),
              _item("Current price of Bitcoin for November 23, 2026", "Fortune", 2, now),
              _item("Nasdaq jumps 7% as Nvidia shares soar", "Financial Times", 5, now),
              _item("Stocks rally as Jensen Huang returns to Nvidia, Nasdaq jumps 7%", "Reuters", 4, now),
              _item("Market outlook for 2027 looks mixed", "Old Blog", 60, now)],
        "b": [_item("Nasdaq jumps 7 percent as Nvidia shares soar", "CNBC", 6, now),
              _item("Bank rings the Nasdaq opening bell", "Nasdaq", 3, now)],
    }
    monkeypatch.setattr(sentiment, "_fetch_raw", lambda q: feeds[q])
    rows, stats = sentiment.gather_market_news(("a", "b"), now=now)
    titles = [r["title"] for r in rows]
    assert stats["not_news"] == 2
    assert not any("price of Bitcoin" in t or "opening bell" in t for t in titles)
    assert "Nvidia" in titles[0] and rows[0].get("also_reported", 0) >= 1
    assert titles[-1] == "Market outlook for 2027 looks mixed"           # older than a day: last


def test_a_trillion_dollar_price_on_a_ceo_is_news():
    assert not sentiment.NOT_NEWS.search("Wall Street just put a $1 trillion price on Jensen Huang")
    assert sentiment.NOT_NEWS.search("ETH price at 6 PM CST on Nov 23, 2026")


def test_story_of_the_day_and_a_quiet_day():
    spec = sentiment.MOOD_SPECS["stock"]
    heads = [{"id": "x1", "title": "Weekly commentary", "source": "BlackRock", "link": "https://a"},
             {"id": "x2", "title": "Nasdaq jumps 7% as Nvidia shares soar", "source": "FT", "link": "https://b"}]
    moves = [{"name": "Nasdaq 100", "change_1d": 7.0, "day": "2026-11-23"}]
    seen = {}

    def chat(ask):
        seen["ask"] = ask
        return json.dumps({"index": 2, "why": "It reports the 7% jump.", "explains_moves": True})

    lead = sentiment.lead_story(spec, heads, moves, chat=chat)
    assert lead["id"] == "x2" and lead["title"].startswith("Nasdaq") and not lead.get("quiet")
    assert "Nasdaq 100 +7.00% on 2026-11-23" in seen["ask"]
    quiet = sentiment.lead_story(spec, heads, moves, chat=lambda a: json.dumps(
        {"index": 0, "why": "No single story drove crypto.", "explains_moves": False}))
    assert quiet["quiet"] and "title" not in quiet
    assert sentiment.lead_story(spec, heads, moves, chat=lambda a: "not json") is None


def test_the_why_line_is_shown_in_the_visit_language():
    report = {"ok": True, "headlines": [], "lead": {"why": "English.", "tr": {"de": "Deutsch."}}}
    assert sentiment.localised(report, "de")["lead"]["why"] == "Deutsch."
    assert sentiment.localised(report, "fr")["lead"]["why"] == "English."
