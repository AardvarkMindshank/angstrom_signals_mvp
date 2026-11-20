"""
🎧 Morning briefing (20 Nov 2026): a short spoken summary each morning, 2 to 5 minutes, from the sections and assets a
member picks: the markets' mood, the Tide, their watchlist, what changed overnight, their funnels and the week's
events. Written by AI from the app's own stored readings, read by the same free voice as the training videos, with
the theme music at the start and end (and an optional quiet music bed under the voice).

Where it goes:
* storage bucket "briefings" (public, sql/2026-11-20_briefings.sql), under a random token per member:
  <token>/<YYYY-MM-DD>.mp3, <token>/<YYYY-MM-DD>.txt (the script) and <token>/feed.xml, a private podcast feed;
  anyone with the token's link can listen, like any private podcast link, and the member can make a new one;
* an email with the link, when the member asks for it;
* the 🎧 Morning briefing section in the app, to play it.

The worker (run_briefings.py, every 15 minutes) makes an episode when the member's chosen hour has come in their
time zone and today's isn't made, or as soon as they press "Make today's now". The briefing describes; it never says
what to buy or sell.
"""

from __future__ import annotations

import html
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

BUCKET = "briefings"
SECTIONS = ("markets", "tides", "watchlist", "changes", "funnels", "events")
SECTION_NAMES = {"markets": "🌍 Market mood", "tides": "🌊 The Tide", "watchlist": "⭐ Your watchlist",
                 "changes": "🔔 What changed overnight", "funnels": "🔻 Your funnels", "events": "📅 The week's events"}
LENGTHS = (2, 3, 4, 5)                       # minutes
WORDS_PER_MINUTE = 150
VOICES = {"bf_emma": "Emma (UK)", "bm_george": "George (UK)", "af_heart": "Heart (US)", "am_michael": "Michael (US)"}
MAX_ASSETS = 12
KEEP_EPISODES = 14                           # in the feed and the bucket
DEFAULT_HOUR = 6


def defaults(zone: str = "UTC") -> dict:
    return {"on": False, "hour": DEFAULT_HOUR, "zone": zone or "UTC", "minutes": 3, "sections": list(SECTIONS),
            "assets": [], "voice": "bf_emma", "email": True, "token": ""}


def settings_of(settings: dict | None) -> dict:
    """The member's briefing choices (user_preferences.settings["briefing"]) over the defaults."""
    settings = settings if isinstance(settings, dict) else {}
    zone = settings.get("digest_tz") or "UTC"
    saved = settings.get("briefing") if isinstance(settings.get("briefing"), dict) else {}
    out = {**defaults(zone), **saved}
    out["sections"] = [s for s in out.get("sections") or [] if s in SECTIONS] or list(SECTIONS)
    out["minutes"] = min(LENGTHS, key=lambda m: abs(m - int(out.get("minutes") or 3)))
    out["hour"] = max(0, min(23, int(out.get("hour") if out.get("hour") is not None else DEFAULT_HOUR)))
    out["voice"] = out["voice"] if out.get("voice") in VOICES else "bf_emma"
    return out


def new_token() -> str:
    return secrets.token_urlsafe(18)


def local_now(zone: str, now: datetime | None = None) -> datetime:
    from digest import safe_zone

    return (now or datetime.now(timezone.utc)).astimezone(safe_zone(zone))


def due(settings: dict | None, now: datetime | None = None) -> bool:
    """Today's episode should be made now: asked for with the button, or switched on, the chosen hour has come in the
    member's zone and today's isn't made yet."""
    raw = settings if isinstance(settings, dict) else {}
    b = settings_of(raw)
    state = raw.get("briefing_state") if isinstance(raw.get("briefing_state"), dict) else {}
    if state.get("requested"):
        return True
    if not b["on"]:
        return False
    here = local_now(b["zone"], now)
    return here.hour >= b["hour"] and state.get("made") != here.date().isoformat()


# ---------------------------------------------------------------------------------------------- gathering facts

def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def _report_words(report) -> str:
    if not isinstance(report, dict):
        return ""
    return " ".join(str(report.get("summary") or "").split())[:600]


def _fresh(stamp, hours: float, now: datetime) -> bool:
    try:
        at = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return now - at <= timedelta(hours=hours)


def watch_assets(prefs: dict, chosen: list | None) -> list[tuple[str, str, str]]:
    """(kind, id, name) of the watchlist assets to cover: the chosen ones (keys "Crypto|bitcoin"), else the whole
    watchlist, at most MAX_ASSETS."""
    out = []
    for kind, column in (("Crypto", "crypto_watchlist"), ("Stock", "stock_watchlist")):
        lst = prefs.get(column) or {}
        items = lst.items() if isinstance(lst, dict) else [(x, x) for x in lst]
        for asset_id, name in items:
            out.append((kind, str(asset_id), str(name or asset_id)))
    if chosen:
        wanted = set(chosen)
        out = [a for a in out if f"{a[0]}|{a[1]}" in wanted or f"{a[0]}|{a[1].lower()}" in wanted
               or f"{a[0]}|{a[1].upper()}" in wanted]
    return out[:MAX_ASSETS]


def gather(supabase, user_id: str, prefs: dict, b: dict, now: datetime | None = None) -> dict:
    """The facts for one member's briefing, as plain data (no prose beyond the stored summaries)."""
    now = now or datetime.now(timezone.utc)
    settings = prefs.get("settings") if isinstance(prefs.get("settings"), dict) else {}
    crypto = settings.get("trade_crypto", True) is not False
    stocks = settings.get("trade_equities", True) is not False
    facts: dict = {}
    want = set(b["sections"])

    # The conditions behind the morning's weather (the music and the opening's tone), whatever sections are chosen:
    # the Tide's direction and the sea state.
    try:
        import tides

        snap = tides.latest(supabase) or {}
        tide, sea = snap.get("tide") or {}, snap.get("sea") or {}
        facts["conditions"] = {"tide": tide.get("label") if tide.get("status") == "ok" else None,
                               "sea": sea.get("state") if sea.get("status") == "ok" else None}
    except Exception:
        facts["conditions"] = {}

    if "markets" in want:
        try:
            rows = supabase.table("market_mood").select("market_key, sentiment_score, sentiment_report, "
                                                       "sentiment_updated_at").execute().data or []
        except Exception:
            rows = []
        moods = []
        for row in rows:
            key = row.get("market_key")
            if (key == "crypto" and not crypto) or (key == "stock" and not stocks):
                continue
            if not _fresh(row.get("sentiment_updated_at"), 48, now):
                continue
            moods.append({"market": "crypto" if key == "crypto" else "stock market",
                          "score_0_to_100": _num(row.get("sentiment_score")),
                          "summary": _report_words(row.get("sentiment_report"))})
        facts["markets"] = moods

    if "tides" in want:
        # The Tide's daily note (the tide, the sea state, the currents pulling hardest) with the events on the near
        # horizon from the Tides calendar, and a storm warning when a big release is within a day.
        try:
            import macro_calendar
            import tides

            snap = tides.latest(supabase)
            soon = macro_calendar.upcoming(now, days=7)
            facts["tide"] = [str(x) for x in tides.summary(snap, soon, now)] if snap else []
            storm = macro_calendar.storm_warning(now)
            if storm:
                facts["tide"].append(f"Storm warning: {storm['name']} at {storm['at'].strftime('%A %H:%M')} UTC, "
                                     f"{storm['why']}")
        except Exception as exc:
            print(f"Tide skipped in a briefing: {str(exc)[:120]}")
            facts["tide"] = []

    if "watchlist" in want:
        from market_store import asset_market_key

        assets = watch_assets(prefs, b.get("assets"))
        keys = {asset_market_key(k, i): (k, i, n) for k, i, n in assets}
        rows = {}
        if keys:
            try:
                got = (supabase.table("asset_market").select("asset_key, readings, sentiment_score, sentiment_report, "
                                                            "sentiment_updated_at").in_("asset_key", list(keys))
                       .execute().data or [])
                rows = {r["asset_key"]: r for r in got}
            except Exception:
                rows = {}
        items = []
        for key, (kind, asset_id, name) in keys.items():
            row = rows.get(key) or {}
            fields = ((row.get("readings") or {}).get("fields") or {}) if isinstance(row.get("readings"), dict) else {}
            item = {"name": name, "kind": "crypto" if kind == "Crypto" else "stock"}
            for f in ("latest_price", "change_1d", "change_7d", "rsi"):
                if fields.get(f) is not None:
                    item[f] = fields[f]
            for f, v in fields.items():          # the Trend, Stretch and Flow readings and their words
                if isinstance(v, (int, float, str)) and re.match(r"^(trend|stretch|flow)", str(f)) and v not in ("", None):
                    item[f] = v
            if _fresh(row.get("sentiment_updated_at"), 72, now):
                item["news_sentiment_0_to_100"] = _num(row.get("sentiment_score"))
                words = _report_words(row.get("sentiment_report"))
                if words:
                    item["news_summary"] = words[:300]
            items.append(item)
        facts["watchlist"] = items

    if "changes" in want:
        since = (now - timedelta(hours=24)).isoformat()
        try:
            notes = (supabase.table("user_notifications").select("asset_name, message, alert_type, created_at")
                     .eq("user_id", user_id).gte("created_at", since).neq("alert_type", "funnel")
                     .order("created_at", desc=True).limit(20).execute().data or [])
        except Exception:
            notes = []
        facts["changes"] = [" ".join(str(n.get("message") or "").split())[:200] for n in notes if n.get("message")]

    if "funnels" in want:
        try:
            import funnel_view

            facts["funnels"] = [{"funnel": f["name"], "candidates": f["candidates"], "more": f["more"],
                                 "flagged": f["flagged"], "line": f["line"]}
                                for f in funnel_view.digest_lines(supabase, user_id)]
        except Exception:
            facts["funnels"] = []

    if "events" in want:
        try:
            import macro_calendar

            facts["events"] = [{"what": e["name"], "when_utc": e["at"].strftime("%A %d %B, %H:%M"), "why": e["why"]}
                               for e in macro_calendar.upcoming(now, days=7) if e["at"] >= now - timedelta(hours=6)][:6]
        except Exception:
            facts["events"] = []
    return facts


# ---------------------------------------------------------------------------------------------- the weather

WEATHERS = ("sunny", "fair", "changeable", "rough", "stormy")


def weather(facts: dict) -> str:
    """The morning's weather, sunny to stormy. Starts from the markets' mood (0 to 100, averaged over the markets
    covered): 65 and over sunny, 55 fair, 45 changeable, 35 rough, under 35 stormy. Then the Tide moves it a step:
    going out one worse, coming in one better; and the sea state: calm one better, rough one worse, storm two worse.
    A storm warning (a big release within a day) makes it at least rough. Picks the music
    (video/music/briefing_bed_<weather>.mp3) and sets the opening's tone."""
    scores = [m.get("score_0_to_100") for m in facts.get("markets") or [] if m.get("score_0_to_100") is not None]
    if not scores:
        scores = [a.get("news_sentiment_0_to_100") for a in facts.get("watchlist") or []
                  if a.get("news_sentiment_0_to_100") is not None]
    mood = sum(scores) / len(scores) if scores else 50.0
    level = 0 if mood >= 65 else 1 if mood >= 55 else 2 if mood >= 45 else 3 if mood >= 35 else 4
    cond = facts.get("conditions") or {}
    level += {"in": -1, "out": 1}.get(cond.get("tide"), 0)
    level += {"calm": -1, "rough": 1, "storm": 2}.get(cond.get("sea"), 0)
    level = max(0, min(4, level))
    if any(str(x).startswith("Storm warning") for x in facts.get("tide") or []):
        level = max(level, 3)
    return WEATHERS[level]


# ---------------------------------------------------------------------------------------------- the script

SYSTEM = (
    "You write the script for a short spoken morning briefing for one member of Angstrom Signals, a market-signals "
    "app whose market-conditions feature is called Tides. Style it like the shipping forecast sailors listen to at "
    "dawn: calm, measured, a steady rhythm, each area of the market given in turn (the tide, the sea state, the "
    "winds, storm warnings on the horizon), with a light nautical flavour that stays perfectly clear to a newcomer. "
    "Never let the metaphor hide a fact: say plainly what moved and by how much. It will be read aloud by a "
    "text-to-speech voice, so write for the ear: short sentences, plain words, numbers rounded and said naturally "
    "(\"about 3 percent\", \"sixty-two thousand dollars\"), no lists, no headings, no symbols, no emoji, no markdown, "
    "no URLs. Use only the facts given; never invent prices, news or events, and say nothing about a section that has "
    "no facts. Describe; never tell the listener to buy, sell or hold, and give no price targets. Trend, stretch and "
    "flow readings run from minus 100 to plus 100 (above zero leans up); sentiment runs from 0 to 100, with 50 "
    "neutral. The overall weather given (sunny, fair, changeable, rough or stormy) sets the tone of the "
    "opening line. Open with \"This is the Angstrom Signals morning forecast for\" the day and date, follow the sections "
    "in the order given with a short spoken link between them, and close with one line saying this is a summary of "
    "the app's readings, not advice, then a brief sign-off such as \"Fair winds.\" Write about {words} words. Reply "
    "with the script text only."
)


def prompt(facts: dict, b: dict, day: datetime, name: str = "") -> tuple[str, list[dict]]:
    order = [s for s in b["sections"] if facts.get({"tides": "tide"}.get(s, s))]
    words = b["minutes"] * WORDS_PER_MINUTE
    user = {"listener_first_name": name or None, "date": day.strftime("%A %d %B %Y"),
            "overall_weather_from_market_mood": weather(facts),
            "sections_in_order": order, "facts": {s: facts.get({"tides": "tide"}.get(s, s)) for s in order}}
    return SYSTEM.format(words=words), [{"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)}]


def plain_script(facts: dict, b: dict, day: datetime) -> str:
    """A script without AI, from the facts alone (used when the AI is unavailable)."""
    out = [f"This is the Angstrom Signals morning forecast for {day.strftime('%A %d %B')}."]
    for m in facts.get("markets") or []:
        score = m.get("score_0_to_100")
        out.append(f"The {m['market']} mood scores {round(score)} out of 100." if score is not None else "")
        if m.get("summary"):
            out.append(m["summary"])
    out += [str(x) for x in (facts.get("tide") or [])[:3]]
    for a in facts.get("watchlist") or []:
        bits = [a["name"]]
        if a.get("change_1d") is not None:
            bits.append(f"moved {a['change_1d']:+.1f} percent over the last day")
        if a.get("news_sentiment_0_to_100") is not None:
            bits.append(f"with news sentiment at {round(a['news_sentiment_0_to_100'])}")
        out.append(", ".join(bits) + ".")
    for c in (facts.get("changes") or [])[:6]:
        out.append(c if c.endswith(".") else c + ".")
    for f in facts.get("funnels") or []:
        n = len(f.get("candidates") or []) + int(f.get("more") or 0)
        out.append(f"Your funnel {f['funnel']} has {n} candidate{'s' if n != 1 else ''}.")
    for e in facts.get("events") or []:
        out.append(f"{e['what']}, {e['when_utc']} UTC.")
    out.append("That's the forecast. It summarises the app's readings and is not advice. Fair winds.")
    return " ".join(x for x in out if x)


def clean(text: str) -> str:
    """Strip what a voice would read out badly: markdown marks, emoji, URLs, stray symbols."""
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"[*_#`>|~\[\]]", "", text).replace("\\n", " ")
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def write_script(supabase, facts: dict, b: dict, day: datetime, name: str = "", chat=None) -> tuple[str, str]:
    """(script, who wrote it): the AI chosen for briefings, else the plain script."""
    import ai_providers

    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if ai_providers.available(provider):
        system, messages = prompt(facts, b, day, name)
        try:
            reply = (chat or ai_providers.chat)(provider, system, messages, max_tokens=1500)
            if isinstance(reply, (tuple, list)):          # ai_providers.chat gives (text, finished)
                reply = reply[0]
            text = clean(reply.get("text") if isinstance(reply, dict) else str(reply))
            if len(text.split()) >= 60:
                return text, provider
        except Exception as exc:
            print(f"Briefing script by AI failed: {str(exc)[:160]}")
    return clean(plain_script(facts, b, day)), "template"


# ---------------------------------------------------------------------------------------------- storage and feed

def public_url(supabase_url: str, path: str) -> str:
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{BUCKET}/{path}"


def feed_xml(base: str, token: str, episodes: list[dict], title: str = "Angstrom Signals morning briefing") -> str:
    """A private podcast feed (RSS 2.0 + iTunes tags): episodes [{day, url, bytes, seconds, summary}] newest first."""
    esc = html.escape
    items = "".join(
        f"<item><title>{esc('Briefing, ' + e['label'])}</title><guid isPermaLink=\"false\">{esc(token[:6] + '-' + e['day'])}</guid>"
        f"<pubDate>{esc(e['pub'])}</pubDate><description>{esc(e.get('summary') or '')}</description>"
        f"<enclosure url=\"{esc(e['url'])}\" length=\"{int(e.get('bytes') or 0)}\" type=\"audio/mpeg\"/>"
        f"<itunes:duration>{int(e.get('seconds') or 0)}</itunes:duration></item>"
        for e in episodes)
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<rss version=\"2.0\" xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\"><channel>"
            f"<title>{esc(title)}</title><link>https://angstromsignals.com</link>"
            "<description>Your private morning briefing from Angstrom Signals: a summary of the app's readings, "
            "not advice.</description><language>en</language><itunes:author>Angstrom Signals</itunes:author>"
            "<itunes:image href=\"https://angstromsignals.com/logo.png\"/><itunes:block>Yes</itunes:block>"
            f"<itunes:explicit>false</itunes:explicit>{items}</channel></rss>")
