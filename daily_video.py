"""
🎬 The daily forecast video (20 Nov 2026): about 90 seconds for social media, made from the same facts as the
Morning forecast (briefing.general_facts), in two shapes: 16:9 (YouTube) and 9:16 (Shorts, TikTok, Reels).

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
# Words for each section, for about 90 seconds in all. Weekends (stock markets shut) drop equities and give crypto
# the time instead.
# 📰 news_stocks / news_crypto (24 Nov 2026): each market's dominant headline, after its numbers. A few words come
# off the Tide and the markets so the video stays about the same length.
SECTIONS = {"story": 30, "tides": 26, "equities": 22, "news_stocks": 24, "crypto": 26, "news_crypto": 24, "horizon": 18}
WEEKEND_SECTIONS = {"story": 30, "tides": 26, "crypto": 36, "news_crypto": 26, "horizon": 18}
NEWS_KINDS = {"news_stocks": "stock", "news_crypto": "crypto"}      # section -> market_mood key


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


# ------------------------------------------------------------------------------------------------ the headlines

NEWS_MAX = 8


def refresh_news(supabase) -> None:
    """Rewrite the crypto and stock market sentiment just before the video is made, so its headlines are the latest
    (24 Nov 2026). Articles already scored keep their scores, and the 12-hour clock restarts from here, so the
    twice-daily refresh falls in step with the video."""
    try:
        import ai_providers
        import market_store
        import sentiment
        import shared_refresh

        sentiment.set_provider(ai_providers.app_choice(supabase, "sentiment"))
        if not sentiment.sentiment_ready():
            print("News refresh skipped: no sentiment AI key.")
            return
        moods = market_store.load_market_moods(supabase) or {}
        for spec in sentiment.MACRO_MOODS:
            shared_refresh._save_mood(supabase, spec, previous=shared_refresh._previous_report(moods.get(spec["key"])))
    except Exception as exc:
        print(f"News refresh skipped: {str(exc)[:160]}")


def headline_rows(report: dict | None) -> list[dict]:
    """A market's scored headlines as the video uses them: {i, title, source, mood (-100..100), words}."""
    rows = []
    for row in ((report or {}).get("headlines") or []):
        if not isinstance(row, dict) or not row.get("title") or row.get("score") is None:
            continue
        mood = briefing.news_mood(row["score"])
        if not mood:
            continue
        rows.append({"i": len(rows), "title": briefing.clean(str(row["title"]))[:160],
                     "source": str(row.get("source") or "")[:40], "note": briefing.clean(str(row.get("note") or ""))[:200],
                     "mood": mood["news_mood"], "words": mood["news_mood_words"],
                     "colour": score_colours.sentiment_tone(row["score"])[0]})       # the app's colour for it
        if len(rows) >= NEWS_MAX:
            break
    return rows


def news_facts(supabase) -> dict:
    """{"stock": [...], "crypto": [...]}: each market's latest scored headlines."""
    try:
        import market_store

        moods = market_store.load_market_moods(supabase) or {}
    except Exception:
        moods = {}
    return {key: headline_rows((moods.get(key) or {}).get("sentiment_report")) for key in ("stock", "crypto")}


def top_headline(rows: list[dict]) -> dict | None:
    """Without the AI: the headline that reads strongest either way."""
    return max(rows, key=lambda r: abs(r["mood"]), default=None)


# ------------------------------------------------------------------------------------------------ the script

ASK = {
    "story": "\"story\": {\"title\": at most 6 words, \"text\": about %d words, \"asset\": the name of the one market "
             "or coin it is about exactly as given in the facts, or \"\"} for the story of the day: the single "
             "standout (the biggest mover, a turn in the Tide, a jump in the fear index, a big event)",
    "tides": "\"tides\": about %d words on the Tide (the macro backdrop: risk-on or defensive, for how long), the "
             "sea state and the strongest currents (dollar, gold, oil, fear index)",
    "equities": "\"equities\": about %d words on the S&P 500 and Nasdaq moves and the stock-market mood",
    "crypto": "\"crypto\": about %d words on Bitcoin, Ether and the other top coins and the crypto mood",
    "horizon": "\"horizon\": about %d words on the next scheduled events",
    "news_stocks": "\"news_stocks\": {\"text\": about %d words on the single most important story in "
                   "stock_headlines (the one most articles are about, or the one that moves markets most): what "
                   "happened, then how the stock headlines read overall, \"pick\": that headline's i}",
    "news_crypto": "\"news_crypto\": {\"text\": about %d words on the single most important story in "
                   "crypto_headlines, the same way, \"pick\": that headline's i}",
}


def system_prompt(sections: dict, weekend: bool) -> str:
    parts = ", ".join(ASK[k] % n for k, n in sections.items())
    return (
        "You write the narration for a 90-second daily market video in the style of the shipping forecast: calm, "
        "clear, a light nautical flavour that never hides a fact. A ship's captain introduces each section; you write "
        "only what the narrator says inside each section. Write for the ear: short sentences, plain words, numbers "
        "rounded and said naturally (\"about 2 percent\", \"sixty-two thousand dollars\"), no symbols, no lists, no "
        "brand or app names. Use only the facts given; never invent prices, news or events. Describe; never tell "
        "anyone to buy, sell or hold. Each 1-day change covers exactly the period in its one_day_change_covers: name "
        "that period (\"on Friday\", \"over the last 24 hours\") and never call it today's move unless it says "
        "today. "
        + ("It is the weekend: stock markets are shut, so do not talk about today's stock moves. " if weekend else "")
        + "Reply with JSON only: {\"headline\": a punchy headline of at most 7 words for the day, " + parts + "}."
    )


def _template(facts: dict, sections: dict = SECTIONS) -> dict:
    """The sections without AI, from the facts alone."""
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
    movers = [a for a in (facts.get("key_markets") or []) + coins if a.get("change_1d") is not None]
    big = max(movers, key=lambda a: abs(a["change_1d"]), default=None)
    story = ({"title": f"{big['name']} on the move", "asset": big["name"],
              "text": f"{big['name']} moved {big['change_1d']:+.1f} percent {briefing.move_span(big)}."} if big else
             {"title": "A steady day", "asset": "", "text": "No single market stood out."})
    out = {"headline": "Your morning market forecast", "story": story, "tides": tide, "equities": eq, "crypto": cr,
           "horizon": hz}
    for kind, key in NEWS_KINDS.items():
        rows = (facts.get("headlines") or {}).get(key) or []
        top = top_headline(rows)
        out[kind] = ({"text": f"In the headlines: {top['title']}.", "pick": top["i"]} if top
                     else {"text": "A quiet day in the headlines.", "pick": None})
    return {k: out[k] for k in ("headline", *sections)}


def today_words(out: dict) -> list[str]:
    """The sections that describe a market move as today's: the figures are the last finished session or day, so
    "today" is wrong in them (the headline, the Tide's levels and the horizon may use it)."""
    texts = {k: out.get(k) for k in ("equities", "crypto")} | {"story": (out.get("story") or {}).get("text")}
    return [k for k, v in texts.items() if isinstance(v, str) and re.search(r"\btoday\b|\bthis morning\b", v, re.I)]


def write_sections(supabase, facts: dict, chat=None, sections: dict = SECTIONS, weekend: bool = False) -> tuple[dict, str]:
    """({headline, story {title, text, asset}, tides, equities?, crypto, horizon}, who wrote it)."""
    import ai_providers

    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if ai_providers.available(provider):
        data = {k: briefing.for_ai(facts).get(k) for k in ("conditions", "markets", "tide", "key_markets", "cryptos",
                                                            "events")}
        data["overall_weather"] = briefing.weather(facts)
        for kind, key in NEWS_KINDS.items():
            if kind in sections:
                data[f"{'stock' if key == 'stock' else 'crypto'}_headlines"] = [
                    {k: r[k] for k in ("i", "title", "source", "note", "words")}
                    for r in (facts.get("headlines") or {}).get(key) or []]
        messages = [{"role": "user", "content": json.dumps(data, ensure_ascii=False, default=str)}]
        for _attempt in range(2):
            try:
                reply = (chat or ai_providers.chat)(provider, system_prompt(sections, weekend), messages, max_tokens=1200)
                if isinstance(reply, (tuple, list)):
                    reply = reply[0]
                text = reply.get("text") if isinstance(reply, dict) else str(reply)
                got = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            except Exception as exc:
                print(f"Video script by AI failed: {str(exc)[:160]}")
                break
            story = got.get("story") if isinstance(got.get("story"), dict) else None
            news = [k for k in sections if k in NEWS_KINDS]
            plain = [k for k in ("headline", *sections) if k != "story" and k not in NEWS_KINDS]
            if not (story and str(story.get("text") or "").strip() and all(
                    isinstance(got.get(k), str) and got[k].strip() for k in plain) and all(
                    isinstance(got.get(k), dict) and str(got[k].get("text") or "").strip() for k in news)):
                break
            out = {k: briefing.clean(got[k]) for k in plain}
            out["story"] = {"title": briefing.clean(str(story.get("title") or "")) or "The story of the day",
                            "text": briefing.clean(str(story["text"])), "asset": str(story.get("asset") or "")}
            for k in news:
                rows = (facts.get("headlines") or {}).get(NEWS_KINDS[k]) or []
                pick = got[k].get("pick")
                pick = pick if isinstance(pick, int) and 0 <= pick < len(rows) else (top_headline(rows) or {}).get("i")
                out[k] = {"text": briefing.clean(str(got[k]["text"])), "pick": pick}
            wrong = today_words(out)
            if not wrong:
                return out, provider
            # A move called "today" when it is Friday's session or the last 24 hours (feedback 23 Nov 2026).
            messages = messages + [{"role": "assistant", "content": text},
                                   {"role": "user", "content": "These parts call a move today's, but every change "
                                    "covers the period in its one_day_change_covers: " + ", ".join(wrong) + ". Write "
                                    "it again naming each period, JSON only."}]
    return _template(facts, sections), "template"


# ------------------------------------------------------------------------------------------------ the graphics' data

def _spark(load, kind: str, asset_id: str) -> list[float]:
    """The last 7 days as hourly closes (feedback 23 Nov 2026: the line, its colour and the week's change all cover
    the same 7 days, and the latest move shows at the end instead of being squeezed into a 30-day line). Falls back
    to daily closes when hourly candles aren't available."""
    for interval, range_key in (("1h", "7D"), ("1D", "1M")):
        try:
            c = load(kind, asset_id, interval, range_key)["candles"]
            c = c[~c["forming"]] if "forming" in c else c
            if interval == "1D":
                c = c.iloc[-8:]
            vals = [round(float(x), 6) for x in c["close"].dropna().tolist()]
            if len(vals) >= 2:
                return vals
        except Exception:
            continue
    return []


def graphics_data(facts: dict, sections: dict, day: datetime, load=None) -> dict:
    """Everything the page draws, as plain numbers and words."""
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
               "change_7d": a.get("change_7d"), "spark": _spark(load, *SPARK["SPY" if "S&P" in a["name"] else "QQQ"])}
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
        "story": {"title": story.get("title", ""), "asset": hit},
        "news": {kind: {"rows": [{k: r[k] for k in ("title", "source", "mood", "words", "colour")}
                                 for r in (facts.get("headlines") or {}).get(key) or []],
                        "pick": (sections.get(kind) or {}).get("pick")}
                 for kind, key in NEWS_KINDS.items() if kind in sections},
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
    if runs_out and 0.5 < starts[-1] < whole:                                  # a silence that runs to the end
        return round(min(whole, starts[-1] + SPEECH_TAIL), 3)
    return whole


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
    out = [("welcome", pick("welcome_weekend" if weekend else "welcome")), ("weather", pick(f"weather_{weather}")),
           ("sign_story", pick("sign_story")), ("sign_tides", pick("sign_tides"))]
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
CTA_SPOKEN = "Join the beta at Market Navi dot A I."
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
    order = [("cap", "welcome"), ("narr", "date"), ("cap", "weather"), ("cap", "sign_story"), ("narr", "story"),
             ("cap", "sign_tides"), ("narr", "tides"), ("cap", "sign_equities"), ("narr", "equities"),
             ("narr", "news_stocks"), ("cap", "sign_crypto"), ("narr", "crypto"), ("narr", "news_crypto"),
             ("cap", "sign_horizon"), ("narr", "horizon"),
             ("cap", "signoff"), ("cap", "tag"), ("cap", "reveal"), ("narr", "close")]
    order = [(who, kind) for who, kind in order if kind in (caps if who == "cap" else narr)]   # weekends: no equities
    if "blooper" in caps and ("narr", caps["blooper"]["after"]) in order:
        at = order.index(("narr", caps["blooper"]["after"])) + 1
        if at < len(order) and order[at][1] in NEWS_KINDS:       # a market's headlines stay with its numbers
            at += 1
        order.insert(at, ("cap", "blooper"))
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


def build(supabase, library: Path, music_dir: Path, out_dir: Path, models: Path, now: datetime | None = None,
          edition: str = "east", presenter: str | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "work"
    work.mkdir(exist_ok=True)
    day = briefing.local_now(briefing.EDITIONS[edition]["zone"], now + timedelta(hours=6))
    refresh_news(supabase)
    facts = briefing.general_facts(supabase, now)
    facts["headlines"] = news_facts(supabase)
    weekend = day.weekday() >= 5
    plan = sections_for(day)
    sections, writer = write_sections(supabase, facts, sections=plan, weekend=weekend)
    spec = graphics_data(facts, sections, day)
    who = presenter_for(day, library, presenter, facts)
    crew = PRESENTERS[who]
    spec["presenter"] = {"key": who, "title": crew["title"]}
    date_line = f"{day.strftime('%A')}, the {_ordinal(day.day)} of {day.strftime('%B')}. {sections['headline']}."
    close_line = f"That was your {'weekend' if weekend else 'daily'} market briefing for {day.strftime('%A')} the {_ordinal(day.day)} of {day.strftime('%B')}."
    if brand.SHOW_IN_VIDEO:
        close_line = close_line[:-1] + f", brought to you by {SPOKEN_NAME}. {CTA_SPOKEN}"
    texts = {"date": date_line, **{k: (sections[k]["text"] if isinstance(sections[k], dict) else sections[k]) for k in plan},
             "close": close_line,
             **({"intro": f"{SPOKEN_NAME}. AI-powered market navigation."} if brand.SHOW_IN_VIDEO else {})}
    narr = {}
    for kind, text in texts.items():
        path = work / f"narr_{kind}.wav"
        narr[kind] = {"file": str(path), "seconds": speak(text, path, models, crew["voice"], crew["speed"],
                                                          crew.get("pitch", 0)),
                      "text": text}
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
    out = Path(get("--out", "out/daily_video"))
    made = build(db, Path(get("--library")), Path(get("--music")), out,
                 Path(get("--models", "out/video/voice_model")), edition=get("--edition", "east"),
                 presenter=get("--presenter") or None)
    if "--publish" in a:
        publish(db, made, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
