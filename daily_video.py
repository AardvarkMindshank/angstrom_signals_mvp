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
GAP = 0.25                       # seconds between segments
FPS = 30
MUSIC = {"sunny": "1-Sunshine.mp3", "fair": "2-Springtime.mp3", "changeable": "3-Cloudy.mp3",
         "rough": "4-Rainy.mp3", "stormy": "5-Stormy.mp3"}
WEATHER_WORDS = {"sunny": ("☀️", "Fair and sunny"), "fair": ("🌤️", "Fair"), "changeable": ("⛅", "Changeable"),
                 "rough": ("🌧️", "Rough seas"), "stormy": ("⛈️", "Storm warning")}
SPARK = {"SPY": ("equity", "SPY"), "QQQ": ("equity", "QQQ"), "Bitcoin": ("crypto", "bitcoin"),
         "Ether": ("crypto", "ethereum"), "Solana": ("crypto", "solana"), "XRP": ("crypto", "ripple"),
         "BNB": ("crypto", "binancecoin")}
SECTIONS = {"tides": 38, "equities": 32, "crypto": 38, "horizon": 24}     # words each, for about 90 seconds in all


def _ordinal(n: int) -> str:
    words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
             9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth",
             15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth", 19: "nineteenth",
             20: "twentieth", 21: "twenty-first", 22: "twenty-second", 23: "twenty-third", 24: "twenty-fourth",
             25: "twenty-fifth", 26: "twenty-sixth", 27: "twenty-seventh", 28: "twenty-eighth",
             29: "twenty-ninth", 30: "thirtieth", 31: "thirty-first"}
    return words[n]


# ------------------------------------------------------------------------------------------------ the script

SYSTEM = (
    "You write the narration for a 90-second daily market video in the style of the shipping forecast: calm, "
    "clear, a light nautical flavour that never hides a fact. A ship's captain introduces each section; you write "
    "only what the narrator says inside each section. Write for the ear: short sentences, plain words, numbers "
    "rounded and said naturally (\"about 2 percent\", \"sixty-two thousand dollars\"), no symbols, no lists, no "
    "brand or app names. Use only the facts given; never invent prices, news or events. Describe; never tell anyone "
    "to buy, sell or hold. Reply with JSON only: {\"headline\": a punchy headline of at most 7 words for the day, "
    "\"tides\": about %(tides)d words on the Tide (the macro backdrop: risk-on or defensive, for how long), the sea "
    "state and the strongest currents (dollar, gold, oil, fear index), \"equities\": about %(equities)d words on the "
    "S&P 500 and Nasdaq moves and the stock-market mood, \"crypto\": about %(crypto)d words on Bitcoin, Ether and "
    "the other top coins and the crypto mood, \"horizon\": about %(horizon)d words on the next scheduled events}."
) % SECTIONS


def _template(facts: dict) -> dict:
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
    return {"headline": "Your morning market forecast", "tides": tide, "equities": eq, "crypto": cr, "horizon": hz}


def write_sections(supabase, facts: dict, chat=None) -> tuple[dict, str]:
    """({headline, tides, equities, crypto, horizon}, who wrote it)."""
    import ai_providers

    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if ai_providers.available(provider):
        try:
            data = {k: facts.get(k) for k in ("conditions", "markets", "tide", "key_markets", "cryptos", "events")}
            data["overall_weather"] = briefing.weather(facts)
            reply = (chat or ai_providers.chat)(provider, SYSTEM, [{"role": "user", "content": json.dumps(
                data, ensure_ascii=False, default=str)}], max_tokens=1200)
            if isinstance(reply, (tuple, list)):
                reply = reply[0]
            text = reply.get("text") if isinstance(reply, dict) else str(reply)
            got = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            if all(isinstance(got.get(k), str) and got[k].strip() for k in ("headline", *SECTIONS)):
                return {k: briefing.clean(got[k]) for k in ("headline", *SECTIONS)}, provider
        except Exception as exc:
            print(f"Video script by AI failed: {str(exc)[:160]}")
    return _template(facts), "template"


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
                 "pts": a.get("unit_of_changes") == "points"} for a in km if a.get("value") is not None]
    stocks = [{"name": "S&P 500" if "S&P" in a["name"] else "Nasdaq 100", "change_1d": a.get("change_1d"),
               "change_7d": a.get("change_7d"), "spark": _spark(load, *SPARK["SPY" if "S&P" in a["name"] else "QQQ"])}
              for a in km if a.get("value") is None]
    coins = [{"name": c["name"], "price": c.get("latest_price"), "change_1d": c.get("change_1d"),
              "change_7d": c.get("change_7d"), "spark": _spark(load, *SPARK[c["name"]]) if c["name"] in SPARK else []}
             for c in facts.get("cryptos") or []]
    moods = {m["market"]: m.get("score_0_to_100") for m in facts.get("markets") or []}
    events = []
    for e in (facts.get("events") or [])[:3]:
        events.append({"what": e.get("what"), "when": e.get("when_utc"), "why": e.get("why")})
    return {
        "date": day.strftime("%A %d %B %Y").replace(" 0", " "), "weather": w, "weather_icon": icon,
        "weather_word": word, "headline": sections["headline"],
        "tide": {"state": cond.get("tide") or "", "sea": cond.get("sea") or "", "days": int(days.group(1)) if days else None},
        "currents": currents, "stocks": stocks, "stock_mood": moods.get("stock market"),
        "coins": coins, "crypto_mood": moods.get("crypto"), "events": events,
        "brand": {"show": bool(brand.SHOW_IN_VIDEO), "name": brand.NAME, "domain": brand.DOMAIN},
    }


# ------------------------------------------------------------------------------------------------ voice and timeline

def speak(text: str, path: Path, models: Path) -> float:
    from kokoro_onnx import Kokoro

    kokoro = Kokoro(str(models / "kokoro-v1.0.onnx"), str(models / "voices-v1.0.bin"))
    samples, rate = kokoro.create(briefing._say_numbers(text), voice=VOICE, speed=SPEED, lang="en-gb")
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


def captain_clips(weather: str, rng: random.Random) -> list[tuple[str, str]]:
    """[(segment kind, clip name)] in running order."""
    pick = lambda base: f"cap_{base}_{rng.choice((1, 2))}_1.mp4"     # noqa: E731  (avatar lab names: <id>_1.mp4)
    return [("welcome", pick("welcome")), ("weather", pick(f"weather_{weather}")), ("sign_tides", pick("sign_tides")),
            ("sign_equities", pick("sign_equities")), ("sign_crypto", pick("sign_crypto")),
            ("sign_horizon", pick("sign_horizon")), ("signoff", pick("signoff"))]


def timeline(caps: dict, narr: dict) -> list[dict]:
    """Segments [{kind, start, end, clip?, audio?}] from the clip and voice lengths (seconds)."""
    order = [("cap", "welcome"), ("narr", "date"), ("cap", "weather"), ("cap", "sign_tides"), ("narr", "tides"),
             ("cap", "sign_equities"), ("narr", "equities"), ("cap", "sign_crypto"), ("narr", "crypto"),
             ("cap", "sign_horizon"), ("narr", "horizon"), ("cap", "signoff"), ("narr", "close")]
    t, out = 0.6, []                                  # a breath of music first
    for who, kind in order:
        src = caps[kind] if who == "cap" else narr[kind]
        length = src["seconds"] + (0.35 if who == "narr" else 0.0)
        if kind == "close":
            length += 3.0                               # the end card holds while the music fades
        seg = {"kind": kind, "who": who, "start": round(t, 3), "end": round(t + length, 3)}
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
          edition: str = "east") -> dict:
    now = now or datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "work"
    work.mkdir(exist_ok=True)
    day = briefing.local_now(briefing.EDITIONS[edition]["zone"], now + timedelta(hours=6))
    facts = briefing.general_facts(supabase, now)
    sections, writer = write_sections(supabase, facts)
    spec = graphics_data(facts, sections, day)
    date_line = f"{day.strftime('%A')}, the {_ordinal(day.day)} of {day.strftime('%B')}. {sections['headline']}."
    close_line = f"That was your daily market briefing for {day.strftime('%A')} the {_ordinal(day.day)} of {day.strftime('%B')}."
    texts = {"date": date_line, **{k: sections[k] for k in SECTIONS}, "close": close_line}
    narr = {}
    for kind, text in texts.items():
        path = work / f"narr_{kind}.wav"
        narr[kind] = {"file": str(path), "seconds": speak(text, path, models), "text": text}
    rng = random.Random(day.date().isoformat())
    caps = {kind: {"file": clip, "seconds": duration(library / clip)}
            for kind, clip in captain_clips(spec["weather"], rng)}
    segs = timeline(caps, narr)
    music = music_dir / MUSIC.get(spec["weather"], "3-Cloudy.mp3")
    made = {}
    for layout in LAYOUTS:
        made[layout] = str(render_layout(layout, {"data": spec}, segs, library, music, work,
                                         out_dir / f"forecast_{day.date().isoformat()}_{layout}.mp4"))
    (out_dir / "script.json").write_text(json.dumps({"writer": writer, "texts": texts, "segments": segs, "spec": spec},
                                                    ensure_ascii=False, indent=1, default=str))
    print(f"Daily video made: {segs[-1]['end']:.0f} s, script by {writer}, weather {spec['weather']}")
    return made


def main() -> int:
    import run_briefings

    a = sys.argv
    get = lambda flag, default=None: a[a.index(flag) + 1] if flag in a else default     # noqa: E731
    db, _url = run_briefings._client()
    build(db, Path(get("--library")), Path(get("--music")), Path(get("--out", "out/daily_video")),
          Path(get("--models", "out/video/voice_model")), edition=get("--edition", "east"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
