from datetime import datetime, timezone
from pathlib import Path

import briefing
import briefing_audio


def test_settings_defaults_and_cleaning():
    b = briefing.settings_of({"digest_tz": "Asia/Bangkok", "briefing": {"minutes": 7, "sections": ["bogus", "events"],
                                                                         "voice": "nope", "hour": 30}})
    assert b["zone"] == "Asia/Bangkok" and b["minutes"] == 5 and b["sections"] == ["events"]
    assert b["voice"] == "bf_emma" and b["hour"] == 23 and b["on"] is False


def test_due_by_hour_in_the_members_zone_and_on_request():
    now = datetime(2026, 11, 20, 23, 30, tzinfo=timezone.utc)            # 06:30 in Bangkok on the 21st
    s = {"briefing": {"on": True, "hour": 6, "zone": "Asia/Bangkok", "token": "x"}}
    assert briefing.due(s, now)
    assert not briefing.due({**s, "briefing_state": {"made": "2026-11-21"}}, now)
    assert not briefing.due({"briefing": {**s["briefing"], "hour": 7}}, now)
    assert briefing.due({"briefing": {"on": False}, "briefing_state": {"requested": "2026-11-21T00:00:00"}}, now)


def test_watch_assets_picks_and_caps():
    prefs = {"crypto_watchlist": {"bitcoin": "Bitcoin", "solana": "Solana"}, "stock_watchlist": {"AAPL": "Apple"}}
    assert [a[1] for a in briefing.watch_assets(prefs, [])] == ["bitcoin", "solana", "AAPL"]
    assert [a[1] for a in briefing.watch_assets(prefs, ["Stock|AAPL"])] == ["AAPL"]


def test_prompt_keeps_section_order_and_skips_empty_ones():
    b = briefing.settings_of({"briefing": {"sections": ["events", "markets", "funnels"], "minutes": 2}})
    facts = {"markets": [{"market": "crypto", "score_0_to_100": 40, "summary": "Fear."}], "events": [], "funnels": []}
    system, messages = briefing.prompt(facts, b, datetime(2026, 11, 20))
    assert "about 300 words" in system and "shipping forecast" in system
    assert '"sections_in_order": ["markets"]' in messages[0]["content"]


def test_plain_script_and_cleaning():
    facts = {"markets": [{"market": "crypto", "score_0_to_100": 41.6, "summary": "Cautious."}],
             "watchlist": [{"name": "Bitcoin", "change_1d": -2.34, "news_sentiment_0_to_100": 38}],
             "events": [{"what": "Fed rate decision", "when_utc": "Wednesday 10 December, 19:00"}]}
    text = briefing.plain_script(facts, briefing.settings_of({}), datetime(2026, 11, 20))
    assert text.startswith("This is the Angstrom Signals morning forecast for Friday 20 November")
    assert "-2.3 percent" in text and "not advice" in text
    assert briefing.clean("**Hi** 🚀 see https://x.y #now") == "Hi see now"


def test_script_falls_back_without_an_ai(monkeypatch):
    import ai_providers

    monkeypatch.setattr(ai_providers, "available", lambda p: False)
    monkeypatch.setattr(ai_providers, "app_choice", lambda db, use: None)
    text, who = briefing.write_script(None, {"events": [{"what": "CPI", "when_utc": "Tue"}]},
                                      briefing.settings_of({}), datetime(2026, 11, 20))
    assert who == "template" and "CPI" in text


def test_feed_is_valid_rss():
    import xml.etree.ElementTree as ET

    xml = briefing.feed_xml("https://x.supabase.co", "tok", [{"day": "2026-11-20", "label": "Friday 20 November 2026",
                                                              "pub": "Fri, 20 Nov 2026 06:00:00 +0000",
                                                              "url": "https://x/a.mp3", "bytes": 10, "seconds": 120,
                                                              "summary": "A & B"}])
    root = ET.fromstring(xml)
    item = root.find("channel/item")
    assert item.find("enclosure").get("type") == "audio/mpeg" and "A & B" in item.find("description").text


def test_chunks_and_mix_command(tmp_path):
    parts = briefing_audio.chunks("One. " * 200, limit=100)
    assert all(len(p) <= 100 for p in parts) and "".join(parts).count("One.") == 200
    cmd = briefing_audio.mix_command(Path("v.wav"), Path("o.mp3"), 120.0, theme=tmp_path / "none.mp3",
                                     bed=tmp_path / "none.mp3")
    assert "amix=inputs=1" in " ".join(cmd) and cmd[-1] == "o.mp3"


def test_weather_from_market_mood():
    assert briefing.weather({"markets": [{"score_0_to_100": 70}, {"score_0_to_100": 66}]}) == "sunny"
    assert briefing.weather({"markets": [{"score_0_to_100": 30}]}) == "stormy"
    assert briefing.weather({"markets": [{"score_0_to_100": 60}], "tide": ["Storm warning: CPI"]}) == "rough"
    assert briefing.weather({}) == "changeable"
