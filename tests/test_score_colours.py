import pathlib

from score_colours import STEPS, score_tone, step, tone_js


def test_five_steps_match_the_help_bands():
    assert [step(v) for v in (70, 69.9, 53, 52.9, 47, 46.9, 30, 29.9)] == [
        "strong_up", "up", "up", "mixed", "mixed", "down", "down", "strong_down"]
    assert step(None) == step(float("nan")) == step("x") == "none"
    assert score_tone(80) == STEPS["strong_up"]


def test_js_scale_matches():
    js = tone_js()
    assert "number >= 70" in js and "number >= 53" in js and "number >= 47" in js and "number >= 30" in js
    assert STEPS["strong_down"][1] in js


def test_site_uses_the_shared_scale():
    source = pathlib.Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert "return sentiment_tone(score)" in source
    assert '""" + sentiment_tone_js() + """' in source


def test_sentiment_is_shown_on_the_reading_scale():
    import score_colours as sc
    assert sc.sentiment_value(50) == 0 and sc.sentiment_value(75) == 50 and sc.sentiment_value(0) == -100
    assert sc.sentiment_text(66) == "+32" and sc.sentiment_text(44) == "-12" and sc.sentiment_text(50) == "0"
    assert sc.sentiment_text(None) == "—" and sc.sentiment_value("x") is None
    assert sc.sentiment_stored(30) == 65 and sc.sentiment_stored(-30) == 35
    assert sc.sentiment_text(52.75) == "+6" and sc.sentiment_text(47.25) == "-5"   # halves round up, as in JS


def test_sentiment_keeps_its_own_categories_converted_not_the_reading_bands():
    import score_colours as sc
    assert sc.SENTIMENT_SHOWN_STEPS == {"strong_up": 40, "up": 6, "mixed": -6, "down": -40}
    # every whole stored score lands in exactly the category it always had
    for stored in range(0, 101):
        assert sc.sentiment_tone(stored) == sc.score_tone(stored), stored
    # not the technical bands: +10 is positive sentiment but a mixed reading
    assert sc.sentiment_tone(sc.sentiment_stored(10)) == sc.score_tone(55) != sc.reading_tone(10)


def test_category_follows_the_number_shown():
    import score_colours as sc
    for stored in (52.9, 52.75, 46.9, 29.9, 69.9):
        shown = int(sc.sentiment_text(stored))
        assert sc.sentiment_tone(stored) == sc.sentiment_tone(sc.sentiment_stored(shown)), stored


def test_browser_colours_match_python():
    import score_colours as sc
    js = sc.sentiment_tone_js()
    assert "Math.floor" in js and "number * 2 - 100" in js
    for name, limit in (("strong_up", sc.STRONG_HIGH), ("up", sc.HIGH), ("mixed", sc.LOW), ("down", sc.STRONG_LOW)):
        assert f"stored >= {limit:g}" in js and sc.STEPS[name][1] in js
