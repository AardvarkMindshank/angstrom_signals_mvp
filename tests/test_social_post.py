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
