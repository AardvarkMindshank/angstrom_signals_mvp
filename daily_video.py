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
# Who presents is a surprise each day (Angus, 23 Nov 2026), a weighted draw seeded by the date, so a video re-made
# the same day keeps its presenter. No clips are tied to a weekday. Presenters whose clip set isn't in the library
# yet are left out of the draw; the captain is always in it.
CHANCES = {"cap": 0.40, "mate": 0.25, "nav": 0.14, "deck": 0.14, "cat": 0.07}
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
INVERSE_WORDS = ("fear", "vix", "volatility")    # metrics where up is bad: their rises show red, falls green
SPARK = {"SPY": ("equity", "SPY"), "QQQ": ("equity", "QQQ"), "Bitcoin": ("crypto", "bitcoin"),
         "Ether": ("crypto", "ethereum"), "Solana": ("crypto", "solana"), "XRP": ("crypto", "ripple"),
         "BNB": ("crypto", "binancecoin")}
# Words for each section, for about 90 seconds in all. Weekends (stock markets shut) drop equities and give crypto
# the time instead.
SECTIONS = {"story": 30, "tides": 30, "equities": 26, "crypto": 32, "horizon": 18}
WEEKEND_SECTIONS = {"story": 30, "tides": 30, "crypto": 46, "horizon": 18}


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
}


def system_prompt(sections: dict, weekend: bool) -> str:
    parts = ", ".join(ASK[k] % n for k, n in sections.items())
    return (
        "You write the narration for a 90-second daily market video in the style of the shipping forecast: calm, "
        "clear, a light nautical flavour that never hides a fact. A ship's captain introduces each section; you write "
        "only what the narrator says inside each section. Write for the ear: short sentences, plain words, numbers "
        "rounded and said naturally (\"about 2 percent\", \"sixty-two thousand dollars\"), no symbols, no lists, no "
        "brand or app names. Use only the facts given; never invent prices, news or events. Describe; never tell "
        "anyone to buy, sell or hold. "
        + ("It is the weekend: stock markets are shut, so do not talk about today's stock moves. " if weekend else "")
        + "Reply with JSON only: {\"headline\": a punchy headline of at most 7 words for the day, " + parts + "}."
    )


def _template(facts: dict, sections: dict = SECTIONS) -> dict:
    """The sections without AI, from the facts alone."""
    km = {a["name"]: a for a in facts.get("key_markets") or []}
    coins = facts.get("cryptos") or []
    tide = (facts.get("tide") or ["The Tide is steady."])[0]
    spy = km.get("S&P 500 (the SPY fund)", {})
    eq = f"The S&P 500 moved {spy.get('change_1d', 0):+.1f} percent on the day." if spy else "Equities were mixed."
    btc = coins[0] if coins else {}
    cr = f"Bitcoin moved {btc.get('change_1d', 0):+.1f} percent on the day." if btc else "Crypto was mixed."
    ev = facts.get("events") or []
    hz = f"Next up: {ev[0]['what']}, {ev[0]['when_utc']} UTC." if ev else "A quiet week on the calendar."
    movers = [a for a in (facts.get("key_markets") or []) + coins if a.get("change_1d") is not None]
    big = max(movers, key=lambda a: abs(a["change_1d"]), default=None)
    story = ({"title": f"{big['name']} on the move", "asset": big["name"],
              "text": f"{big['name']} moved {big['change_1d']:+.1f} percent over the last day."} if big else
             {"title": "A steady day", "asset": "", "text": "No single market stood out over the last day."})
    out = {"headline": "Your morning market forecast", "story": story, "tides": tide, "equities": eq, "crypto": cr,
           "horizon": hz}
    return {k: out[k] for k in ("headline", *sections)}


def write_sections(supabase, facts: dict, chat=None, sections: dict = SECTIONS, weekend: bool = False) -> tuple[dict, str]:
    """({headline, story {title, text, asset}, tides, equities?, crypto, horizon}, who wrote it)."""
    import ai_providers

    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if ai_providers.available(provider):
        try:
            data = {k: facts.get(k) for k in ("conditions", "markets", "tide", "key_markets", "cryptos", "events")}
            data["overall_weather"] = briefing.weather(facts)
            reply = (chat or ai_providers.chat)(provider, system_prompt(sections, weekend), [{"role": "user", "content": json.dumps(
                data, ensure_ascii=False, default=str)}], max_tokens=1200)
            if isinstance(reply, (tuple, list)):
                reply = reply[0]
            text = reply.get("text") if isinstance(reply, dict) else str(reply)
            got = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            story = got.get("story") if isinstance(got.get("story"), dict) else None
            plain = [k for k in ("headline", *sections) if k != "story"]
            if story and str(story.get("text") or "").strip() and all(
                    isinstance(got.get(k), str) and got[k].strip() for k in plain):
                out = {k: briefing.clean(got[k]) for k in plain}
                out["story"] = {"title": briefing.clean(str(story.get("title") or "")) or "The story of the day",
                                "text": briefing.clean(str(story["text"])), "asset": str(story.get("asset") or "")}
                return out, provider
        except Exception as exc:
            print(f"Video script by AI failed: {str(exc)[:160]}")
    return _template(facts, sections), "template"


# ------------------------------------------------------------------------------------------------ the graphics' data

def _spark(load, kind: str, asset_id: str, n: int = 30) -> list[float]:
    try:
        c = load(kind, asset_id, "1D", "3M")["candles"]
        c = c[~c["forming"]] if "forming" in c else c
        return [round(float(x), 6) for x in c["close"].dropna().tolist()[-n:]]
    except Exception:
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
                 "pts": a.get("unit_of_changes") == "points",
                 # Colour by what the move means, not its sign: a rising fear index is bad news, so it shows red.
                 "inverse": any(w in a["name"].lower() for w in INVERSE_WORDS)}
                for a in km if a.get("value") is not None]
    stocks = [{"name": "S&P 500" if "S&P" in a["name"] else "Nasdaq 100", "change_1d": a.get("change_1d"),
               "change_7d": a.get("change_7d"), "spark": _spark(load, *SPARK["SPY" if "S&P" in a["name"] else "QQQ"])}
              for a in km if a.get("value") is None]
    coins = [{"name": c["name"], "price": c.get("latest_price"), "change_1d": c.get("change_1d"),
              "change_7d": c.get("change_7d"), "spark": _spark(load, *SPARK[c["name"]]) if c["name"] in SPARK else []}
             for c in facts.get("cryptos") or []]
    moods = {m["market"]: m.get("score_0_to_100") for m in facts.get("markets") or []}
    story = sections.get("story") or {}
    pool = {s_["name"]: s_ for s_ in stocks} | {c["name"]: c for c in coins}
    alias = {"S&P 500 (the SPY fund)": "S&P 500", "Nasdaq 100 (the QQQ fund)": "Nasdaq 100"}
    hit = pool.get(alias.get(story.get("asset", ""), story.get("asset", "")))
    if hit is None:                                    # a current (gold, oil, the fear index): no chart, its number
        cur = next((c for c in currents if c["name"] == story.get("asset")), None)
        hit = {"name": cur["name"], "value": cur["value"], "change_7d": cur["change"], "inverse": cur["inverse"],
               "pts": cur["pts"]} if cur else None
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
        "weekend": day.weekday() >= 5,
        "brand": {"show": bool(brand.SHOW_IN_VIDEO), "name": brand.NAME, "domain": brand.DOMAIN,
                  "company": brand.COMPANY, "year": datetime.now(timezone.utc).year, "logo": _logo_uri()},
    }


# ------------------------------------------------------------------------------------------------ voice and timeline

def speak(text: str, path: Path, models: Path, voice: str = VOICE, speed: float = SPEED) -> float:
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
    return len(pcm) / rate


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def presenter_for(day: datetime, library: Path | None = None, override: str | None = None) -> str:
    """Who presents: the override, else a weighted draw for the day (CHANCES) among presenters whose clips are in the
    library; the captain when nobody else's are."""
    if override in PRESENTERS:
        return override if library is None or override == "cap" or has_set(library, override) else "cap"
    pool = {who: w for who, w in CHANCES.items() if who == "cap" or library is None or has_set(library, who)}
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
             ("cap", "sign_crypto"), ("narr", "crypto"), ("cap", "sign_horizon"), ("narr", "horizon"),
             ("cap", "signoff"), ("narr", "close")]
    order = [(who, kind) for who, kind in order if kind in (caps if who == "cap" else narr)]   # weekends: no equities
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
        f.append(f"[{k}:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},fps={FPS},format=rgba,"
                 f"setpts=PTS-STARTPTS[c{i}]")
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
    facts = briefing.general_facts(supabase, now)
    weekend = day.weekday() >= 5
    plan = sections_for(day)
    sections, writer = write_sections(supabase, facts, sections=plan, weekend=weekend)
    spec = graphics_data(facts, sections, day)
    who = presenter_for(day, library, presenter)
    crew = PRESENTERS[who]
    spec["presenter"] = {"key": who, "title": crew["title"]}
    date_line = f"{day.strftime('%A')}, the {_ordinal(day.day)} of {day.strftime('%B')}. {sections['headline']}."
    close_line = f"That was your {'weekend' if weekend else 'daily'} market briefing for {day.strftime('%A')} the {_ordinal(day.day)} of {day.strftime('%B')}."
    if brand.SHOW_IN_VIDEO:
        close_line = close_line[:-1] + f", brought to you by {SPOKEN_NAME}."
    texts = {"date": date_line, **{k: (sections[k]["text"] if k == "story" else sections[k]) for k in plan},
             "close": close_line,
             **({"intro": f"{SPOKEN_NAME}. AI-powered market navigation."} if brand.SHOW_IN_VIDEO else {})}
    narr = {}
    for kind, text in texts.items():
        path = work / f"narr_{kind}.wav"
        narr[kind] = {"file": str(path), "seconds": speak(text, path, models, crew["voice"], crew["speed"]),
                      "text": text}
    rng = random.Random(day.date().isoformat())
    caps = {}
    for kind, clip in captain_clips(spec["weather"], rng, weekend, who):
        clip = pick_look(library, clip, rng)
        caps[kind] = {"file": clip, "seconds": duration(library / clip)}
    guest = guest_for(day, facts, library)
    if guest:
        for kind, line in (("welcome", "welcome"), ("signoff", "signoff")):
            clip = pick_look(library, f"{guest}_{line}_1_1.mp4", rng)
            caps[kind] = {"file": clip, "seconds": duration(library / clip), "title": GUESTS[guest]}
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
