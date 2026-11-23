import social_post as s


def test_captions_fit_each_platform():
    words = "Sunday, the twenty-second of November. Rough Seas Fear Tide Runs Strong.\n\nBitcoin slid."
    c = s.captions("2026-11-22", {"presenter": "The Deckhand"}, words)
    assert "Rough Seas Fear Tide Runs Strong." in c["telegram"] and "The Deckhand" in c["telegram"]
    assert "Sun 22 Nov" in c["telegram"] and "not financial advice" in c["telegram"]
    assert len(c["x"]) <= 280 and len(c["threads"]) <= 500 and len(c["youtube_title"]) <= 100
    assert "Link in bio" in c["instagram"] and "#fyp" in c["tiktok"]


def test_a_platform_without_its_secrets_is_skipped(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert s.post_telegram("2026-11-22", {"telegram": "x"}, {"tall": "u", "tall_poster": "p"}).startswith("skipped")


def test_due_from_eight_in_bangkok_once_the_video_is_out_and_not_yet_posted(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    import social_post as sp

    state = {"posted": False, "meta": {"2026-11-25": {}}}

    class R:
        def __init__(self, code, body=None):
            self.status_code, self._b = code, body

        def json(self):
            return self._b

    def fake_get(path):
        if path.endswith("videos.json"):
            return R(200, state["meta"])
        return R(200 if state["posted"] else 404)
    monkeypatch.setattr(sp, "_get", fake_get)
    bkk = ZoneInfo("Asia/Bangkok")
    assert sp.due(datetime(2026, 11, 25, 7, 59, tzinfo=bkk)) == ""            # before 08:00
    assert sp.due(datetime(2026, 11, 25, 8, 5, tzinfo=bkk)) == "2026-11-25"
    state["posted"] = True
    assert sp.due(datetime(2026, 11, 25, 9, 0, tzinfo=bkk)) == ""             # posted already
    state["posted"], state["meta"] = False, {"2026-11-24": {}}
    assert sp.due(datetime(2026, 11, 25, 9, 0, tzinfo=bkk)) == ""             # today's video not out: never yesterday's
    assert sp.due(datetime(2026, 11, 23, 9, 0, tzinfo=bkk)) == ""             # before the first day posted this way


def test_claim_is_refused_when_the_marker_exists(monkeypatch):
    import social_post as sp

    codes = iter([200, 409])
    monkeypatch.setattr(sp.requests, "post", lambda *a, **k: type("R", (), {"status_code": next(codes)})())
    assert sp.claim("2026-11-25") is True and sp.claim("2026-11-25") is False
