"""The new Trade Log page's frame: settings and words handed over, plan periods, and a built bundle present."""
import os

import tradelog_page


def test_config_hands_over_periods_words_and_version():
    c = tradelog_page.config("https://x.supabase.co", "anon", "pro")
    assert c["periods"] == ["1y", "3y", "5y", "all"] and c["url"] and c["key"] == "anon"
    assert tradelog_page.config("u", "k", "plus")["periods"] == ["1y"]
    assert c["version"].endswith(".js")


def test_the_react_page_is_built_and_its_texts_are_found():
    here = os.path.dirname(tradelog_page.__file__)
    assert os.path.exists(os.path.join(here, "static", "tl2", "index.html"))
    texts = tradelog_page.js_words(*tradelog_page._sources_text(), code="th")
    assert texts.get("Performance") and texts.get("Where you make and lose money")
