"""🧭 The Passage Plan, about the member (24 Nov 2026, agreed with Angus).

The Morning Outlook is the market, the same for everyone. The Passage Plan is this member's day: their watchlist
(each asset's last move, its Trend, Stretch and Flow and how they changed since the day before, its news mood and
top story, and whether the Tide is a headwind or tailwind for it), their funnels, the alerts that fired for them
overnight, and only the events that touch what they hold. The Tide gets one line, as context; the Outlook covers it.

The facts here are the app's own (the chart's candles for the moves, the stored readings and their daily record,
the asset sentiment cards, the account's alerts and funnels), so the plan says what the app shows. The AI writes
two versions from the same facts: one to read (short headings, the readings behind each point) and one to hear
(plain sentences, no brackets or symbols).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import briefing

SPOKEN_WORDS = 380                      # about 2.5 minutes
MAX_ASSETS = briefing.MAX_ASSETS


def _clusters(readings: dict | None) -> dict:
    signals = (((readings or {}).get("fields") or {}).get("signals") or {}) if isinstance(readings, dict) else {}
    clusters = signals.get("clusters") or {}
    out = {}
    for name in ("trend", "stretch", "flow"):
        c = clusters.get(name) or {}
        if c.get("percent") is not None:
            out[name] = round(float(c["percent"]))
    regime = (signals.get("context") or {}).get("regime")
    if isinstance(regime, dict) and regime.get("label"):
        out["regime"] = regime["label"]
    return out


def _top_story(report: dict | None) -> dict | None:
    """The asset's headline that reads strongest either way, with its source."""
    rows = [h for h in ((report or {}).get("headlines") or []) if isinstance(h, dict) and h.get("score") is not None]
    if not rows:
        return None
    h = max(rows, key=lambda r: abs(float(r["score"]) - 50))
    return {"title": h.get("title"), "source": h.get("source"),
            "mood": (briefing.news_mood(h["score"]) or {}).get("news_mood")}


def _tide(snap: dict | None) -> dict:
    """One line of context: the Tide, the sea, and the wind for each market."""
    import tides

    if not snap or (snap.get("tide") or {}).get("status") != "ok":
        return {}
    t, sea = snap["tide"], snap.get("sea") or {}
    out = {"tide": tides.TIDE_WORDS[t["label"]][0], "tide_plain": tides.TIDE_WORDS[t["label"]][1],
           "held_trading_days": t.get("held_days")}
    if sea.get("status") == "ok":
        out["sea"] = f"{sea['state']} ({sea['plain']})"
    out["wind"] = {m: {"wind": w.get("wind"), "led_by": [tides.SPEC[k]["name"] for k in w.get("drivers") or []]}
                   for m, w in (snap.get("winds") or {}).items()}
    return out


def facts(supabase, user_id: str, row: dict, now: datetime | None = None, load=None) -> dict:
    """Everything the plan may say, as plain data. row: the member's user_preferences row (watchlists, settings)."""
    from market_store import asset_market_key
    import tides

    now = now or datetime.now(timezone.utc)
    snap = tides.latest(supabase)
    tide = _tide(snap)
    assets = briefing.watch_assets(row, None)[:MAX_ASSETS]
    keys = {asset_market_key(k, i): (k, i, n) for k, i, n in assets}
    stored, daily = {}, {}
    if keys:
        try:
            got = (supabase.table("asset_market").select("asset_key, readings, sentiment_score, sentiment_report, "
                                                        "sentiment_updated_at").in_("asset_key", list(keys))
                   .execute().data or [])
            stored = {r["asset_key"]: r for r in got}
        except Exception:
            stored = {}
        try:
            since = (now - timedelta(days=6)).date().isoformat()
            got = (supabase.table("readings_daily").select("asset_key, day, trend, stretch, flow")
                   .in_("asset_key", list(keys)).gte("day", since).order("day", desc=True).execute().data or [])
            for r in got:
                daily.setdefault(r["asset_key"], []).append(r)
        except Exception:
            daily = {}
    items = []
    for key, (kind, asset_id, name) in keys.items():
        market = "crypto" if kind == "Crypto" else "equity"
        moves = briefing._candle_moves(market, asset_id, load, now)
        item = {"name": name, "market": "crypto" if market == "crypto" else "stocks"}
        if moves:
            item["one_day_change_covers"] = briefing.one_day_covers(market, moves.get("last_day"), now)
            item.update({k: moves[k] for k in ("latest_price", "change_1d", "change_7d") if moves.get(k) is not None})
        r = stored.get(key) or {}
        now_read = _clusters(r.get("readings"))
        if now_read:
            item["readings_now"] = now_read                       # Trend, Stretch, Flow: -100..+100
        # The readings' day before the current one, from the daily record (newest first).
        as_of = str(((((r.get("readings") or {}).get("fields") or {}).get("signals") or {}).get("as_of")) or "")
        days = daily.get(key) or []
        before = next((d for d in days if as_of and str(d.get("day") or "") < as_of), None)
        if before and now_read:
            changed = {k: now_read[k] - round(float(before[k])) for k in ("trend", "stretch", "flow")
                       if before.get(k) is not None and k in now_read}
            if any(changed.values()):
                item["readings_change_since"] = {"day": before["day"], **changed}
        if briefing._fresh(r.get("sentiment_updated_at"), 72, now) and r.get("sentiment_score") is not None:
            mood = briefing.news_mood(r["sentiment_score"]) or {}
            item["news_mood"] = mood.get("news_mood")
            item["news_mood_words"] = mood.get("news_mood_words")
            story = _top_story(r.get("sentiment_report"))
            if story:
                item["top_story"] = story
        wind = (tide.get("wind") or {}).get(market)
        if wind:
            item["tide_for_its_market"] = wind["wind"]
        items.append(item)
    # Biggest day's move first, so the plan leads with what changed most.
    items.sort(key=lambda a: -abs(a.get("change_1d") or 0))

    out = {"tide_context": tide, "watchlist": items}
    since = (now - timedelta(hours=24)).isoformat()
    try:
        notes = (supabase.table("user_notifications").select("asset_name, message, alert_type, created_at")
                 .eq("user_id", user_id).gte("created_at", since).neq("alert_type", "funnel")
                 .order("created_at", desc=True).limit(20).execute().data or [])
    except Exception:
        notes = []
    out["alerts_last_24h"] = [" ".join(str(n.get("message") or "").split())[:200] for n in notes if n.get("message")]
    try:
        import funnel_view

        out["funnels"] = [{"funnel": f["name"], "candidates": f["candidates"], "more": f["more"],
                           "flagged": f["flagged"], "line": f["line"]} for f in funnel_view.digest_lines(supabase,
                                                                                                         user_id)]
    except Exception:
        out["funnels"] = []
    try:
        import macro_calendar

        out["events_next_7_days"] = [{"what": e["name"], "when_utc": e["at"].strftime("%A %d %B, %H:%M"),
                                      "why": e["why"]} for e in macro_calendar.upcoming(now, days=7)
                                     if e["at"] >= now - timedelta(hours=6)][:6]
    except Exception:
        out["events_next_7_days"] = []
    return out


SYSTEM = (
    "You write a MarketNavi Passage Plan: one member's morning plan for their own trading day, from the facts given "
    "about their watchlist, funnels and alerts. It is NOT a market report: a separate Morning Outlook covers the "
    "markets, the Tide and the calendar for everyone, so give the Tide one sentence only, as context, and spend every "
    "other sentence on this member's assets, funnels and alerts. Lead with what changed most. Trend, Stretch and Flow "
    "run from minus 100 to plus 100 (above zero leans up; Stretch high means stretched up, low stretched down); say "
    "how each moved since the day given when it moved by 10 or more. A news mood runs from minus 100 to plus 100. "
    "Each 1-day change covers exactly its one_day_change_covers period: name it (\"on Monday\", \"over the last 24 "
    "hours\"), never call it today's. Mention an event only if it touches this member's markets, and say which of "
    "their assets. Use only the facts given and only their numbers, rounded (one decimal place for percentages); "
    "never invent prices, news or events; say nothing about a part with no facts. Describe; never say buy, sell, "
    "enter or exit, and give no price targets. Anything about what may happen next is an expectation: label it "
    "\"Expectation:\" and say what would show it right or wrong.\n"
    "Reply with JSON only: {\"written\": the plan to read, in markdown, with exactly these short headings in this "
    "order, each as a bold line: **🧭 Your morning in brief** (two or three sentences: the Tide in one, then the "
    "member's biggest changes), **⛵ Your watchlist** (one short bullet per asset, biggest change first, each with "
    "the readings behind it in brackets), **🔻 Your funnels** (only if there are any), **🔔 Overnight alerts** (only "
    "if there are any), **📅 Events that touch your assets** (only if any do), **🔭 What to watch** (two or three "
    "expectations about this member's assets); under 450 words. \"spoken\": the same plan for the ear, about "
    "{words} words: plain spoken sentences that flow, no headings, no brackets, no symbols or emoji, numbers as "
    "digits; open with \"Good morning{name}.\" and do not close (a fixed closing line is added)}."
)


def prompt(f: dict, day: datetime, name: str = "") -> tuple[str, list[dict]]:
    user = {"date": day.strftime("%A %d %B %Y"), "facts": f}
    system = SYSTEM.replace("{words}", str(SPOKEN_WORDS)).replace("{name}", f", {name}" if name else "")
    return system, [{"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)}]


def write(supabase, f: dict, day: datetime, name: str = "", chat=None) -> tuple[dict | None, str]:
    """({"written", "spoken"}, who wrote it), or (None, reason) when the AI didn't give both."""
    import ai_providers

    provider = ai_providers.pick("briefing", ai_providers.app_choice(supabase, "briefing"))
    if not ai_providers.available(provider):
        return None, "no AI key"
    system, messages = prompt(f, day, name)
    try:
        reply = (chat or ai_providers.chat)(provider, system, messages, max_tokens=3000)
        if isinstance(reply, (tuple, list)):
            reply = reply[0]
        text = reply.get("text") if isinstance(reply, dict) else str(reply)
        got = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    except Exception as exc:
        return None, f"AI failed: {str(exc)[:120]}"
    written, spoken = str(got.get("written") or "").strip(), str(got.get("spoken") or "").strip()
    if not written or len(spoken.split()) < 60:
        return None, "AI reply incomplete"
    spoken = briefing.clean(spoken) + (" That's your Passage Plan. It describes the app's readings for your "
                                       "assets and is not advice. Fair winds and following seas.")
    return {"written": written, "spoken": spoken}, provider
