"""🌐 Languages (i18n.py, lang_picker.py, i18n_check.py): which language a visit shows, the lookup, the files."""

import json
import os
import re
from types import SimpleNamespace

import i18n
import i18n_check
import lang_picker


def test_browser_language_list_in_order():
    assert i18n.browser_preferences("th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7") == ["th-TH", "th", "en-US", "en"]
    assert i18n.browser_preferences("en;q=0.5, de") == ["de", "en"]
    assert i18n.browser_preferences("") == []
    assert i18n.browser_preferences("fr;q=0, *") == []


def test_codes_are_normalised():
    assert i18n.normalise("th-TH") == "th"
    assert i18n.normalise("pt-br") == "pt-BR" and i18n.normalise("pt-PT") == "pt-BR"
    assert i18n.normalise("zh-Hans-CN") == "zh-CN" and i18n.normalise("zh-TW") is None
    assert i18n.normalise("xx") is None and i18n.normalise(None) is None


def test_choice_order_never_location():
    # a link wins (and opens a beta language for anyone)
    assert i18n.choose(query="th", saved="en", browser="en") == "th"
    # a saved choice next, if offered to this person
    assert i18n.choose(saved="th", browser="en", admin=True) == "th"
    assert i18n.choose(saved="th", browser="en", admin=False) == "en"     # beta: not for everyone yet
    # then the browser's list, first language the app offers
    assert i18n.choose(browser="th-TH,th;q=0.9,en;q=0.8", admin=True) == "th"
    assert i18n.choose(browser="ja,de;q=0.9") == "en"                       # not offered yet: English
    assert i18n.choose() == "en"


def test_lookup_falls_back_and_keeps_values(tmp_path, monkeypatch):
    (tmp_path / "th.json").write_text(json.dumps({"Hello": "สวัสดี", "{n} new": "ใหม่ {n}", "Bad {n}": "เสีย"}),
                                      encoding="utf-8")
    monkeypatch.setattr(i18n, "LOCALES", str(tmp_path))
    assert i18n.translate("Hello", "th") == "สวัสดี"
    assert i18n.translate("Not there", "th") == "Not there"
    assert i18n.translate("{n} new", "th", n=3) == "ใหม่ 3"
    assert i18n.translate("Bad {n}", "th", n=2) == "Bad 2"                  # a translation that lost {n}: English
    assert i18n.translate("Hello", "en") == "Hello"


def test_every_language_file_is_sound():
    for name in os.listdir(i18n.LOCALES):
        code = name.removesuffix(".json")
        assert code in i18n.BY_CODE, f"{name}: not a language the app knows"
        with open(os.path.join(i18n.LOCALES, name), encoding="utf-8") as fh:
            data = json.load(fh)
        for english, words in data.items():
            if english.startswith("_"):
                continue
            assert isinstance(words, str) and words.strip(), (name, english)
            assert set(re.findall(r"{(\w+)}", english)) == set(re.findall(r"{(\w+)}", words)), (name, english)


def test_every_language_has_a_flag_image():
    for lang in i18n.LANGUAGES:
        assert i18n.flag_svg(lang["flag"]).lstrip().startswith("<svg"), lang["code"]


def test_offered_languages():
    assert [x["code"] for x in i18n.offered()] == ["en"]
    assert "th" in [x["code"] for x in i18n.offered(admin=True)]
    assert "th" in [x["code"] for x in i18n.offered(extra="th")]


def test_the_check_finds_texts_in_code():
    src = 'x = t("Save")\ny = i18n.t("Hello {n}", n=1)\nz = i18n.mark("Kept " "together")\nw = t(name)\n'
    assert i18n_check.texts_in(src) == ["Save", "Hello {n}", "Kept together"]
    texts = i18n_check.all_texts()
    assert "Welcome Back" in texts and "Quick Snapshot" in texts


def test_thai_covers_the_converted_screens():
    r = i18n_check.report("th")
    assert r["total"] > 50 and not r["missing"], r["missing"][:5]


def test_picker_payload_and_events():
    data = lang_picker.payload("th", i18n.offered(admin=True), ask=False, chosen=True)
    assert data["current"] == "th" and any(o["code"] == "th" and o["beta"] for o in data["options"])
    assert all(o["flag"].lstrip().startswith("<svg") for o in data["options"])
    state = {}
    ev = SimpleNamespace(lang=json.dumps({"code": "th-TH", "how": "pick", "nonce": 1}))
    assert lang_picker.read_event(ev, "s", state) == {"code": "th", "how": "pick"}
    assert lang_picker.read_event(ev, "s", state) is None
    bad = SimpleNamespace(lang=json.dumps({"code": "xx", "how": "pick", "nonce": 2}))
    assert lang_picker.read_event(bad, "s", state) is None


_FIELD = re.compile(r"{(\w+)}")
