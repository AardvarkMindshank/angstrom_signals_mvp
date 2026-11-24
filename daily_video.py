"""
🎬 The daily video (the Morning Outlook) (20 Nov 2026): about 90 seconds for social media, made from the same facts as the
Morning Outlook (briefing.general_facts), in two shapes: 16:9 (YouTube) and 9:16 (Shorts, TikTok, Reels).

Running order (each captain line is a pre-made clip from the 3D captain's library, picked by the day's weather and
at random between two versions; everything else is made fresh each day with the free voice):

    🎭 welcome · date and headline · 🎭 the weather · 🎭 signpost · the Tide and currents · 🎭 signpost · equities ·
    🎭 signpost · crypto · 🎭 signpost · on the horizon · 🎭 sign-off · closing line

The captain and the narrator share one voice (George), so the cuts between them are seamless. Graphics are drawn
by video/daily/forecast.html (render(t), as the teaser), the captain clips are laid over them with ffmpeg, the
music is the morning's weather track, dipping under the voice. No brand name appears unless brand.SHOW_IN_VIDEO.

    python daily_video.py --library <folder of captain clips> --music <folder of weather tracks> --out <folder>
"""

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

import brand
import briefing
import score_colours

HERE = Path(__file__).resolve().parent
PAGE = HERE / "video" / "daily" / "forecast.html"
RENDER = HERE / "video" / "daily" / "render.js"
VOICE, SPEED = "bm_george", 1.1
# ⚓ The crew (21 Nov 2026): who presents is a daily weighted draw (CHANCES below); the presenter also narrates, so the voice matches.
# Clip names in the library: <prefix>_<line>_<1|2>_1.mp4 (avatar lab). A presenter whose clips are missing falls
# back to the captain.
PRESENTERS = {
    "cap": {"title": "The Captain", "voice": "bm_george", "speed": 1.1},
    "mate": {"title": "The First Mate", "voice": "af_bella", "speed": 1.08},
    "nav": {"title": "The Navigator", "voice": "af_sarah", "speed": 1.08},
    "deck": {"title": "The Deckhand", "voice": "bm_lewis", "speed": 1.08},
}
PRESENTERS["cat"] = {"title": "The Ship's Cat", "voice": "af_nicole", "speed": 1.25}
# The new crew (23 Nov 2026): the Cook (Italian, a little lower; his galley sways with the ship), the Admiral (rare, and
# more likely on CPI and jobs-report days) and the Rat (raised voice, flickering candle; only on days the cat isn't on).
PRESENTERS["cook"] = {"title": "The Ship's Cook", "voice": "im_nicola", "speed": 1.05, "pitch": -3, "effect": "sway"}
PRESENTERS["admiral"] = {"title": "The Admiral", "voice": "bm_fable", "speed": 1.0}
PRESENTERS["rat"] = {"title": "The Ship's Rat", "voice": "am_echo", "speed": 1.2, "pitch": 7, "effect": "flicker"}
# Who presents is a surprise each day (Angus, 23 Nov 2026), a weighted draw seeded by the date, so a video re-made
# the same day keeps its presenter. No clips are tied to a weekday. Presenters whose clip set isn't in the library
# yet are left out of the draw; the captain is always in it.
CHANCES = {"cap": 0.34, "mate": 0.20, "nav": 0.12, "deck": 0.12, "cook": 0.08, "cat": 0.06, "rat": 0.05,
           "admiral": 0.03}
BIG_DAY_WORDS = ("CPI", "inflation", "jobs report", "Employment", "payrolls")   # the Admiral's inspection days
RAT_TAG_CHANCE = 0.5            # on the Rat's days, his candlelit midnight-snack tag after the sign-off
# 🎬 Bloopers (23 Nov 2026): short comic clips. The Cook's rear reveal closes one in four of the videos he presents;
# the others drop in between two sections in about one video in ten (never inside a section, so never over a number).
COOK_REVEAL = "blooper_cook_back_1.mp4"
COOK_REVEAL_CHANCE = 0.25                                            # one in four of his own videos (Angus, 23 Nov)
ROUGH = ("rough", "stormy")
BLOOPERS = {      # not_with: presenters it never plays beside (the Rat keeps out of the cat's videos); weather: only then
    "blooper_rat_pocket_1.mp4": {"caption": ["Outtake", "Meanwhile, in the galley"], "not_with": ("cat",)},
    "blooper_admiral_cheese_1.mp4": {"caption": ["Outtake", "Who's been at the cheese?"], "not_with": ("cat",)},
    "blooper_cat_chase_1.mp4": {"caption": ["Outtake", "Meanwhile, on the chart table"], "not_with": ()},
    "blooper_rat_wave_1.mp4": {"caption": ["Outtake", "Rough seas below decks"], "not_with": ("cat",),
                               "weather": ROUGH},
    "blooper_cook_wave_1.mp4": {"caption": ["Outtake", "Rough seas in the galley"], "not_with": (), "weather": ROUGH},
}
BLOOPER_CHANCE = 0.10              # rare on purpose (Angus, 23 Nov 2026)
BLOOPER_AFTER = ("story", "tides", "equities", "crypto")             # it plays after one of these sections


def blooper_for(day: datetime, who: str, library: Path | None, sections, weather: str | None = None) -> dict | None:
    """The day's blooper, if any: {file, after}, drawn from the date so a re-run gives the same video."""
    rng = random.Random(f"blooper-{day.date().isoformat()}")
    if rng.random() >= BLOOPER_CHANCE:
        return None
    pool = sorted(f for f, b in BLOOPERS.items() if who not in b["not_with"]
                  and (weather in b.get("weather", (weather,)))
                  and (library is None or (library / f).exists()))
    slots = [k for k in BLOOPER_AFTER if k in sections]
    if not pool or not slots:
        return None
    return {"file": rng.choice(pool), "after": rng.choice(slots)}
# 🎁 Guests on special days: a cameo (their own welcome and sign-off; the day's presenter does the rest).
GUESTS = {"santa": "Father Christmas", "ghost": "The Ghost Captain", "bunny": "The Easter Bunny",
          "neptune": "King Neptune"}
FIXED_DAYS = {(12, 24): "santa", (12, 25): "santa", (10, 31): "ghost"}
SET_LINES = ("welcome", "welcome_weekend", "weather_sunny", "weather_fair", "weather_changeable", "weather_rough",
             "weather_stormy", "sign_story", "sign_tides", "sign_equities", "sign_crypto", "sign_horizon", "signoff")


def easter(year: int) -> tuple[int, int]:
    """(month, day) of Easter Sunday (the Gregorian computus)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    return month, (h + l_ - 7 * m + 114) % 31 + 1


def has_set(library: Path, who: str) -> bool:
    """Whether the library holds a presenter's whole clip set (first versions at least)."""
    return all((library / f"{who}_{line}_1_1.mp4").exists() for line in SET_LINES)


def guest_for(day: datetime, facts: dict | None, library: Path | None) -> str | None:
    """The day's guest, if any and if their cameo clips are in the library: Father Christmas on the 24th and 25th of
    December, the ghost captain at Halloween, the Easter Bunny on Easter Sunday, King Neptune on Fed decision days."""
    guest = FIXED_DAYS.get((day.month, day.day))
    if guest is None and (day.month, day.day) == easter(day.year):
        guest = "bunny"
    if guest is None:
        when = day.strftime("%d %B")
        for e in (facts or {}).get("events") or []:
            text = f"{e.get('what', '')} {e.get('when_utc', '')}"
            if ("Fed" in text or "FOMC" in text) and when.lstrip("0") in text.replace(" 0", " "):
                guest = "neptune"
    if guest and library is not None and not all((library / f"{guest}_{k}_1_1.mp4").exists()
                                                 for k in ("welcome", "signoff")):
        return None
    return guest
GAP = 0.25                       # seconds between segments
FPS = 30
MUSIC = {"sunny": "1-Sunshine.mp3", "fair": "2-Springtime.mp3", "changeable": "3-Cloudy.mp3",
         "rough": "4-Rainy.mp3", "stormy": "5-Stormy.mp3"}
WEATHER_WORDS = {"sunny": ("☀️", "Fair and sunny"), "fair": ("🌤️", "Fair"), "changeable": ("⛅", "Changeable"),
                 "rough": ("🌧️", "Rough seas"), "stormy": ("⛈️", "Storm warning")}
DOLLAR_CURRENTS = ("Gold", "Oil")                # prices in dollars: shown with a $
INVERSE_WORDS = ("fear", "vix", "volatility")    # metrics where up is bad: their rises show red, falls green
SPARK = {"SPY": ("equity", "SPY"), "QQQ": ("equity", "QQQ"), "Bitcoin": ("crypto", "bitcoin"),
         "Ether": ("crypto", "ethereum"), "Solana": ("crypto", "solana"), "XRP": ("crypto", "ripple"),
         "BNB": ("crypto", "binancecoin")}
# 🧭 The Morning Outlook (24 Nov 2026, agreed with Angus from the mock-up): every section comes from what the app
# shows. The Tide first (the weeks-long backdrop), then the story of the day (the bigger of the two Market sentiment
# cards' stories), then each market in the same order: its sentiment card (score, words, strip, summary), then its
# numbers. Nothing is worked out for the video alone: the cards are read as stored, the numbers are the daily
# briefing's facts, and every number the script says is checked against them before anything is made.
# Word counts for a little over two minutes (the first test ran 154 s; at fewer words it ran 127 s but read clipped,
# so Angus asked for it to flow: 24 Nov 2026).
SECTIONS = {"tides": 24, "story": 28, "stock_mood": 25, "equities": 20, "crypto_mood": 25, "crypto": 22, "horizon": 14}
WEEKEND_SECTIONS = {"tides": 26, "story": 30, "crypto_mood": 28, "crypto": 26, "horizon": 14}
MOOD_KINDS = {"stock_mood": "stock", "crypto_mood": "crypto"}      # section -> the app's Market sentiment card


def sections_for(day: datetime) -> dict:
    return WEEKEND_SECTIONS if day.weekday() >= 5 else SECTIONS


def _ordinal(n: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
             9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth",
             15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth", 19: "nineteenth",
             20: "twentieth", 21: "twenty-first", 22: "twenty-second", 23: "twenty-third", 24: "twenty-fourth",
             25: "twenty-fifth", 26: "twenty-sixth", 27: "twenty-seventh", 28: "twenty-eighth",
             29: "twenty-ninth", 30: "thirtieth", 31: "thirty-first"}
    return words[n]


# ------------------------------------------------------------------------------------------------ the app's cards

def refresh_moods(supabase) -> None:
    """Rewrite the two Market sentiment cards just before the video, with the same code and data sources as the app's
    background job (shared_refresh), so the video shows the latest and the 12-hour clock restarts from here. The
    video job carries every data key the background job has (24 Nov 2026: without them a refresh scored only the
    readings it could fetch)."""
    try:
        import ai_providers
        import market_store
        import sentiment
        import shared_refresh

        sentiment.set_provider(ai_providers.app_choice(supabase, "sentiment"))
        if not sentiment.sentiment_ready():
            print("Sentiment refresh skipped: no sentiment AI key.")
            return
        moods = market_store.load_market_moods(supabase) or {}
        for spec in sentiment.MACRO_MOODS:
            shared_refresh._save_mood(supabase, spec, previous=shared_refresh._previous_report(moods.get(spec["key"])))
    except Exception as exc:
        print(f"Sentiment refresh skipped: {str(exc)[:160]}")


def app_moods(supabase) -> dict:
    """{"stock": report, "crypto": report}: the two Market sentiment cards exactly as the app stores them."""
    try:
        import market_store

        rows = market_store.load_market_moods(supabase) or {}
    except Exception:
        rows = {}
    out = {}
    for key in ("stock", "crypto"):
        report = (rows.get(key) or {}).get("sentiment_report")
        if isinstance(report, str):
            try:
                report = json.loads(report)
            except ValueError:
                report = None
        out[key] = report if isinstance(report, dict) and report.get("ok") else None
    return out


def _first_sentence(text: str) -> str:
    text = " ".join(str(text or "").split())
    cut = re.search(r"(?<=[.!?])\s", text)
    return text[:cut.start()] if cut else text


def mood_view(report: dict | None) -> dict | None:
    """One card as the video uses it: the score and words as the app shows them, the card's colour, the first
    sentence of its summary, its story of the day, its readings and its headlines."""
    if not report or report.get("score") is None:
        return None
    mood = briefing.news_mood(report["score"]) or {}
    tone = score_colours.sentiment_tone(report["score"])
    readings = [{"name": i.get("name"), "value": i.get("value"), "detail": i.get("detail")}
                for g in report.get("gauges") or [] if isinstance(g, dict) for i in g.get("items") or []
                if isinstance(i, dict) and i.get("score") is not None and not i.get("stale")]
    heads = [{"title": h.get("title"), "source": h.get("source"),
              "mood": (briefing.news_mood(h["score"]) or {}).get("news_mood")}
             for h in report.get("headlines") or [] if isinstance(h, dict) and h.get("score") is not None]
    lead = report.get("lead") if isinstance(report.get("lead"), dict) else None
    return {"score": mood.get("news_mood"), "words": mood.get("news_mood_words"), "colour": tone[0],
            "bg": tone[1], "arrow": tone[2], "summary": _first_sentence(report.get("summary")), "lead": lead,
            "readings": readings, "headlines": heads}


def _lead_size(lead: dict | None) -> float:
    """How big a card's story of the day is: the largest move it explains. A quiet day is 0."""
    if not lead or lead.get("quiet") or not lead.get("title"):
        return 0.0
    moves = [abs(float(m["change_1d"])) for m in lead.get("moves") or [] if m.get("change_1d") is not None]
    return max(moves, default=0.0) or 0.01


def top_story(views: dict, weekend: bool = False) -> dict | None:
    """The story of the day for the whole video: the bigger of the two cards' stories (stocks are shut at weekends,
    so then crypto's). None when neither card has one."""
    keys = ("crypto",) if weekend else ("stock", "crypto")
    best = max(keys, key=lambda k: _lead_size((views.get(k) or {}).get("lead")))
    lead = (views.get(best) or {}).get("lead")
    return {"market": best, **lead} if _lead_size(lead) else None


def strip_svg(report: dict | None, width: int) -> str:
    """The app's sentiment strip (sentiment_spread), coloured for the video's dark sea."""
    from sentiment_spread import spread_html

    html_ = spread_html(report, (report or {}).get("score"), width=width) if report else ""
    return (html_.replace("var(--ang-track,#e5e7eb)", "rgba(255,255,255,.32)")
            .replace("var(--ang-muted,#9ca3af)", "rgba(255,255,255,.6)")
            .replace("var(--ang-text,#111827)", "#ffffff").replace("var(--ang-muted,#6b7280)", "rgba(255,255,255,.75)"))


# ------------------------------------------------------------------------------------------------ the script

ASK = {
    "tides": "\"tides\": about %d words on the Tide over recent weeks: risk-on or defensive and for how long, the sea "
             "state and the strongest currents (dollar, gold, oil, fear index). These are weeks-long readings: say "
             "\"over the past month\" or \"this week\", never \"today\"",
    "story": "\"story\": {\"title\": at most 6 words, \"text\": about %d words, \"asset\": \"\" or a market name} for "
             "the story of the day. When story_of_the_day is given, tell it: what happened (from its headline and "
             "why) and the moves given with it, naming their day; asset \"\". If overall_weather is rough or stormy "
             "and the story is good news, call it a bright spell in heavy weather (and the other way round on fair "
             "days). When story_of_the_day is null, the single standout mover in the facts, with asset its name "
             "exactly as given",
    "stock_mood": "\"stock_mood\": about %d words on stock_market_sentiment: its score and words exactly as given "
                  "(\"plus 22, bullish\"), what most of its headlines are about, and one or two of its readings by "
                  "name and value. If its story is the story of the day, mention it in a few words only",
    "equities": "\"equities\": about %d words on the S&P 500 and Nasdaq 100 moves, the day's and the week's",
    "crypto_mood": "\"crypto_mood\": about %d words on crypto_market_sentiment the same way. If its story differs "
                   "from the story of the day and is not a quiet day, open with it",
    "crypto": "\"crypto\": about %d words on Bitcoin, Ether and the other top coins, the day's and the week's moves",
    "horizon": "\"horizon\": about %d words on the next scheduled events",
}


def system_prompt(sections: dict, weekend: bool) -> str:
    parts = ", ".join(ASK[k] % n for k, n in sections.items())
    return (
        "You write the narration for a two-minute daily market video, the Morning Outlook, in the style of the "
        "shipping forecast: calm, clear, a light nautical flavour that never hides a fact. A crew member introduces "
        "each section; you write only what is said inside each section. Write for the ear: short sentences, plain "
        "words, no lists, no brand or app names. Write numbers as digits and round them for the ear: percentages to "
        "one decimal place (\"4.7 percent\", never \"4.71\"), prices to about three figures (\"60,100 dollars\"), "
        "scores as whole numbers (\"plus 19\"); a check compares every number you write with the facts, so use only "
        "numbers in the facts and never work new ones out. Keep each section to its word count, but write it as flowing "
        "spoken sentences that join naturally, like a presenter talking, never clipped notes (\"The Tide has been going "
        "out for 25 trading days\", not \"Tide out, 25 days\"). Use only the facts given; never invent "
        "prices, news or events. Describe; never tell anyone to buy, sell or hold. Each 1-day change covers exactly "
        "the period in its one_day_change_covers: name that period (\"on Monday\", \"over the last 24 hours\") and "
        "never call it today's move unless it says today. "
        + ("It is the weekend: stock markets are shut, so do not talk about today's stock moves. " if weekend else "")
        + "Reply with JSON only: {\"headline\": a punchy headline of at most 7 words about the story of the day "
        "(it opens the video and the story section follows it up), " + parts + "}."
    )


def _template(facts: dict, sections: dict = SECTIONS, views: dict | None = None, story: dict | None = None) -> dict:
    """The sections without AI, from the facts and the cards alone."""
    views = views or {}
    km = {a["name"]: a for a in facts.get("key_markets") or []}
    coins = facts.get("cryptos") or []
    tide = (facts.get("tide") or ["The Tide is steady."])[0]
    spy = km.get("S&P 500 (the SPY fund)", {})
    eq = (f"The S&P 500 moved {spy.get('change_1d', 0):+.1f} percent {briefing.move_span(spy)}." if spy
          else "Equities were mixed.")
    btc = coins[0] if coins else {}
    cr = f"Bitcoin moved {btc.get('change_1d', 0):+.1f} percent {briefing.move_span(btc)}." if btc else "Crypto was mixed."
    ev = facts.get("events") or []
    hz = f"Next up: {ev[0]['what']}, {ev[0]['when_utc']} UTC." if ev else "A quiet week on the calendar."
    if story:
        story_out = {"title": "The story of the day", "asset": "", "text": f"{story['title']}. {story.get('why', '')}"}
    else:
        movers = [a for a in (facts.get("key_markets") or []) + coins if a.get("change_1d") is not None]
        big = max(movers, key=lambda a: abs(a["change_1d"]), default=None)
        story_out = ({"title": f"{big['name']} on the move", "asset": big["name"],
                      "text": f"{big['name']} moved {big['change_1d']:+.1f} percent {briefing.move_span(big)}."} if big
                     else {"title": "A steady day", "asset": "", "text": "No single market stood out."})

    def mood_line(key, label):
        v = views.get(key)
        if not v or v.get("score") is None:
            return f"No {label} sentiment reading today."
        return f"{label.capitalize()} news reads {v['words']}, {v['score']:+d}. {v['summary']}"

    out = {"headline": "Your Morning Outlook", "story": story_out, "tides": tide, "equities": eq, "crypto": cr,
           "horizon": hz, "stock_mood": mood_line("stock", "stock-market"), "crypto_mood": mood_line("crypto", "crypto")}
    return {k: out[k] for k in ("headline", *sections)}


def today_words(out: dict) -> list[str]:
    """The sections that describe a market move as today's: the figures are the last finished session or day, so
    "today" is wrong in them (the headline, the Tide's levels and the horizon may use it)."""
    texts = {k: out.get(k) for k in ("equities", "crypto")} | {"story": (out.get("story") or {}).get("text")}
    return [k for k, v in texts.items() if isinstance(v, str) and re.search(r"\btoday\b|\bthis morning\b", v, re.I)]


# 🔢 Every number in the script must be one of the app's (24 Nov 2026): the facts and the two cards, as given or
# rounded. Dates, years, times and ordinals are not checked.
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
_MONTHS = r"(january|february|march|april|may|june|july|august|september|october|november|december)"


def known_numbers(*sources) -> list[float]:
    """Every number in the sources (nested dicts, lists and strings), as positive values."""
    out = []

    def walk(x):
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            out.append(abs(float(x)))
        elif isinstance(x, str):
            out.extend(float(m.replace(",", "")) for m in _NUM.findall(x.replace("−", "-")))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    for s in sources:
        walk(s)
    return out


def unknown_numbers(text: str, known: list[float]) -> list[str]:
    """The numbers in the text that are not in `known`, as given or rounded (to a whole number or 1 decimal place),
    or in thousands, millions or billions."""
    bad = []
    for m in _NUM.finditer(text):
        token = m.group(0).rstrip(",")
        after, before = text[m.end():m.end() + 14].lower(), text[max(0, m.start() - 14):m.start()].lower()
        value = float(token.replace(",", ""))
        if re.match(r"(st|nd|rd|th)\b|:\d", after) or re.search(r"\d:$", before):
            continue                                          # ordinals and times
        if re.search(r"(s&p|nasdaq|dow|russell|ftse|dax|nikkei|coindesk|top)\s*$", before):
            continue                                          # names: the S&P 500, the Nasdaq 100, the top 5
        if re.match(r"\s*hours?\b", after):
            continue                                          # periods: "over the last 24 hours"
        if 1990 <= value <= 2100 and "," not in token and "." not in token:
            continue                                          # years
        if value <= 31 and (re.match(r"\s*" + _MONTHS, after) or re.search(_MONTHS + r"\s*$", before)):
            continue                                          # dates
        ok = False
        for scale in (1, 1e3, 1e6, 1e9):
            x = value * scale
            for k in known:
                if abs(x - k) <= max(0.051 * scale, 0.006 * k) or (scale == 1 and abs(x - k) < 0.5 and x == round(x)):
                    ok = True
                    break
            if ok:
                break
        if not ok:
            bad.append(token)
    return bad


_UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALES = {"hundred": 100, "thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9}
_WORD = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|" \
        r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|" \
        r"million|billion)"
_WORDS_RUN = re.compile(r"\b" + _WORD + r"(?:[\s-]+(?:and[\s-]+)?" + _WORD + r")*(?:\s+point(?:\s+" + _WORD + r")+)?\b",
                        re.I)


def _words_value(words: str) -> str:
    """"four point seven" -> "4.7", "sixty thousand four hundred" -> "60400", "twenty-five" -> "25"."""
    whole, _, frac = words.lower().replace("-", " ").partition(" point ")
    total = current = 0
    for w in whole.split():
        if w == "and":
            continue
        if w in _UNITS:
            current += _UNITS[w]
        elif w in _TENS:
            current += _TENS[w]
        elif w == "hundred":
            current = max(current, 1) * 100
        elif w in _SCALES:
            total += max(current, 1) * _SCALES[w]
            current = 0
    value = str(total + current)
    digits = "".join(str(_UNITS[w]) for w in frac.split() if w in _UNITS and _UNITS[w] < 10)
    return value + ("." + digits if digits else "")


def digits_for_words(text: str) -> str:
    """The text with spelled-out numbers as digits, so the check sees them too (24 Nov 2026: the script said "four
    point seven percent" in words, which a digits-only check would never look at). "One" alone is left as a word."""
    def swap(m):
        words = m.group(0)
        if re.match(r"[\s-]+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)\b", m.string[m.end():], re.I):
            return words                                   # a date: "the twenty-fourth"
        return words if words.lower() in ("one", "zero") else _words_value(words)
    return _WORDS_RUN.sub(swap, text)


def script_numbers_problems(out: dict, known: list[float]) -> dict:
    """{section: [numbers not in the app's data]} for a written script, in digits or in words."""
    problems = {}
    for k, v in out.items():
        text = v.get("text") if isinstance(v, dict) else v
        if isinstance(text, str):
            bad = unknown_numbers(digits_for_words(text), known)
            if bad:
                problems[k] = bad
    return problems


def write_sections(supabase, facts: dict, chat=None, sections: dict = SECTIONS, weekend: bool = False,
                   views: dict | None = None, story: dict | None = None) -> tuple[dict, str]:
    """({headline, tides, story {title, text, asset}, stock_mood?, equities?, crypto_mood, crypto, horizon}, who wrote
    it). Falls back to the template when the AI doesn't answer, or still uses a number not in the app's data."""
    import ai_providers

    views = views or {}
    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if ai_providers.available(provider):
        data = {k: briefing.for_ai(facts).get(k) for k in ("conditions", "tide", "key_markets", "cryptos", "events")}
        data["overall_weather"] = briefing.weather(facts)
        data["story_of_the_day"] = ({k: story.get(k) for k in ("market", "title", "source", "why", "moves")}
                                    if story else None)
        for kind, key in MOOD_KINDS.items():
            if kind in sections:
                v = views.get(key) or {}
                lead = v.get("lead") or {}
                data[f"{'stock' if key == 'stock' else 'crypto'}_market_sentiment"] = {
                    "score": v.get("score"), "words": v.get("words"), "summary": v.get("summary"),
                    "its_story": ({"title": lead.get("title"), "why": lead.get("why")} if lead and not lead.get("quiet")
                                  else {"quiet_day": lead.get("why")} if lead else None),
                    "readings": v.get("readings"), "headlines": v.get("headlines")}
        known = known_numbers(data)
        messages = [{"role": "user", "content": json.dumps(data, ensure_ascii=False, default=str)}]
        for _attempt in range(3):
            try:
                reply = (chat or ai_providers.chat)(provider, system_prompt(sections, weekend), messages, max_tokens=1500)
                if isinstance(reply, (tuple, list)):
                    reply = reply[0]
                text = reply.get("text") if isinstance(reply, dict) else str(reply)
                got = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            except Exception as exc:
                print(f"Video script by AI failed: {str(exc)[:160]}")
                break
            story_got = got.get("story") if isinstance(got.get("story"), dict) else None
            plain = [k for k in ("headline", *sections) if k != "story"]
            if not (story_got and str(story_got.get("text") or "").strip() and all(
                    isinstance(got.get(k), str) and got[k].strip() for k in plain)):
                break
            out = {k: briefing.clean(got[k]) for k in plain}
            out["story"] = {"title": briefing.clean(str(story_got.get("title") or "")) or "The story of the day",
                            "text": briefing.clean(str(story_got["text"])), "asset": str(story_got.get("asset") or "")}
            wrong = today_words(out)
            numbers = script_numbers_problems(out, known)
            if not wrong and not numbers:
                return out, provider
            ask = []
            if wrong:
                # A move called "today" when it is Friday's session or the last 24 hours (feedback 23 Nov 2026).
                ask.append("These parts call a move today's, but every change covers the period in its "
                           "one_day_change_covers: " + ", ".join(wrong) + ".")
            if numbers:
                ask.append("These numbers are not in the facts: " + "; ".join(f"{k}: {', '.join(v)}"
                                                                               for k, v in numbers.items())
                           + ". Use only the facts' numbers, as given or rounded.")
                print(f"Video script: numbers not in the app's data, asking again: {json.dumps(numbers)}")
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": " ".join(ask) + " Write it again, JSON only."}]
    return _template(facts, sections, views, story), "template"


# ------------------------------------------------------------------------------------------------ the graphics' data

def _spark(load, kind: str, asset_id: str) -> list[float]:
    """The week's daily closes, the very closes its 1-day and 1-week changes are worked out from (briefing's
    _candle_moves), so the line always agrees with the numbers beside it (24 Nov 2026: an hourly line ended in
    Friday's fall beside Monday's +4.7%). Shares: the last 6 sessions; coins: the last 8 days."""
    try:
        return briefing._candle_moves(kind, asset_id, load).get("week_closes") or []
    except Exception:
        return []


def _spark_days(load, kind: str, asset_id: str) -> list[str]:
    """The weekday of each of those closes ("Mon"), for the main markets' chart."""
    try:
        days = briefing._candle_moves(kind, asset_id, load).get("week_days") or []
        return [datetime.fromisoformat(d).strftime("%a") if d else "" for d in days]
    except Exception:
        return []


def graphics_data(facts: dict, sections: dict, day: datetime, load=None, views: dict | None = None,
                  story_lead: dict | None = None, reports: dict | None = None) -> dict:
    """Everything the page draws, as plain numbers and words."""
    views, reports = views or {}, reports or {}
    if load is None:
        import chart_data

        load = chart_data.load_candles
    w = briefing.weather(facts)
    icon, word = WEATHER_WORDS.get(w, ("⛅", w.title()))
    cond = facts.get("conditions") or {}
    tide_line = " ".join(facts.get("tide") or [])
    days = re.search(r"for (\d+) trading days", tide_line)
    km = facts.get("key_markets") or []
    currents = [{"name": a["name"], "value": a.get("value"), "change": a.get("change_7d"),
                 "pts": a.get("unit_of_changes") == "points", "dollars": a["name"] in DOLLAR_CURRENTS,
                 # Colour by what the move means, not its sign: a rising fear index is bad news, so it shows red.
                 "inverse": any(w in a["name"].lower() for w in INVERSE_WORDS)}
                for a in km if a.get("value") is not None]
    stocks = [{"name": "S&P 500" if "S&P" in a["name"] else "Nasdaq 100", "change_1d": a.get("change_1d"),
               "day_label": briefing.session_word(a.get("session_day")),
               "change_7d": a.get("change_7d"), "spark": _spark(load, *SPARK["SPY" if "S&P" in a["name"] else "QQQ"]),
               "days": _spark_days(load, *SPARK["SPY" if "S&P" in a["name"] else "QQQ"])}
              for a in km if a.get("value") is None]
    coins = [{"name": c["name"], "price": c.get("latest_price"), "change_1d": c.get("change_1d"), "day_label": "24h",
              "change_7d": c.get("change_7d"), "spark": _spark(load, *SPARK[c["name"]]) if c["name"] in SPARK else []}
             for c in facts.get("cryptos") or []]
    # The mood gauges show the news mood as the app does: -100..+100 and its words (feedback 23 Nov 2026).
    moods = {m["market"]: ({"value": m["news_mood"], "words": m["news_mood_words"]}
                           if m.get("news_mood") is not None else None) for m in facts.get("markets") or []}
    story = sections.get("story") or {}
    pool = {s_["name"]: s_ for s_ in stocks} | {c["name"]: c for c in coins}
    alias = {"S&P 500 (the SPY fund)": "S&P 500", "Nasdaq 100 (the QQQ fund)": "Nasdaq 100"}
    hit = pool.get(alias.get(story.get("asset", ""), story.get("asset", "")))
    if hit is None:                                    # a current (gold, oil, the fear index): no chart, its number
        cur = next((c for c in currents if c["name"] == story.get("asset")), None)
        hit = {"name": cur["name"], "value": cur["value"], "change_7d": cur["change"], "inverse": cur["inverse"],
               "pts": cur["pts"], "dollars": cur["dollars"]} if cur else None
    events = []
    for e in (facts.get("events") or [])[:3]:
        events.append({"what": e.get("what"), "when": e.get("when_utc"), "why": e.get("why")})
    return {
        "date": day.strftime("%A %d %B %Y").replace(" 0", " "), "weather": w, "weather_icon": icon,
        "weather_word": word, "headline": sections["headline"],
        "tide": {"state": cond.get("tide") or "", "sea": cond.get("sea") or "", "days": int(days.group(1)) if days else None},
        "currents": currents, "stocks": stocks, "stock_mood": moods.get("stock market"),
        "coins": coins, "crypto_mood": moods.get("crypto"), "events": events,
        "story": {"title": story.get("title", ""), "asset": None if story_lead else hit},
        "lead": ({k: story_lead.get(k) for k in ("market", "title", "source", "why", "moves")} if story_lead else None),
        # Each Market sentiment card as the app shows it: score, words, colour, its strip and its summary.
        "cards": {key: ({"score": v["score"], "words": v["words"], "colour": v["colour"], "bg": v["bg"],
                         "arrow": v["arrow"], "summary": v["summary"],
                         # Drawn at the app's scale and enlarged on the page (zoom), so the dots and the
                         # agree/mixed/split word stay in proportion.
                         "strip": strip_svg(reports.get(key), 300),
                         "strip_port": strip_svg(reports.get(key), 210),
                         "lead": ({k: v["lead"].get(k) for k in ("title", "source", "why", "quiet")}
                                  if v.get("lead") else None)} if v else None)
                  for key, v in views.items()},
        "weekend": day.weekday() >= 5,
        "brand": {"show": bool(brand.SHOW_IN_VIDEO), "name": brand.NAME, "domain": brand.DOMAIN,
                  "company": brand.COMPANY, "year": datetime.now(timezone.utc).year, "logo": _logo_uri(),
                  "cta": CTA_WORDS},
    }


# ------------------------------------------------------------------------------------------------ voice and timeline

def speak(text: str, path: Path, models: Path, voice: str = VOICE, speed: float = SPEED, pitch: float = 0) -> float:
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))
    samples, rate = kokoro.create(briefing._say_numbers(text), voice=voice, speed=speed,
                                  lang="en-gb" if voice.startswith("b") else "en-us")
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm.tobytes())
    if pitch:
        pitch_shift(path, pitch)
    return len(pcm) / rate


def pitch_shift(path: Path, semitones: float) -> None:
    """Raise (+) or lower (-) a voice by semitones, keeping its speed, in place (the same as the avatar lab)."""
    with wave.open(str(path)) as wf:
        rate = wf.getframerate()
    f = 2 ** (semitones / 12)
    tmp = path.with_suffix(".shift.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-af",
                    f"asetrate={rate}*{f},aresample={rate},atempo={1 / f}", str(tmp)], check=True)
    tmp.replace(path)


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


SPEECH_TAIL = 0.35              # the presenter holds still this long after the last word, then the shot ends


def speech_seconds(path: Path) -> float:
    """How long a presenter clip runs until the last word (plus a short tail). The talking-avatar tool sometimes pads
    a clip with a second or two of mouth movement after the voice ends (23 Nov 2026: the Admiral's sign-off), so the
    shot is cut where the clip's own sound goes quiet for good. The whole clip when it has no quiet tail."""
    whole = duration(path)
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-vn", "-af", "silencedetect=n=-38dB:d=0.25",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", out)]
    runs_out = starts and (len(ends) < len(starts) or ends[-1] >= whole - 0.1)   # ffmpeg closes it at the end
    end = whole
    if runs_out and 0.5 < starts[-1] < whole:                                  # a silence that runs to the end
        end = min(whole, starts[-1] + SPEECH_TAIL)
    # The tail can also be a faint hum, not silence (24 Nov 2026: the Deckhand's lips moved on after his sign-off).
    # So the voice's end is also found from loudness: the last moment within 24 dB of the clip's loudest.
    last = last_voiced(path)
    if last and 0.5 < last < end:
        end = min(end, last + SPEECH_TAIL)
    return round(end, 3)


def last_voiced(path: Path, below_peak: float = 24.0) -> float | None:
    """The time of the last 50 ms of the clip's sound within `below_peak` dB of its loudest, or None."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-af",
                          "aresample=8000,asetnsamples=400,astats=metadata=1:reset=1,"
                          "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"],
                         capture_output=True, text=True).stdout
    times = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", out)]
    levels = [float(x) if x not in ("-inf", "inf", "nan") else -200.0
              for x in re.findall(r"RMS_level=(-?inf|nan|-?[0-9.]+)", out)]
    pairs = list(zip(times, levels))
    if not pairs:
        return None
    peak = max(level for _, level in pairs)
    loud = [t for t, level in pairs if level > peak - below_peak]
    return (loud[-1] + 0.05) if loud else None


def big_day(day: datetime, facts: dict | None) -> bool:
    """A CPI or jobs-report day (the week's events in the facts name it with today's date)."""
    when = day.strftime("%d %B").lstrip("0")
    for e in (facts or {}).get("events") or []:
        text = f"{e.get('what', '')} {e.get('when_utc', '')}"
        if any(w.lower() in text.lower() for w in BIG_DAY_WORDS) and when in text.replace(" 0", " "):
            return True
    return False


def presenter_for(day: datetime, library: Path | None = None, override: str | None = None,
                  facts: dict | None = None) -> str:
    """Who presents: the override, else a weighted draw for the day (CHANCES) among presenters whose clips are in the
    library; the captain when nobody else's are. On CPI and jobs-report days the Admiral comes aboard 4 times in 10."""
    if override in PRESENTERS:
        return override if library is None or override == "cap" or has_set(library, override) else "cap"
    pool = {who: w for who, w in CHANCES.items() if who == "cap" or library is None or has_set(library, who)}
    if "admiral" in pool and big_day(day, facts):
        pool["admiral"] = (sum(pool.values()) - pool["admiral"]) * 2 / 3
    roll = random.Random(f"presenter-{day.date().isoformat()}").random() * sum(pool.values())
    for who, weight in pool.items():
        roll -= weight
        if roll < 0:
            return who
    return "cap"


def captain_clips(weather: str, rng: random.Random, weekend: bool = False, who: str = "cap") -> list[tuple[str, str]]:
    """[(segment kind, clip name)] in running order, for the day's presenter (the captain by default)."""
    pick = lambda base: f"{who}_{base}_{rng.choice((1, 2))}_1.mp4"     # noqa: E731  (avatar lab names: <id>_1.mp4)
    # The story now comes after the Tide, so the crew's "First, the story of the day" (their first story line) no
    # longer fits: they use their second (the Captain's two both fit).
    story = pick("sign_story") if who == "cap" else f"{who}_sign_story_2_1.mp4"
    out = [("welcome", pick("welcome_weekend" if weekend else "welcome")), ("weather", pick(f"weather_{weather}")),
           ("sign_tides", pick("sign_tides")), ("sign_story", story)]
    if not weekend:
        out.append(("sign_equities", pick("sign_equities")))
    return out + [("sign_crypto", pick("sign_crypto")), ("sign_horizon", pick("sign_horizon")),
                  ("signoff", pick("signoff"))]


def _logo_uri() -> str:
    """The whole MarketNavi logo for dark backgrounds, for the opening and closing cards."""
    import base64
    path = Path(__file__).resolve().parent / "assets" / "brand" / "full-dark-tight.png"
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode() if path.exists() else ""


# Opening and closing (21 Nov 2026): the whole logo, large, with the name spoken over the music at the start; at the
# end, after the presenter's "Fair winds and following seas", a pause, then the logo again with the closing line.
SPOKEN_NAME = "Market Navi"                 # how the voice says MarketNavi
# 📣 The call to action at the very end (24 Nov 2026): on the closing card and said once, after the sign-off.
CTA_WORDS = "Join the beta at marketnavi.ai"
# Spelt for the voice (24 Nov 2026): "A I" and "ay eye" both came out "aye aye" (ɐ aɪ / aɪ aɪ); the voice's own
# phonemes for "A-I" are eɪ aɪ, the two letters.
CTA_SPOKEN = "To listen to or read the full version, and to join the beta, visit Market Navi dot A-I."
CLOSE_VOICE, CLOSE_SPEED = "bf_emma", 1.0
INTRO_HOLD = 1.6                            # the logo stays this long after the opening words
OUTRO_PAUSE = 1.0                           # music only, between the sign-off and the closing line


def pick_look(library: Path | None, clip: str, rng: random.Random) -> str:
    """A second look of the same line, when the library has one: <id>_2.mp4 beside <id>_1.mp4 (for example King
    Neptune with his trident, kept where it did not glitch). Picks one at random to keep the days fresh."""
    if library is None or not clip.endswith("_1.mp4"):
        return clip
    other = clip[: -len("_1.mp4")] + "_2.mp4"
    return rng.choice((clip, other)) if (library / other).exists() else clip


def timeline(caps: dict, narr: dict) -> list[dict]:
    """Segments [{kind, start, end, clip?, audio?}] from the clip and voice lengths (seconds)."""
    # The Morning Outlook's order (24 Nov 2026): the Tide, the story of the day, then each market's sentiment card
    # and its numbers.
    order = [("cap", "welcome"), ("narr", "date"), ("cap", "weather"), ("cap", "sign_tides"), ("narr", "tides"),
             ("cap", "sign_story"), ("narr", "story"), ("cap", "sign_equities"), ("narr", "stock_mood"),
             ("narr", "equities"), ("cap", "sign_crypto"), ("narr", "crypto_mood"), ("narr", "crypto"),
             ("cap", "sign_horizon"), ("narr", "horizon"),
             ("cap", "signoff"), ("cap", "tag"), ("cap", "reveal"), ("narr", "close")]
    order = [(who, kind) for who, kind in order if kind in (caps if who == "cap" else narr)]   # weekends: no equities
    if "blooper" in caps and ("narr", caps["blooper"]["after"]) in order:
        order.insert(order.index(("narr", caps["blooper"]["after"])) + 1, ("cap", "blooper"))
    if "intro" in narr:
        order = [("narr", "intro")] + order
    t, out = (0.3 if "intro" in narr else 0.6), []     # a breath of music first
    for who, kind in order:
        src = caps[kind] if who == "cap" else narr[kind]
        length = src["seconds"] + (0.35 if who == "narr" else 0.0)
        if kind == "intro":
            length += INTRO_HOLD
        if kind == "close":
            length += 3.0                               # the end card holds while the music fades
            if "intro" in narr:
                t += OUTRO_PAUSE
        seg = {"kind": kind, "who": who, "start": round(t, 3), "end": round(t + length, 3)}
        if who == "cap" and src.get("title"):
            seg["title"] = src["title"]                 # a guest's cameo: their own name on the badge
        if who == "cap" and src.get("caption"):
            seg["caption"] = src["caption"]             # a blooper's own words beside it
        seg["clip" if who == "cap" else "audio"] = src["file"]
        out.append(seg)
        t += length + GAP
    return out


# ------------------------------------------------------------------------------------------------ rendering

LAYOUTS = {"land": {"size": (1920, 1080), "box": (120, 150, 600, 812)},
           "port": {"size": (1080, 1920), "box": (180, 210, 720, 974)}}


def rounded_mask(path: Path, w: int, h: int, radius: int = 36) -> None:
    from PIL import Image, ImageDraw

    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    m.save(path)


EFFECTS = {"cook": "sway", "rat": "flicker", "ratd": "flicker", "nav": "zoom"}
SWAY = 0.03                      # the Cook's galley rolls about 1.7 degrees each way (was 0.7; 23 Nov 2026)
ZOOM = 0.72                      # the Navigator's clips: framed above the ship's wheel, which doesn't turn with her hands


def clip_effect(clip: str, bw: int, bh: int) -> str:
    """The ffmpeg filters that fit a presenter clip into its box, with the presenter's movement (23 Nov 2026): the
    Cook's galley sways gently with the roll of the ship; the Rat's candle flickers over him."""
    fit = f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
    effect = EFFECTS.get(clip.split("_")[0])
    if effect == "sway":
        big_w, big_h = int(bw * 1.1) // 2 * 2, int(bh * 1.1) // 2 * 2
        return (f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h},"
                f"rotate=a='{SWAY}*sin(2*PI*t/4.5)':c=black,crop={bw}:{bh},")
    if effect == "zoom":
        return f"crop=iw*{ZOOM}:ih*{ZOOM}:(iw-ow)/2:0," + fit
    if effect == "flicker":
        return fit + "eq=brightness='0.035*sin(2*PI*t*1.7)+0.02*sin(2*PI*t*4.3)':eval=frame,"
    return fit


def render_layout(layout: str, spec: dict, segs: list[dict], library: Path, music: Path, work: Path, out: Path) -> Path:
    W, H = LAYOUTS[layout]["size"]
    bx, by, bw, bh = LAYOUTS[layout]["box"]
    total = segs[-1]["end"] + 0.2
    graphics = work / f"graphics_{layout}.mp4"
    page_spec = work / f"spec_{layout}.json"
    page_spec.write_text(json.dumps({**spec, "layout": layout, "segments": segs, "box": [bx, by, bw, bh],
                                     "total": total}, ensure_ascii=False))
    subprocess.run(["node", str(RENDER), str(PAGE), str(page_spec), str(graphics), str(W), str(H), str(total), str(FPS)],
                   check=True)
    mask = work / f"mask_{layout}.png"
    rounded_mask(mask, bw, bh)
    caps = [s for s in segs if s["who"] == "cap"]
    narr = [s for s in segs if s["who"] == "narr"]
    args = ["ffmpeg", "-y", "-v", "error", "-i", str(graphics), "-loop", "1", "-i", str(mask)]
    for s in caps:
        args += ["-i", str(library / s["clip"])]
    for s in narr:
        args += ["-i", str(s["audio"])]
    args += ["-stream_loop", "-1", "-i", str(music)]
    f, n_caps = [], len(caps)
    f.append(f"[1:v]format=gray,split={n_caps}" + "".join(f"[m{i}]" for i in range(n_caps)))
    last = "[0:v]"
    for i, s in enumerate(caps):
        k = 2 + i
        f.append(f"[{k}:v]{clip_effect(s['clip'], bw, bh)}fps={FPS},format=rgba,setpts=PTS-STARTPTS[c{i}]")
        f.append(f"[m{i}]fps={FPS},trim=duration={s['end'] - s['start']:.3f},setpts=PTS-STARTPTS[mm{i}];"
                 f"[c{i}][mm{i}]alphamerge,setpts=PTS-STARTPTS+{s['start']}/TB[ca{i}]")
        f.append(f"{last}[ca{i}]overlay={bx}:{by}:enable='between(t,{s['start']},{s['end']})':eof_action=pass[v{i}]")
        last = f"[v{i}]"
    voices = []
    for i, s in enumerate(caps):
        f.append(f"[{2 + i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={int(s['start'] * 1000)}:all=1[ac{i}]")
        voices.append(f"[ac{i}]")
    base = 2 + n_caps
    for j, s in enumerate(narr):
        f.append(f"[{base + j}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={int(s['start'] * 1000)}:all=1[an{j}]")
        voices.append(f"[an{j}]")
    f.append("".join(voices) + f"amix=inputs={len(voices)}:normalize=0,volume=1.6,apad=whole_dur={total}[vo]")
    f.append("[vo]asplit[vk][vm]")
    mi = base + len(narr)
    f.append(f"[{mi}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total},asetpts=PTS-STARTPTS,volume=0.55,"
             f"afade=t=in:st=0:d=0.5,afade=t=out:st={max(total - 3.0, 0)}:d=3[mu]")
    f.append("[mu][vk]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=500[md]")
    f.append("[md][vm]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]")
    tmp = out.with_suffix(".tmp.mp4")
    args += ["-filter_complex", ";".join(f), "-map", last, "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264",
             "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
             "-movflags", "+faststart", str(tmp)]
    subprocess.run(args, check=True)
    tmp.rename(out)
    return out


SCREENS = HERE / "video" / "daily" / "screens"
# A screen the live capture (video/daily_screens.js) couldn't take, and that has no stored copy yet, falls back to the
# nearest of the first fixed pictures (21 Nov 2026).
SCREEN_FALLBACK = {"dashboard": "snapshot", "stock_card": "table", "crypto_card": "table", "btc_chart": "chart",
                   "calendar": "tides"}


def ensure_screens(folder: Path = SCREENS) -> list[str]:
    """Make sure every screen the page uses exists; returns the ones filled from a fallback."""
    filled = []
    for name, spare in SCREEN_FALLBACK.items():
        target, source = folder / f"{name}.jpg", folder / f"{spare}.jpg"
        if not target.exists() and source.exists():
            target.write_bytes(source.read_bytes())
            filled.append(name)
    return filled


def build(supabase, library: Path, music_dir: Path, out_dir: Path, models: Path, now: datetime | None = None,
          edition: str = "east", presenter: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "work"
    work.mkdir(exist_ok=True)
    # The video carries the date it is made on, in its edition's zone (Angus, 24 Nov 2026: a test made on Tuesday
    # afternoon was branded Wednesday). The daily run comes after the Asia & Europe edition, early morning there.
    day = briefing.local_now(briefing.EDITIONS[edition]["zone"], now)
    refresh_moods(supabase)
    facts = briefing.general_facts(supabase, now)
    reports = app_moods(supabase)
    views = {key: mood_view(report) for key, report in reports.items()}
    weekend = day.weekday() >= 5
    plan = sections_for(day)
    lead = top_story(views, weekend)
    sections, writer = write_sections(supabase, facts, sections=plan, weekend=weekend, views=views, story=lead)
    spec = graphics_data(facts, sections, day, views=views, story_lead=lead, reports=reports)
    who = presenter_for(day, library, presenter, facts)
    crew = PRESENTERS[who]
    spec["presenter"] = {"key": who, "title": crew["title"]}
    # The headline is the story of the day's, told after the Tide: so the date line says so (Angus, 24 Nov 2026).
    date_line = (f"{day.strftime('%A')}, the {_ordinal(day.day)} of {day.strftime('%B')}. {sections['headline']}. "
                 "More on that after a look at the tides.")
    edition_name = "Weekend Outlook" if weekend else "Morning Outlook"
    close_line = f"That was your {edition_name} for {day.strftime('%A')} the {_ordinal(day.day)} of {day.strftime('%B')}."
    if brand.SHOW_IN_VIDEO:
        close_line = close_line[:-1] + f", brought to you by {SPOKEN_NAME}. {CTA_SPOKEN}"
    texts = {"date": date_line, **{k: (sections[k]["text"] if isinstance(sections[k], dict) else sections[k]) for k in plan},
             "close": close_line,
             **({"intro": f"{SPOKEN_NAME}. AI-powered market navigation."} if brand.SHOW_IN_VIDEO else {})}
    narr = {}
    for kind, text in texts.items():
        path = work / f"narr_{kind}.wav"
        # The closing lines are Emma's, the voice of the app's daily briefing and the training videos (24 Nov 2026).
        voice, speed, pitch = ((CLOSE_VOICE, CLOSE_SPEED, 0) if kind == "close"
                               else (crew["voice"], crew["speed"], crew.get("pitch", 0)))
        narr[kind] = {"file": str(path), "seconds": speak(text, path, models, voice, speed, pitch), "text": text}
    rng = random.Random(day.date().isoformat())
    caps = {}
    for kind, clip in captain_clips(spec["weather"], rng, weekend, who):
        clip = pick_look(library, clip, rng)
        caps[kind] = {"file": clip, "seconds": speech_seconds(library / clip)}
    tag = f"ratd_tag_{rng.choice((1, 2))}_1.mp4"
    if who == "rat" and rng.random() < RAT_TAG_CHANCE and (library / tag).exists():
        caps["tag"] = {"file": tag, "seconds": speech_seconds(library / tag)}
    reveal_roll = random.Random(f"reveal-{day.date().isoformat()}").random()
    if who == "cook" and reveal_roll < COOK_REVEAL_CHANCE and (library / COOK_REVEAL).exists():
        caps["reveal"] = {"file": COOK_REVEAL, "seconds": duration(library / COOK_REVEAL)}
    blooper = blooper_for(day, who, library, narr, spec["weather"])
    if blooper:
        caps["blooper"] = {"file": blooper["file"], "seconds": duration(library / blooper["file"]),
                           "after": blooper["after"], "title": "Blooper",
                           "caption": BLOOPERS[blooper["file"]]["caption"]}
    guest = guest_for(day, facts, library)
    if guest:
        for kind, line in (("welcome", "welcome"), ("signoff", "signoff")):
            clip = pick_look(library, f"{guest}_{line}_1_1.mp4", rng)
            caps[kind] = {"file": clip, "seconds": speech_seconds(library / clip), "title": GUESTS[guest]}
        spec["guest"] = {"key": guest, "title": GUESTS[guest]}
    segs = timeline(caps, narr)
    filled = ensure_screens()
    if filled:
        print(f"App screens from the first fixed pictures: {', '.join(filled)}")
    music = music_dir / MUSIC.get(spec["weather"], "3-Cloudy.mp3")
    made = {}
    for layout in LAYOUTS:
        made[layout] = str(render_layout(layout, {"data": spec}, segs, library, music, work,
                                         out_dir / f"forecast_{day.date().isoformat()}_{layout}.mp4"))
    (out_dir / "script.json").write_text(json.dumps({"writer": writer, "texts": texts, "segments": segs, "spec": spec},
                                                    ensure_ascii=False, indent=1, default=str))
    print(f"Daily video made: {segs[-1]['end']:.0f} s, presented by {crew['title']}, script by {writer}, "
          f"weather {spec['weather']}")
    return {"files": made, "day": day.date().isoformat(), "seconds": round(segs[-1]["end"], 1),
            "presenter": (spec.get("guest") or {}).get("title") or crew["title"], "weather": spec["weather"]}


# ---------------------------------------------------------------------------------------------- in the app
# 🎬 Published to the public "briefings" bucket (21 Nov 2026): video/<day>_<land|port>.mp4, a poster picture each, and
# video/videos.json {day: {made_at, seconds, presenter, weather}}. A week is kept, like the briefings. The app plays
# the newest once a day when a member opens it (Settings can switch that off), and keeps a box to watch it again.
VIDEO_FOLDER = "video"
KEEP_VIDEOS = 7


def videos_meta(db) -> dict:
    try:
        return json.loads(db.storage.from_(briefing.BUCKET).download(f"{VIDEO_FOLDER}/videos.json"))
    except Exception:
        return {}


def video_due(db, now: datetime | None = None) -> str:
    """The day of today's video when it should be made now ("" when not): the Asia & Europe edition of the Morning
    forecast is made for that day and its video isn't yet."""
    import run_briefings
    now = now or datetime.now(timezone.utc)
    _at, eid = briefing.edition_slot("east", now)
    if eid not in run_briefings._meta(db, briefing.GENERAL):
        return ""
    return "" if eid[:10] in videos_meta(db) else eid[:10]


def compress(src: Path, dst: Path, layout: str) -> Path:
    """A phone-friendly copy (720p, about 5 to 8 MB for 90 seconds) and its poster picture."""
    size = "1280:720" if layout == "land" else "720:1280"
    tmp = dst.with_name(dst.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"scale={size}", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.rename(dst)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "4", "-i", str(dst), "-frames:v", "1", "-q:v", "4",
                    str(dst.with_suffix(".jpg"))], check=True)
    return dst


def publish(db, made: dict, work: Path) -> None:
    import run_briefings
    day = made["day"]
    out = os.getenv("GITHUB_OUTPUT")                  # the social step posts exactly this day (not a cached "newest")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"day={day}\n")
    for layout, path in made["files"].items():
        small = compress(Path(path), work / f"{day}_{layout}.mp4", layout)
        run_briefings._upload(db, f"{VIDEO_FOLDER}/{day}_{layout}.mp4", small.read_bytes(), "video/mp4")
        run_briefings._upload(db, f"{VIDEO_FOLDER}/{day}_{layout}.jpg", small.with_suffix(".jpg").read_bytes(),
                              "image/jpeg")
        print(f"Published {layout}: {small.stat().st_size / 1e6:.1f} MB")
    script = work / "script.json"
    if script.exists():                                  # "Read it" in the app: what the presenter and narrator say
        texts = json.loads(script.read_text()).get("texts") or {}
        run_briefings._upload(db, f"{VIDEO_FOLDER}/{day}.txt",
                              "\n\n".join(str(v) for v in texts.values() if v).encode(), "text/plain")
    meta = videos_meta(db)
    meta[day] = {"made_at": datetime.now(timezone.utc).isoformat(), "seconds": made["seconds"],
                 "presenter": made["presenter"], "weather": made["weather"]}
    keep = sorted(meta, reverse=True)[:KEEP_VIDEOS]
    old = [d for d in meta if d not in keep]
    meta = {d: meta[d] for d in keep}
    run_briefings._upload(db, f"{VIDEO_FOLDER}/videos.json", json.dumps(meta).encode(), "application/json")
    if old:
        try:
            db.storage.from_(briefing.BUCKET).remove([f"{VIDEO_FOLDER}/{d}_{lay}.{x}" for d in old
                                                     for lay in LAYOUTS for x in ("mp4", "jpg")]
                                                    + [f"{VIDEO_FOLDER}/{d}.txt" for d in old])
        except Exception as exc:
            print(f"Old videos not removed: {type(exc).__name__}")


def main() -> int:
    import run_briefings

    a = sys.argv
    get = lambda flag, default=None: a[a.index(flag) + 1] if flag in a else default     # noqa: E731
    db, _url = run_briefings._client()
    if "--check" in a:                              # alerts.yml: start the video job when today's is due
        print(video_due(db) or "0")
        return 0
    if "--publish-from" in a:                       # publish a reviewed test exactly as it is (24 Nov 2026)
        src = Path(get("--publish-from"))
        script = json.loads((src / "script.json").read_text())
        files = {layout: str(next(src.glob(f"forecast_*_{layout}.mp4"))) for layout in LAYOUTS}
        day = Path(files["land"]).name.split("_")[1]
        spec = script.get("spec") or {}
        made = {"files": files, "day": day, "seconds": round(script["segments"][-1]["end"], 1),
                "presenter": ((spec.get("guest") or {}).get("title") or (spec.get("presenter") or {}).get("title")
                              or "The Captain"), "weather": spec.get("weather")}
        publish(db, made, src)
        return 0
    out = Path(get("--out", "out/daily_video"))
    made = build(db, Path(get("--library")), Path(get("--music")), out,
                 Path(get("--models", "out/video/voice_model")), edition=get("--edition", "east"),
                 presenter=get("--presenter") or None)
    if "--publish" in a:
        publish(db, made, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
