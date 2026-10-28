"""Ready-made colour themes are complete, valid, and match the app's own defaults."""
import ast
import pathlib
import re

import colour_themes as ct


def _app_defaults():
    source = (pathlib.Path(__file__).resolve().parent.parent / "app.py").read_text()
    found = re.search(r"_THEME_COLOURS = (\(.*?\n\))", source, re.S)
    return dict(ast.literal_eval(found.group(1)))


def test_default_theme_matches_the_app():
    assert ct.THEMES["Default"] == _app_defaults()


def test_every_theme_is_complete_and_valid():
    defaults = _app_defaults()
    for name, colours in ct.THEMES.items():
        assert set(colours) == set(ct.KEYS), name
        assert ct.clean_set(colours, defaults) == colours, name


def test_night_borders_can_be_seen_in_every_theme_but_default():
    def lum(hex_value):
        r, g, b = (int(hex_value[i:i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    for name, colours in ct.THEMES.items():
        if name == "Default":
            continue
        assert abs(lum(colours["border_night"]) - lum(colours["page_night"])) > 30, name
        assert abs(lum(colours["border_day"]) - lum(colours["page_day"])) > 15, name


def test_clean_set_repairs_bad_values():
    defaults = _app_defaults()
    fixed = ct.clean_set({"page_day": "#ABCDEF", "page_night": "red", "border_day": None}, defaults)
    assert fixed["page_day"] == "#abcdef"
    assert fixed["page_night"] == defaults["page_night"]
    assert fixed["border_day"] == defaults["border_day"]
    assert ct.clean_set(None, defaults) == defaults


def test_swatch_html_is_safe_and_shows_both_modes():
    page = ct.swatch_html({"page_day": '#fff"><script>', "page_night": "#000000"})
    assert "<script>" not in page
    assert page.count("flex:1;background:") >= 2
