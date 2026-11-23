"""🎬 The daily forecast video's running order and script plumbing (no rendering here)."""
import json
import random
from datetime import datetime

import daily_video as dv

CAPS = ("welcome", "weather", "sign_story", "sign_tides", "sign_equities", "sign_crypto", "sign_horizon", "signoff")


def _caps(kinds):
    return {k: {"file": f"{k}.mp4", "seconds": 3.0} for k in kinds}


def _narr(kinds):
    return {k: {"file": f"{k}.wav", "seconds": 5.0} for k in kinds}


def test_weekday_order_has_the_story_and_equities():
    segs = dv.timeline(_caps(CAPS), _narr(("date", "story", "tides", "equities", "crypto", "horizon", "close")))
    kinds = [s["kind"] for s in segs]
    assert kinds[:5] == ["welcome", "date", "weather", "sign_story", "story"]
    assert "equities" in kinds and kinds[-2:] == ["signoff", "close"]
    assert all(b["start"] > a["end"] for a, b in zip(segs, segs[1:]))


def test_weekend_drops_equities_and_greets_the_weekend():
    day = datetime(2026, 11, 21)                       # a Saturday
    assert day.weekday() == 5 and "equities" not in dv.sections_for(day)
    clips = dict(dv.captain_clips("stormy", random.Random(1), weekend=True))
    assert "sign_equities" not in clips and clips["welcome"].startswith("cap_welcome_weekend_")
    narr = {k: v for k, v in _narr(("date", "story", "tides", "crypto", "horizon", "close")).items()}
    segs = dv.timeline(_caps(clips), narr)
    assert "equities" not in [s["kind"] for s in segs] and "sign_equities" not in [s["kind"] for s in segs]
    assert "stock markets are shut" in dv.system_prompt(dv.sections_for(day), True)


def test_template_story_picks_the_biggest_mover():
    facts = {"key_markets": [{"name": "S&P 500 (the SPY fund)", "change_1d": -0.5}],
             "cryptos": [{"name": "Bitcoin", "change_1d": 1.0}, {"name": "Solana", "change_1d": -6.2}]}
    out = dv._template(facts)
    assert out["story"]["asset"] == "Solana" and "6.2" in out["story"]["text"]


def test_ai_sections_need_a_story():
    reply = json.dumps({"headline": "h", "story": {"title": "t", "text": "x y", "asset": "Bitcoin"},
                        "tides": "a", "equities": "b", "crypto": "c", "horizon": "d"})

    class DB:
        pass

    import ai_providers
    old = ai_providers.available, ai_providers.app_choice
    ai_providers.available, ai_providers.app_choice = (lambda p: True), (lambda db, use: "grok")
    try:
        got, who = dv.write_sections(DB(), {}, chat=lambda *a, **k: (reply, True))
        assert who == "grok" and got["story"]["asset"] == "Bitcoin"
        bad = json.dumps({"headline": "h", "tides": "a", "equities": "b", "crypto": "c", "horizon": "d"})
        got, who = dv.write_sections(DB(), {"cryptos": [{"name": "Ether", "change_1d": 3.0}]},
                                     chat=lambda *a, **k: (bad, True))
        assert who == "template" and got["story"]["asset"] == "Ether"
    finally:
        ai_providers.available, ai_providers.app_choice = old


def test_fear_index_rises_are_bad_news():
    facts = {"key_markets": [{"name": "Fear (VIX)", "value": 29.0, "change_7d": 9.0, "unit_of_changes": "points"},
                             {"name": "Gold", "value": 3500.0, "change_7d": -8.0}], "cryptos": []}
    spec = dv.graphics_data(facts, {"headline": "h", "story": {"title": "t", "asset": "Gold"}}, datetime(2026, 11, 20),
                            load=lambda *a: {"candles": None})
    inv = {c["name"]: c["inverse"] for c in spec["currents"]}
    assert inv == {"Fear (VIX)": True, "Gold": False}
    assert spec["story"]["asset"]["name"] == "Gold" and spec["story"]["asset"]["value"] == 3500.0


def test_presenter_is_a_weighted_daily_surprise_with_the_captain_as_fallback(tmp_path):
    from datetime import timedelta

    days = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(2000)]
    assert {dv.presenter_for(d, tmp_path) for d in days} == {"cap"}       # nobody else's clips yet: the captain
    (tmp_path / "mate_signoff_1_1.mp4").write_bytes(b"")
    assert {dv.presenter_for(d, tmp_path) for d in days[:200]} == {"cap"}  # one clip is not a set
    for who in ("mate", "nav", "deck", "cat", "cook", "rat", "admiral"):
        for line in dv.SET_LINES:
            (tmp_path / f"{who}_{line}_1_1.mp4").write_bytes(b"")
    picks = [dv.presenter_for(d, tmp_path) for d in days]
    share = {w: picks.count(w) / len(picks) for w in dv.CHANCES}
    for who, chance in dv.CHANCES.items():
        assert abs(share[who] - chance) < 0.04, (who, share[who])
    assert dv.presenter_for(days[5], tmp_path) == dv.presenter_for(days[5], tmp_path)   # a re-made day keeps it
    assert dv.presenter_for(days[5], tmp_path, override="deck") == "deck"
    clips = dict(dv.captain_clips("fair", random.Random(2), who="deck"))
    assert all(c.startswith("deck_") for c in clips.values())


def test_easter_and_special_guests(tmp_path):
    assert dv.easter(2027) == (3, 28) and dv.easter(2026) == (4, 5)
    xmas = datetime(2026, 12, 25)
    assert dv.guest_for(xmas, {}, tmp_path) is None                     # no Father Christmas clips yet
    for k in ("welcome", "signoff"):
        (tmp_path / f"santa_{k}_1_1.mp4").write_bytes(b"")
    assert dv.guest_for(xmas, {}, tmp_path) == "santa"
    fed = {"events": [{"what": "Fed · December meeting", "when_utc": "Wednesday 09 December, 19:00"}]}
    assert dv.guest_for(datetime(2026, 12, 9), fed, None) == "neptune"
    assert dv.guest_for(datetime(2026, 12, 8), fed, None) is None
    assert dv.guest_for(datetime(2027, 3, 28), {}, None) == "bunny"


def test_cameo_titles_reach_the_badge():
    caps = _caps(CAPS)
    caps["welcome"]["title"] = "Father Christmas"
    segs = dv.timeline(caps, _narr(("date", "story", "tides", "equities", "crypto", "horizon", "close")))
    assert segs[0]["title"] == "Father Christmas" and "title" not in segs[2]


def test_the_cat_only_with_a_whole_set(tmp_path):
    for line in dv.SET_LINES:
        (tmp_path / f"cat_{line}_1_1.mp4").write_bytes(b"")
    days = [datetime(2027, 1, d) for d in range(1, 32)] + [datetime(2027, 2, d) for d in range(1, 29)]
    cats = sum(dv.presenter_for(d, tmp_path) == "cat" for d in days)
    assert 0 < cats < 15                                                  # now and then, not every day


def test_pick_look_uses_a_second_look_only_when_it_exists(tmp_path):
    import random
    import daily_video as dv
    (tmp_path / "neptune_welcome_1_1.mp4").write_bytes(b"x")
    assert dv.pick_look(tmp_path, "neptune_welcome_1_1.mp4", random.Random(1)) == "neptune_welcome_1_1.mp4"
    (tmp_path / "neptune_welcome_1_2.mp4").write_bytes(b"x")
    seen = {dv.pick_look(tmp_path, "neptune_welcome_1_1.mp4", random.Random(i)) for i in range(20)}
    assert seen == {"neptune_welcome_1_1.mp4", "neptune_welcome_1_2.mp4"}
    assert dv.pick_look(None, "cap_welcome_1_1.mp4", random.Random(1)) == "cap_welcome_1_1.mp4"


def test_video_due_after_the_asia_edition_and_only_once(monkeypatch):
    from datetime import datetime, timezone

    import briefing
    import daily_video as dv
    import run_briefings as rb
    now = datetime(2026, 11, 21, 22, 0, tzinfo=timezone.utc)          # after the 21:30 UTC Asia & Europe edition
    _at, eid = briefing.edition_slot("east", now)
    monkeypatch.setattr(rb, "_meta", lambda db, token: {})
    assert dv.video_due(None, now) == ""                                 # the forecast isn't made yet
    monkeypatch.setattr(rb, "_meta", lambda db, token: {eid: {"made_at": now.isoformat()}})
    monkeypatch.setattr(dv, "videos_meta", lambda db: {})
    assert dv.video_due(None, now) == eid[:10]
    monkeypatch.setattr(dv, "videos_meta", lambda db: {eid[:10]: {}})
    assert dv.video_due(None, now) == ""


def test_figures_cover_the_same_week_and_the_mood_matches_the_app():
    """Feedback 23 Nov 2026: the line is the last 7 days (hourly), a share's week is 5 trading days, and the mood
    gauge shows the app's -100..+100 number and words."""
    import pandas as pd

    import briefing

    asked = []

    def load(kind, aid, interval, rng):
        asked.append((interval, rng))
        return {"candles": pd.DataFrame({"close": [float(i) for i in 1 + pd.RangeIndex(20)], "forming": False})}
    assert len(dv._spark(load, "crypto", "bitcoin")) == 20 and asked == [("1h", "7D")]
    closes = list(range(100, 110))                     # 10 daily closes
    daily = lambda *a: {"candles": pd.DataFrame({"close": [float(c) for c in closes], "forming": False})}  # noqa: E731
    assert briefing._candle_moves("equity", "SPY", daily)["change_7d"] == round((109 / 104 - 1) * 100, 2)
    assert briefing._candle_moves("crypto", "bitcoin", daily)["change_7d"] == round((109 / 102 - 1) * 100, 2)
    assert briefing.news_mood(43) == {"news_mood": -14, "news_mood_words": "mildly bearish"}
    assert briefing.mood_line({"market": "crypto", **briefing.news_mood(43)}) == \
        "News about the crypto market reads mildly bearish, minus 14 on a scale of minus 100 to plus 100."
    facts = {"markets": [{"market": "crypto", "score_0_to_100": 43, **briefing.news_mood(43)}], "cryptos": []}
    spec = dv.graphics_data(facts, {"headline": "h", "story": {}}, datetime(2026, 11, 23), load=load)
    assert spec["crypto_mood"] == {"value": -14, "words": "mildly bearish"}
    assert "score_0_to_100" not in str(briefing.for_ai(facts)["markets"])


def test_moves_name_their_session_and_today_is_sent_back():
    """Feedback 23 Nov 2026: on a Monday morning the S&P 500's move is Friday's, never "today"."""
    from datetime import timezone

    import ai_providers
    import briefing

    monday = datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc)
    assert briefing.one_day_covers("equity", "2026-11-20", monday) == \
        "the US trading session of Friday 20 November (not today)"
    assert "all of Sunday UTC" in briefing.one_day_covers("crypto", None, monday)
    assert briefing.move_span({"session_day": "2026-11-20"}) == "on Friday"
    assert briefing.move_span({"name": "Bitcoin"}) == "over the last 24 hours"
    assert briefing.session_word("2026-11-20") == "Fri"

    good = {"headline": "Up on Friday", "story": {"title": "t", "text": "Ether rose over the last 24 hours.", "asset": ""},
            "tides": "x", "equities": "On Friday the S&P 500 rose.", "crypto": "y", "horizon": "z"}
    bad = {**good, "equities": "The S&P 500 is up today."}
    replies = [json.dumps(bad), json.dumps(good)]
    old = ai_providers.available, ai_providers.app_choice
    ai_providers.available, ai_providers.app_choice = (lambda p: True), (lambda db, k: "grok")
    try:
        got, who = dv.write_sections(None, {}, chat=lambda *a, **k: replies.pop(0))
        assert who != "template" and got["equities"] == "On Friday the S&P 500 rose." and not replies
    finally:
        ai_providers.available, ai_providers.app_choice = old


def test_the_admiral_comes_on_big_days_and_the_new_crew_moves(tmp_path):
    """23 Nov 2026: the Admiral is likelier on CPI and jobs-report days; the Cook's galley sways, the Rat's candle
    flickers; the Rat's candlelit tag follows his sign-off."""
    from datetime import timedelta

    for who in ("mate", "nav", "deck", "cat", "cook", "rat", "admiral"):
        for line in dv.SET_LINES:
            (tmp_path / f"{who}_{line}_1_1.mp4").write_bytes(b"")
    days = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(600)]
    cpi = lambda d: {"events": [{"what": "CPI (inflation)", "when_utc": d.strftime("%A %d %B, 13:30")}]}   # noqa: E731
    share = sum(dv.presenter_for(d, tmp_path, facts=cpi(d)) == "admiral" for d in days) / len(days)
    assert 0.3 < share < 0.5
    assert sum(dv.presenter_for(d, tmp_path) == "admiral" for d in days) / len(days) < 0.07
    assert "rotate=" in dv.clip_effect("cook_welcome_1_1.mp4", 600, 812)
    assert "eq=brightness" in dv.clip_effect("ratd_tag_1_1.mp4", 600, 812)
    assert "rotate" not in dv.clip_effect("admiral_welcome_1_1.mp4", 600, 812)
    assert dv.clip_effect("nav_signoff_1_1.mp4", 600, 812).startswith("crop=iw*0.72")       # above the wheel
    caps = {k: {"file": f"{k}.mp4", "seconds": 2.0} for k in ("welcome", "weather", "signoff", "tag")}
    narr = {k: {"file": f"{k}.wav", "seconds": 2.0} for k in ("date", "close")}
    kinds = [s["kind"] for s in dv.timeline(caps, narr)]
    assert kinds.index("tag") == kinds.index("signoff") + 1 and kinds[-1] == "close"


def test_speech_seconds_cuts_a_silent_tail(tmp_path):
    """A presenter clip padded with silent mouth movement ends shortly after the last word."""
    import subprocess
    clip = tmp_path / "admiral_signoff_1_1.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=5",
                    "-f", "lavfi", "-i", "sine=f=300:d=3", "-af", "apad=whole_dur=5", "-t", "5",
                    "-c:v", "libx264", "-c:a", "aac", str(clip)], check=True)
    secs = dv.speech_seconds(clip)
    assert 3.0 < secs < 3.6


def test_speech_seconds_keeps_a_clip_that_talks_to_the_end(tmp_path):
    import subprocess
    clip = tmp_path / "cap_welcome_1_1.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=3",
                    "-f", "lavfi", "-i", "sine=f=300:d=3", "-t", "3", "-c:v", "libx264", "-c:a", "aac", str(clip)],
                   check=True)
    assert abs(dv.speech_seconds(clip) - dv.duration(clip)) < 0.01


def test_bloopers_about_one_day_in_four_never_with_the_cat():
    from datetime import timedelta
    start = datetime(2027, 1, 1)
    sections = {"story": {}, "tides": {}, "equities": {}, "crypto": {}}
    picks = [dv.blooper_for(start + timedelta(days=i), "cap", None, sections) for i in range(400)]
    share = sum(p is not None for p in picks) / len(picks)
    assert 0.18 < share < 0.32
    assert all(p["after"] in dv.BLOOPER_AFTER for p in picks if p)
    cat_days = [dv.blooper_for(start + timedelta(days=i), "cat", None, sections) for i in range(400)]
    assert all(p["file"] in ("blooper_cat_chase_1.mp4", "blooper_cook_wave_1.mp4") for p in cat_days if p)


def test_blooper_plays_between_sections_and_the_cook_reveal_at_the_end():
    caps = {k: {"file": f"cook_{k}.mp4", "seconds": 2.0} for k in ("welcome", "weather", "sign_story", "sign_tides",
                                                                  "sign_crypto", "sign_horizon", "signoff")}
    caps["reveal"] = {"file": dv.COOK_REVEAL, "seconds": 5.0}
    caps["blooper"] = {"file": "blooper_rat_pocket_1.mp4", "seconds": 5.0, "after": "tides", "title": "Blooper",
                       "caption": ["Outtake", "Meanwhile, in the galley"]}
    narr = {k: {"file": f"{k}.wav", "seconds": 3.0} for k in ("date", "story", "tides", "crypto", "horizon", "close")}
    kinds = [s["kind"] for s in dv.timeline(caps, narr)]
    assert kinds[kinds.index("tides") + 1] == "blooper"
    assert kinds[-2:] == ["reveal", "close"]
    seg = next(s for s in dv.timeline(caps, narr) if s["kind"] == "blooper")
    assert seg["title"] == "Blooper" and seg["caption"][0] == "Outtake"


def test_wave_bloopers_only_in_rough_weather():
    from datetime import timedelta
    sections = {"story": {}, "tides": {}, "crypto": {}}
    calm = [dv.blooper_for(datetime(2027, 1, 1) + timedelta(days=i), "cap", None, sections, "sunny") for i in range(400)]
    assert not any(p and "wave" in p["file"] for p in calm)
    rough = [dv.blooper_for(datetime(2027, 1, 1) + timedelta(days=i), "cap", None, sections, "stormy") for i in range(400)]
    assert any(p and "wave" in p["file"] for p in rough)
