"""
🎧 The spoken briefings (20 Nov 2026), in two kinds:

* 🌍 The Morning forecast: the same for everyone, made twice a day: the Asia & Europe edition just after the US
  close, and the Americas edition before the New York morning. The main markets (S&P 500, Nasdaq, the dollar, gold,
  oil, the VIX), the top five coins, the markets' mood, the Tide and the events on the horizon. Shared files under
  general/ in the bucket, with one shared feed; the app and the daily email always give the newest edition, which is
  the one made for the listener's morning wherever they are.
* 🧭 Your Passage Plan, spoken (Pro and Elite): the day's written AI Passage Plan (navigator.py), read aloud, so the
  written and spoken plans always say the same. Kept in the 📓 Logbook with the written plan.

Both are styled like the shipping forecast, read by the free Kokoro voice, over the music for the morning's weather
(briefing_audio.py).

Where they go (storage bucket "briefings", public, sql/2026-11-20_briefings.sql):
* general/<YYYY-MM-DD>-<edition>.mp3 and .txt, general/episodes.json and general/feed.xml;
* <token>/<YYYY-MM-DD>.mp3 and .txt and <token>/feed.xml for each member's spoken plan, under a random token: anyone
  with the link can listen, like any private podcast link, and the member can make a new one.
The app plays both in 📸 Quick Snapshot (and the plan in 📓 Logbook); the daily summary email links both
(listen_links). The worker is run_briefings.py, every 15 minutes. Both describe; neither says what to buy or sell.
The older choices (sections, assets, length) are kept in the settings but no longer used.
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
            "assets": [], "voice": "bf_emma", "email": False, "token": ""}


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


def plan_of(supabase, user_id: str) -> str:
    """The member's plan (user_plans; no row means the beta default, as in the app)."""
    import plans

    try:
        rows = supabase.table("user_plans").select("plan").eq("user_id", user_id).limit(1).execute().data or []
    except Exception:
        rows = []
    return plans.normalise(rows[0].get("plan") if rows else None)


def personal_allowed(plan: str) -> bool:
    """The spoken Passage Plan comes with Pro and Elite."""
    import plans

    return plans.includes(plan, "pro")


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


# ---------------------------------------------------------------------------------------------- the Morning forecast

GENERAL = "general"                         # the shared folder in the bucket
EDITIONS = {
    # made at (UTC hour, minute); named for the morning it serves; its date is that morning's date in `zone`
    "east": {"name": "Asia & Europe edition", "at": (21, 30), "zone": "Asia/Singapore"},
    "west": {"name": "Americas edition", "at": (10, 30), "zone": "America/New_York"},
}
EDITION_WINDOW_HOURS = 8                    # a missed edition is still made this long after its time, then skipped
KEEP_GENERAL = 28                           # two weeks of both editions
GENERAL_SECTIONS = ("markets", "key_markets", "cryptos", "tides", "events")
GENERAL_SECTION_NAMES = {"markets": "the markets' mood", "key_markets": "the main markets",
                         "cryptos": "the top five coins", "tides": "the Tide", "events": "the week's events"}
KEY_STOCKS = {"SPY": "S&P 500 (the SPY fund)", "QQQ": "Nasdaq 100 (the QQQ fund)"}
TOP_COINS = {"bitcoin": "Bitcoin", "ethereum": "Ether", "solana": "Solana", "ripple": "XRP", "binancecoin": "BNB"}
TIDES_MARKETS = ("dollar", "gold", "oil", "fear")         # from the Tides readings


def edition_slot(edition: str, now: datetime) -> tuple[datetime, str]:
    """(when the newest run of this edition was due, at or before now; its episode id "<YYYY-MM-DD>-<edition>",
    dated by the morning it serves)."""
    from zoneinfo import ZoneInfo

    hour, minute = EDITIONS[edition]["at"]
    at = now.astimezone(timezone.utc).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if at > now:
        at -= timedelta(days=1)
    day = at.astimezone(ZoneInfo(EDITIONS[edition]["zone"])) + timedelta(hours=6)    # the morning it serves
    return at, f"{day.date().isoformat()}-{edition}"


def editions_due(made: dict, now: datetime | None = None) -> list[tuple[str, str]]:
    """[(edition, episode id)] to make now: its time has come, within the window, and it isn't made yet."""
    now = now or datetime.now(timezone.utc)
    out = []
    for edition in EDITIONS:
        at, eid = edition_slot(edition, now)
        if eid not in made and now - at <= timedelta(hours=EDITION_WINDOW_HOURS):
            out.append((edition, eid))
    return out


def newest(meta: dict) -> str:
    """The newest episode id in an episodes.json record (by when it was made), or ""."""
    best = max(((str(m.get("made_at") or ""), k) for k, m in (meta or {}).items() if isinstance(m, dict)),
               default=("", ""))
    return best[1]


def _pct(a, b):
    try:
        return round((float(a) / float(b) - 1) * 100, 2) if b else None
    except (TypeError, ValueError):
        return None


def _candle_moves(kind: str, asset_id: str, load=None) -> dict:
    """Last daily close and its 1-day and 7-day moves, from the chart's candles (Yahoo or Binance)."""
    try:
        if load is None:
            import chart_data

            load = chart_data.load_candles
        got = load(kind, asset_id, "1D", "3M")
        c = got["candles"]
        c = c[~c["forming"]] if "forming" in c else c
        closes = [float(x) for x in c["close"].dropna().tolist()]
    except Exception:
        return {}
    if len(closes) < 8:
        return {}
    return {"latest_price": round(closes[-1], 4), "change_1d": _pct(closes[-1], closes[-2]),
            "change_7d": _pct(closes[-1], closes[-8])}


def general_facts(supabase, now: datetime | None = None, load=None) -> dict:
    """The facts for the Morning forecast, the same for everyone: the markets' mood, the main markets, the top five
    coins, the Tide (with a storm warning) and the week's events."""
    now = now or datetime.now(timezone.utc)
    prefs = {"crypto_watchlist": dict(TOP_COINS), "stock_watchlist": dict(KEY_STOCKS), "settings": {}}
    b = {"sections": ["markets", "tides", "watchlist", "events"], "assets": []}
    facts = gather(supabase, "", prefs, b, now)
    items = facts.pop("watchlist", []) or []
    by_name = {i["name"]: i for i in items}
    stocks, coins = [], []
    for kind, names, out in (("equity", KEY_STOCKS, stocks), ("crypto", TOP_COINS, coins)):
        for asset_id, name in names.items():
            item = dict(by_name.get(name) or {"name": name})
            item.pop("kind", None)
            if item.get("change_1d") is None or item.get("latest_price") is None:
                item.update({k: v for k, v in _candle_moves(kind, asset_id, load).items() if v is not None})
            if kind == "equity":
                item.pop("latest_price", None)            # a fund's price means little to a listener; its moves do
            out.append(item)
    tides_markets = []
    try:
        import tides

        snap = tides.latest(supabase) or {}
        for key in TIDES_MARKETS:
            c = (snap.get("currents") or {}).get(key) or {}
            if c.get("status") == "ok":
                tides_markets.append({"name": c.get("name"), "value": c.get("value"), "change_7d": c.get("change_7"),
                                      "change_30d": c.get("change_30"), "direction_30d": c.get("direction"),
                                      "band_against_5_years": c.get("band"),
                                      "unit_of_changes": "points" if c.get("unit") == "pts" else "percent"})
    except Exception as exc:
        print(f"Tides markets skipped in the forecast: {str(exc)[:120]}")
    facts["key_markets"] = stocks + tides_markets
    facts["cryptos"] = coins
    if not facts.get("events"):                           # a quiet week: name the next big release instead
        try:
            import macro_calendar

            nxt = macro_calendar.upcoming(now, days=35)[:1]
            facts["events"] = [{"what": e["name"], "when_utc": e["at"].strftime("%A %d %B, %H:%M"), "why": e["why"],
                                "note": "nothing scheduled this week; this is the next one"} for e in nxt]
        except Exception:
            pass
    return facts


GENERAL_SYSTEM = (
    "You write the script for the Angstrom Signals Morning forecast, a short spoken market briefing that every member "
    "of the app hears, the same for everyone. Angstrom Signals is a market-signals app whose market-conditions feature "
    "is called Tides. Style it like the shipping forecast sailors listen to at dawn: calm, measured, a steady rhythm, "
    "each area of the market given in turn (the tide, the sea state, the winds, storm warnings on the horizon), with a "
    "light nautical flavour that stays perfectly clear to a newcomer. Never let the metaphor hide a fact: say plainly "
    "what moved and by how much. It will be read aloud by a text-to-speech voice, so write for the ear: short "
    "sentences, plain words, numbers rounded and said naturally (\"about 3 percent\", \"sixty-two thousand "
    "dollars\"), no lists, no headings, no symbols, no emoji, no markdown, no URLs. Round every price to a natural "
    "spoken figure (\"about sixty-two thousand dollars\", \"just under one dollar\") and changes to one decimal at "
    "most. Use only the facts given; never "
    "invent prices, news or events, and say nothing about a section that has no facts. Changes are percent unless "
    "marked as points. Describe; never tell the listener to buy, sell or hold, and give no price targets. Trend, "
    "stretch and flow readings run from minus 100 to plus 100 (above zero leans up); sentiment runs from 0 to 100, "
    "with 50 neutral. The overall weather given (sunny, fair, changeable, rough or stormy) sets the tone of the "
    "opening line. Open with \"This is the Angstrom Signals morning forecast, {edition}, for\" the day and date, follow "
    "the sections in the order given with a short spoken link between them, and close with one line saying this is a "
    "summary of the app's readings, not advice, then end with exactly \"Fair winds and following seas.\" Write about {words} "
    "words. Reply with the script text only."
)
GENERAL_MINUTES = 3


def general_prompt(facts: dict, edition: str, day: datetime) -> tuple[str, list[dict]]:
    order = [s for s in GENERAL_SECTIONS if facts.get({"tides": "tide"}.get(s, s))]
    user = {"date": day.strftime("%A %d %B %Y"), "edition": EDITIONS[edition]["name"],
            "overall_weather_from_market_mood": weather(facts),
            "sections_in_order": [GENERAL_SECTION_NAMES[s] for s in order],
            "facts": {GENERAL_SECTION_NAMES[s]: facts.get({"tides": "tide"}.get(s, s)) for s in order}}
    system = GENERAL_SYSTEM.format(edition=EDITIONS[edition]["name"], words=GENERAL_MINUTES * WORDS_PER_MINUTE)
    return system, [{"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)}]


def plain_general(facts: dict, edition: str, day: datetime) -> str:
    """The forecast without AI, from the facts alone."""
    out = [f"This is the Angstrom Signals morning forecast, {EDITIONS[edition]['name']}, for {day.strftime('%A %d %B')}."]
    for m in facts.get("markets") or []:
        if m.get("score_0_to_100") is not None:
            out.append(f"The {m['market']} mood scores {round(m['score_0_to_100'])} out of 100.")
    for a in (facts.get("key_markets") or []) + (facts.get("cryptos") or []):
        move = a.get("change_1d") if a.get("change_1d") is not None else a.get("change_7d")
        if move is not None:
            span = "over the last day" if a.get("change_1d") is not None else "over the week"
            out.append(f"{a['name']} moved {move:+.1f} percent {span}.")
    out += [str(x) for x in (facts.get("tide") or [])[:3]]
    for e in (facts.get("events") or [])[:4]:
        out.append(f"{e['what']}, {e['when_utc']} UTC.")
    out.append("That's the forecast. It summarises the app's readings and is not advice. Fair winds and following seas.")
    return " ".join(out)


def write_general(supabase, facts: dict, edition: str, day: datetime, chat=None) -> tuple[str, str]:
    """(script, who wrote it) for one edition of the Morning forecast."""
    import ai_providers

    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if ai_providers.available(provider):
        system, messages = general_prompt(facts, edition, day)
        try:
            reply = (chat or ai_providers.chat)(provider, system, messages, max_tokens=1500)
            if isinstance(reply, (tuple, list)):
                reply = reply[0]
            text = clean(reply.get("text") if isinstance(reply, dict) else str(reply))
            if len(text.split()) >= 80:
                return text, provider
        except Exception as exc:
            print(f"Forecast script by AI failed: {str(exc)[:160]}")
    return clean(plain_general(facts, edition, day)), "template"


# ---------------------------------------------------------------------------------------------- the spoken Passage Plan

PLAN_HEADINGS = {"conditions": "First, the conditions.", "weather on the route": "The weather on the route.",
                 "your vessels": "Your vessels.", "hazards": "Hazards.", "things to watch": "Things to watch."}


def _say_numbers(text: str) -> str:
    """Signs and symbols a voice reads badly, as words: +2.1% -> plus 2.1 percent, 62/100 -> 62 out of 100."""
    text = re.sub(r"(?<![\w.])\+(?=\d)", "plus ", text)
    text = re.sub(r"(?<![\w.])[-−–](?=\d)", "minus ", text)
    text = re.sub(r"(\d)\s*/\s*100\b", r"\1 out of 100", text)
    text = text.replace("%", " percent").replace("→", " to ").replace("≈", "about ").replace("&", " and ")
    text = re.sub(r"\be\.g\.", "for example", text)
    text = re.sub(r"\bi\.e\.", "that is", text)
    return text


def spoken_plan(body: str, day: datetime) -> str:
    """The written Passage Plan as a script to read aloud: the same words, with a spoken opening and close, each
    heading said as a short line, and signs said as words."""
    out = [f"This is your Angstrom Signals Passage Plan for {day.strftime('%A %d %B')}."]
    for raw in (body or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^[#>*\s]*\**\s*[^\w*]*\s*([A-Za-z][A-Za-z ]+?)\s*\**\s*(?:[-–—:]\s*(.*))?$", line)
        heading = m and m.group(1).strip().lower() in PLAN_HEADINGS and (line.startswith(("*", "#")) or m.group(2))
        if heading:
            out.append(PLAN_HEADINGS[m.group(1).strip().lower()])
            line = m.group(2) or ""
        line = re.sub(r"^[-*•]\s+", "", line)
        line = clean(_say_numbers(line))
        if line:
            out.append(line if line[-1] in ".!?:" else line + ".")
    out.append("That's your Passage Plan. It describes the app's readings and is not advice. Fair winds and following "
               "seas.")
    return " ".join(out)


def tag_line(kind: str, day: datetime) -> str:
    """The closing line, said after a pause with the music still playing: "That was your daily market briefing for
    20 November 2026, brought to you by Angstrom Signals." kind: "general" or "passage"."""
    what = "Passage Plan briefing" if kind == "passage" else "daily market briefing"
    return f"That was your {what} for {day.day} {day.strftime('%B %Y')}, brought to you by Angstrom Signals."


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
    "the app's readings, not advice, then end with exactly \"Fair winds and following seas.\" Write about {words} words. Reply "
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
    out.append("That's the forecast. It summarises the app's readings and is not advice. Fair winds and following seas.")
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


def feed_xml(base: str, token: str, episodes: list[dict], title: str = "Your Angstrom Signals Passage Plan",
             about: str = "Your private daily Passage Plan from Angstrom Signals, read aloud: a summary of the app's "
                          "readings, not advice.", item: str = "Passage Plan") -> str:
    """A podcast feed (RSS 2.0 + iTunes tags): episodes [{day, label, url, bytes, seconds, summary}] newest first."""
    esc = html.escape
    items = "".join(
        f"<item><title>{esc(e.get('title') or (item + ', ' + e['label']))}</title><guid isPermaLink=\"false\">{esc(token[:6] + '-' + e['day'])}</guid>"
        f"<pubDate>{esc(e['pub'])}</pubDate><description>{esc(e.get('summary') or '')}</description>"
        f"<enclosure url=\"{esc(e['url'])}\" length=\"{int(e.get('bytes') or 0)}\" type=\"audio/mpeg\"/>"
        f"<itunes:duration>{int(e.get('seconds') or 0)}</itunes:duration></item>"
        for e in episodes)
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<rss version=\"2.0\" xmlns:itunes=\"http://www.itunes.com/dtds/podcast-1.0.dtd\"><channel>"
            f"<title>{esc(title)}</title><link>https://angstromsignals.com</link>"
            f"<description>{esc(about)}</description><language>en</language><itunes:author>Angstrom Signals</itunes:author>"
            "<itunes:image href=\"https://angstromsignals.com/logo.png\"/><itunes:block>Yes</itunes:block>"
            f"<itunes:explicit>false</itunes:explicit>{items}</channel></rss>")


def stored_json(supabase, path: str) -> dict:
    try:
        got = json.loads(supabase.storage.from_(BUCKET).download(path))
        return got if isinstance(got, dict) else {}
    except Exception:
        return {}


def listen_links(supabase, base: str, settings: dict | None, plan: str, now: datetime | None = None
                 ) -> list[tuple[str, str]]:
    """[(words, url)] for the daily email: the newest Morning forecast, and, for Pro and Elite, today's spoken
    Passage Plan when made in the last 20 hours."""
    now = now or datetime.now(timezone.utc)
    out = []
    general = stored_json(supabase, f"{GENERAL}/episodes.json")
    eid = newest(general)
    if eid and base:
        name = EDITIONS.get(eid[11:], {}).get("name", "")
        out.append((f"🌍 The Morning forecast ({name})" if name else "🌍 The Morning forecast",
                    public_url(base, f"{GENERAL}/{eid}.mp3")))
    b = settings_of(settings)
    if b.get("token") and base and personal_allowed(plan):
        meta = stored_json(supabase, f"{b['token']}/episodes.json")
        day = newest(meta)
        if day and _fresh((meta.get(day) or {}).get("made_at"), 20, now):
            out.append(("🧭 Your Passage Plan", public_url(base, f"{b['token']}/{day}.mp3")))
    return out
