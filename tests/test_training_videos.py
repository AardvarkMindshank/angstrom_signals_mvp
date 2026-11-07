"""Training videos in Help and guides: the series order and the player's Back / Next / Start."""

import json
from pathlib import Path

import pytest

import training_videos as tv


def test_every_video_has_a_script_and_a_web_address():
    for _, videos in tv.SERIES.values():
        for slug, title, length in videos:
            script = json.loads((Path("video/series") / f"{slug}.json").read_text())
            assert script["slug"] == slug
            assert tv.info(slug)["url"] == f"https://www.angstromsignals.com/videos/training/{slug}.mp4"
            assert length.count(":") == 1


def test_moving_through_a_series():
    near = tv.neighbours("03-signal-groups")
    assert near == {"first": "01-angstrom-lattice-at-a-glance", "previous": "02-signals", "next": "04-signal-sets"}
    assert tv.neighbours("01-angstrom-lattice-at-a-glance")["previous"] is None
    assert tv.neighbours("05-prism-scan")["next"] is None
    assert tv.neighbours("w2-overextended-rally") == {"first": "w1-trend-with-volume",
                                                      "previous": "w1-trend-with-volume",
                                                      "next": "w3-breakout-with-volume"}


def test_labels_and_positions():
    v = tv.info("04-signal-sets")
    assert (v["label"], v["position"], v["count"]) == ("4 · Signal Sets", 4, 5)
    assert tv.info("w3-breakout-with-volume")["label"] == "Breakout with volume"


def test_unknown_video():
    with pytest.raises(KeyError):
        tv.find("nope")
