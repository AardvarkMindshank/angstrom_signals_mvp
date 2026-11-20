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


def test_script_from_the_ai_reply(monkeypatch):
    import ai_providers

    monkeypatch.setattr(ai_providers, "available", lambda p: True)
    monkeypatch.setattr(ai_providers, "app_choice", lambda db, use: "grok")
    words = "This is the Angstrom Signals morning forecast. " + "Calm seas. " * 40
    text, who = briefing.write_script(None, {}, briefing.settings_of({}), datetime(2026, 11, 20),
                                      chat=lambda *a, **k: (words + "\n\nFair winds.", True))
    assert who == "grok" and text.startswith("This is") and not text.startswith("(") and "True" not in text


def test_weather_counts_the_tide_and_the_sea():
    today = {"markets": [{"score_0_to_100": 46}, {"score_0_to_100": 44}], "conditions": {"tide": "out", "sea": "rough"}}
    assert briefing.weather(today) == "stormy"
    assert briefing.weather({"markets": [{"score_0_to_100": 60}], "conditions": {"tide": "in", "sea": "calm"}}) == "sunny"
    assert briefing.weather({"markets": [{"score_0_to_100": 50}], "conditions": {"tide": "slack", "sea": "moderate"}}) \
        == "changeable"


# ---- the Morning forecast's editions, and the spoken Passage Plan (20 Nov 2026)
from datetime import datetime as _dt, timezone as _tz


def test_edition_slots_date_the_morning_they_serve():
    now = _dt(2026, 11, 20, 22, 0, tzinfo=_tz.utc)               # just after the east edition's time
    at, eid = briefing.edition_slot("east", now)
    assert at == _dt(2026, 11, 20, 21, 30, tzinfo=_tz.utc) and eid == "2026-11-21-east"
    at, eid = briefing.edition_slot("west", now)
    assert at == _dt(2026, 11, 20, 10, 30, tzinfo=_tz.utc) and eid == "2026-11-20-west"


def test_editions_due_once_and_only_within_the_window():
    now = _dt(2026, 11, 20, 22, 0, tzinfo=_tz.utc)
    assert briefing.editions_due({}, now) == [("east", "2026-11-21-east")]      # west's window (8 h) has passed
    assert briefing.editions_due({"2026-11-21-east": {}}, now) == []
    morning = _dt(2026, 11, 20, 10, 45, tzinfo=_tz.utc)
    assert ("west", "2026-11-20-west") in briefing.editions_due({}, morning)


def test_newest_is_by_when_made():
    meta = {"2026-11-21-east": {"made_at": "2026-11-20T21:40:00+00:00"},
            "2026-11-20-west": {"made_at": "2026-11-20T10:40:00+00:00"}}
    assert briefing.newest(meta) == "2026-11-21-east"
    assert briefing.newest({}) == ""


def test_spoken_plan_keeps_the_words_and_says_the_headings():
    body = ("**⚓ Conditions** - Tide going out (risk-defensive), held 6 trading days.\n\n"
            "**🌦️ Weather on the route**\n- CPI on Wed: dollar +2.1%, score 62/100.\n\n"
            "**🔭 Things to watch** - Expectation: the tide holds 5 closes.")
    out = briefing.spoken_plan(body, _dt(2026, 11, 21))
    assert out.startswith("This is your Angstrom Signals Passage Plan for Saturday 21 November.")
    assert "First, the conditions. Tide going out (risk-defensive), held 6 trading days." in out
    assert "The weather on the route. CPI on Wed: dollar plus 2.1 percent, score 62 out of 100." in out
    assert "Things to watch. Expectation: the tide holds 5 closes." in out
    assert "*" not in out and "⚓" not in out and out.endswith("Fair winds.")


def test_general_facts_use_candles_when_no_stored_readings():
    import pandas as pd

    class Empty:
        def __getattr__(self, name):
            return self

        def __call__(self, *a, **k):
            return self

        @property
        def data(self):
            return []

        def execute(self):
            return self

    def load(kind, asset_id, interval, rng):
        closes = [100.0] * 7 + [110.0, 121.0]
        return {"candles": pd.DataFrame({"close": closes, "forming": [False] * 9})}

    facts = briefing.general_facts(Empty(), _dt(2026, 11, 20, 22, tzinfo=_tz.utc), load=load)
    names = [a["name"] for a in facts["key_markets"]]
    assert names[:2] == ["S&P 500 (the SPY fund)", "Nasdaq 100 (the QQQ fund)"]
    btc = facts["cryptos"][0]
    assert btc["name"] == "Bitcoin" and btc["change_1d"] == 10.0 and btc["change_7d"] == 21.0


def test_general_prompt_names_the_edition_and_sections():
    facts = {"markets": [{"market": "crypto", "score_0_to_100": 40}], "cryptos": [{"name": "Bitcoin"}],
             "conditions": {}}
    system, msgs = briefing.general_prompt(facts, "west", _dt(2026, 11, 20))
    assert "Americas edition" in system and "Asia" not in system
    assert "the top five coins" in msgs[0]["content"]


def test_digest_lists_the_listen_links():
    import digest

    _, page, plain = digest.render_digest([], [], {"digest_tz": "UTC"}, "https://app",
                                          listen=[("🌍 The Morning forecast", "https://x/general/a.mp3")])
    assert "https://x/general/a.mp3" in page and "🌍 The Morning forecast: https://x/general/a.mp3" in plain
