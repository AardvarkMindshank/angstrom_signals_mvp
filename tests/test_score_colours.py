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
    assert "return score_tone(score)" in source
    assert '""" + tone_js() + """' in source
