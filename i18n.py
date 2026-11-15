"""
🌐 Languages (15 Nov 2026): every piece of on-screen text goes through t("English text"). English is the base and the
fallback; each other language is one file of wording, locales/<code>.json, mapping the English text to its
translation. Text not yet translated simply shows in English, so nothing breaks for want of a translation.

Which language a person sees, in order:
  1. a link with ?lang=<code> (how a beta language is shared for checking), kept for the visit;
  2. their own choice (account setting "language"; on the sign-in page, the choice remembered by this browser);
  3. their browser's language preferences (the Accept-Language list, in its order), the first one the app has;
  4. English.
Never the person's location or IP address: an English speaker in Thailand sees English.

A language is "live" (everyone can pick it), "beta" (admins and ?lang= links only, while it is checked), or not
offered yet. Product names (Angstrom, Lattice, Prism, Funnels, Tides, Sonar, Navigator) stay in English.

Writing text in the app:
    t("Save")                                  plain text
    t("{n} new since your last visit", n=3)    with values: the translation keeps the {n}
Keep the whole sentence in one t() (never glue translated pieces together: word order differs between languages).
"""

from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
LOCALES = os.path.join(HERE, "locales")
FLAGS = os.path.join(HERE, "static", "flags")
BASE = "en"

# code, the language's own name, its English name, flag (country of its main market), status, writing direction
LANGUAGES = [
    {"code": "en", "name": "English", "english": "English", "flag": "gb", "status": "live", "dir": "ltr"},
    {"code": "th", "name": "ไทย", "english": "Thai", "flag": "th", "status": "beta", "dir": "ltr"},
    {"code": "es", "name": "Español", "english": "Spanish", "flag": "es", "status": "planned", "dir": "ltr"},
    {"code": "pt-BR", "name": "Português (Brasil)", "english": "Portuguese (Brazil)", "flag": "br", "status": "planned",
     "dir": "ltr"},
    {"code": "zh-CN", "name": "简体中文", "english": "Chinese (Simplified)", "flag": "cn", "status": "planned", "dir": "ltr"},
    {"code": "ja", "name": "日本語", "english": "Japanese", "flag": "jp", "status": "planned", "dir": "ltr"},
    {"code": "ko", "name": "한국어", "english": "Korean", "flag": "kr", "status": "planned", "dir": "ltr"},
    {"code": "de", "name": "Deutsch", "english": "German", "flag": "de", "status": "planned", "dir": "ltr"},
    {"code": "fr", "name": "Français", "english": "French", "flag": "fr", "status": "planned", "dir": "ltr"},
    {"code": "tr", "name": "Türkçe", "english": "Turkish", "flag": "tr", "status": "planned", "dir": "ltr"},
    {"code": "vi", "name": "Tiếng Việt", "english": "Vietnamese", "flag": "vn", "status": "planned", "dir": "ltr"},
    {"code": "id", "name": "Bahasa Indonesia", "english": "Indonesian", "flag": "id", "status": "planned", "dir": "ltr"},
]
BY_CODE = {lang["code"]: lang for lang in LANGUAGES}

_FIELD = re.compile(r"{(\w+)(?:![rsa])?(?::[^{}]*)?}")


def offered(admin: bool = False, extra: str | None = None) -> list[dict]:
    """The languages a person may pick: live ones, beta ones for admins, and the one a ?lang= link opened."""
    return [lang for lang in LANGUAGES
            if lang["status"] == "live" or (lang["status"] == "beta" and admin) or lang["code"] == extra]


def normalise(code) -> str | None:
    """A language code as the app knows it ("pt-br" → "pt-BR", "th-TH" → "th", "zh-Hans-CN" → "zh-CN"), or None."""
    raw = str(code or "").strip().replace("_", "-")
    if not raw:
        return None
    low = raw.lower()
    for lang in LANGUAGES:
        if lang["code"].lower() == low:
            return lang["code"]
    head = low.split("-")[0]
    if head == "zh":
        return "zh-CN" if not any(part in ("hant", "tw", "hk", "mo") for part in low.split("-")[1:]) else None
    if head == "pt":
        return "pt-BR"
    for lang in LANGUAGES:
        if lang["code"].lower() == head:
            return lang["code"]
    return None


def browser_preferences(header: str | None) -> list[str]:
    """The browser's Accept-Language list ("th-TH,th;q=0.9,en;q=0.8") as raw codes, most wanted first."""
    out = []
    for i, part in enumerate(str(header or "").split(",")):
        bits = part.strip().split(";")
        if not bits[0]:
            continue
        q = 1.0
        for b in bits[1:]:
            b = b.strip()
            if b.startswith("q="):
                try:
                    q = float(b[2:])
                except ValueError:
                    q = 0.0
        if q > 0 and bits[0] != "*":
            out.append((-q, i, bits[0]))
    return [code for _q, _i, code in sorted(out)]


def choose(query=None, saved=None, browser=None, admin: bool = False) -> str:
    """Which language to show (module docstring): a ?lang= link, the saved choice, the browser's list, English.
    A language not offered to this person is skipped."""
    link = normalise(query)
    if link and link in BY_CODE and BY_CODE[link]["status"] in ("live", "beta"):
        return link
    allowed = {lang["code"] for lang in offered(admin)}
    mine = normalise(saved)
    if mine in allowed:
        return mine
    for raw in browser_preferences(browser) if isinstance(browser, str) else list(browser or []):
        code = normalise(raw)
        if code in allowed:
            return code
    return BASE


@lru_cache(maxsize=32)
def _catalogue(code: str, stamp: float) -> dict:
    path = os.path.join(LOCALES, f"{code}.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v.strip() and not k.startswith("_")}


def catalogue(code: str) -> dict:
    """English text → translation for one language (re-read when its file changes)."""
    if code == BASE:
        return {}
    path = os.path.join(LOCALES, f"{code}.json")
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return {}
    return _catalogue(code, stamp)


_OVERRIDE = threading.local()


@contextmanager
def using(code: str | None):
    """Text in another language for a while, such as an email in its recipient's language from a background job:
        with i18n.using(account_language(settings)): body = compose(...)"""
    before = getattr(_OVERRIDE, "code", None)
    _OVERRIDE.code = code if code in BY_CODE else BASE
    try:
        yield
    finally:
        _OVERRIDE.code = before


def set_language(code: str | None) -> None:
    """Like using(), for a loop over recipients: text in `code` until set_language(None)."""
    _OVERRIDE.code = (code if code in BY_CODE else BASE) if code else None


def account_language(settings: dict | None) -> str:
    """The language an account chose (its "language" setting), for what is sent to it; English when none."""
    code = normalise((settings or {}).get("language"))
    return code if code in BY_CODE and BY_CODE[code]["status"] in ("live", "beta") else BASE


def current() -> str:
    """The language of this visit (set by app.py each run), or of an i18n.using() block; English outside Streamlit."""
    forced = getattr(_OVERRIDE, "code", None)
    if forced:
        return forced
    try:
        import streamlit as st

        return st.session_state.get("lang") or BASE
    except Exception:
        return BASE


def translate(text: str, code: str, **values) -> str:
    """`text` in language `code`, with {fields} filled in. A translation that invents a {field} is not trusted:
    the English is used instead."""
    words = catalogue(code).get(text, text) if code != BASE else text
    if words != text and not set(_FIELD.findall(words)) <= set(_FIELD.findall(text)):
        words = text                                   # a translation may leave out a value (an English plural
                                                       # "s"), never invent one
    if values:
        try:
            return words.format(**values)
        except (KeyError, IndexError, ValueError):
            return text.format(**values)
    return words


def mark(text: str) -> str:
    """Marks English text kept in a constant so the translation check finds it; translate it where it is shown,
    with t(CONSTANT)."""
    return text


def t(text: str, **values) -> str:
    """On-screen text in the visit's language (English when there is no translation)."""
    return translate(text, current(), **values)


# Text drawn by the browser (component JavaScript, lw_chart.js): written as T(“English”) or T(“{n} rows”, {n: 3}) in
# the JS. The page gets the translations it needs in its data (data.tr, from js_words), and JS_T is the small T helper
# each component puts at the top of its code. Keep JS texts free of quotes and backslashes.
_JS_TEXT = re.compile(r"""\bTM?\((["'])((?:(?!\1)[^\\\n])+)\1""")
JS_T = ("const T = (s, v) => { const src = (typeof data === 'object' && data) || (typeof component === 'object' &&"
        " component && component.data) || {}; const tr = (src && src.tr) || {}; let w = tr[s] || s;"
        " return v ? w.replace(/\\{(\\w+)\\}/g, (m, k) => (k in v ? v[k] : m)) : w; };")


_JS_ENTRY = re.compile(r"(const \{[^}]*\} = component;)")


def js_ready(js: str) -> str:
    """Component JavaScript with the T helper put in after each `const { … } = component;`."""
    if JS_T in js:                                     # already has it
        return js
    return _JS_ENTRY.sub(lambda m: m.group(1) + "\n  " + JS_T, js)


def js_texts(source: str) -> list[str]:
    """The texts a piece of JavaScript gives to T(“…”), each once, in order."""
    seen: dict[str, None] = {}
    for _q, text in _JS_TEXT.findall(source or ""):
        seen.setdefault(text, None)
    return list(seen)


def js_words(*sources: str, code: str | None = None) -> dict:
    """English → translation for the T(“…”) texts in these JavaScript sources, in the visit's language (only the
    ones translated; a translation that invents a {field} is left out)."""
    code = code or current()
    if code == BASE:
        return {}
    have = catalogue(code)
    out = {}
    for source in sources:
        for text in js_texts(source):
            words = have.get(text)
            if words and set(_FIELD.findall(words)) <= set(_FIELD.findall(text)):
                out[text] = words
    return out


def with_words(mount, *sources: str):
    """A Streamlit component that also hands its JavaScript the translations it needs (data.tr), so each place that
    shows it needs no change."""
    def show(*args, **kwargs):
        data = kwargs.get("data")
        as_text = isinstance(data, str)
        if as_text:                                    # some components get their data as JSON text
            try:
                data = json.loads(data)
            except ValueError:
                data = None
        if isinstance(data, dict):
            words = js_words(*sources)
            if words:
                data = {**data, "tr": words}
                kwargs["data"] = json.dumps(data) if as_text else data
        return mount(*args, **kwargs)
    return show


def flag_svg(country: str) -> str:
    """A flag as SVG markup (static/flags, from the MIT-licensed flag-icons set): flag emojis don't show on Windows."""
    try:
        with open(os.path.join(FLAGS, f"{country}.svg"), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def html_lang(code: str) -> str:
    """The code for the page's lang attribute (screen readers, fonts, browser translation offers)."""
    return code if code in BY_CODE else BASE
