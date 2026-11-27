"""The new app's Help and guides are read from the classic app's own help (web/scripts/help.py): every topic must find
its texts, so a change to the classic help can't leave a topic empty."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "web", "scripts"))

import help as h  # noqa: E402


def test_every_help_topic_has_text_in_english_and_another_language():
    blocks = h.classic_blocks()
    for code in ("en", "fr"):
        topics = h.topics(code, blocks)
        assert [t["key"] for t in topics] == [k for k, *_ in h.TABS]
        for t in topics:
            assert t["blocks"] and all(len(b) > 20 for b in t["blocks"]), (code, t["key"])
    fr = {t["key"]: t for t in h.topics("fr", blocks)}
    assert fr["start"]["blocks"][0] != h.START[0]          # translated, not the English text


def test_the_training_videos_are_listed():
    vids = h.videos()
    assert vids and all(v["videos"] and v["videos"][0]["url"].endswith(".mp4") for v in vids)
