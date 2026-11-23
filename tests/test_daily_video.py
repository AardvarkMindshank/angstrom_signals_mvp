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
    for who in ("mate", "nav", "deck", "cat"):
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
