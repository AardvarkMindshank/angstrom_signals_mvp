"""Trade Log weekly review (spec v0.5, phase 4): a short AI review of the member's past week, written when they first
open it, from facts worked out here. It describes; it never advises.

How it stays honest:
- The AI sees only facts computed from the member's own trades (numbered T1, T2, ...), their stats and the readings
  saved with each trade. It must cite the trades each statement rests on, and every cited trade must exist.
- Anything resting on fewer than MIN_TRADES trades is a "possible pattern", with its count.
- A guard rejects advice-like wording (buy, sell, targets, predictions, "you should"). One retry; if the second answer
  still fails, the member gets a plain summary built from the facts instead, so nothing unchecked is ever shown.
- Readings are described as what happened together, never as a cause.
- Only numbers and asset names go to the AI provider: no names, emails or keys.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

import tradelog

MAX_TRADES_SHOWN = 40
FORBIDDEN = [
    r"\byou should\b", r"\byou must\b", r"\bi recommend\b", r"\brecommend(ed|ation)?\b", r"\bconsider (buying|selling)\b",
    r"\b(buy|sell|short|long) (now|more|it|this)\b", r"\bgo (long|short)\b", r"\bprice target\b", r"\btarget price\b",
    r"\bwill (rise|fall|go up|go down|rally|crash|bounce)\b", r"\bis (likely|set|going) to (rise|fall|rally|drop)\b",
    r"\bentry point\b", r"\bset (a|your) stop\b", r"\btake profit at\b", r"\bguarantee", r"\bcaused\b",
    r"\bbecause the (regime|trend|score|readings?)\b",
]
SYSTEM = (
    "You write a short weekly review of one trader's own closed trades for MarketNavi, a descriptive market-readings "
    "app. You are a mirror, not a tipster.\n"
    "Rules, all mandatory:\n"
    "1. Use ONLY the facts in the JSON you are given. Never invent numbers, trades, dates or readings.\n"
    "2. Never give advice: no buy, sell, hold, long or short suggestions, no price targets, no predictions, no "
    "'you should'. Never say a trade was right or wrong.\n"
    "3. Describe what happened together; never say a reading caused a result.\n"
    "4. If a pattern rests on fewer than 10 trades, call it a 'possible pattern' and give the count.\n"
    "5. Cite the trades each statement rests on with their ids, like (T3, T5).\n"
    "6. Plain, friendly English, short sentences. Each part at most 3 sentences.\n"
    "Answer with JSON only: {\"happened\": str, \"pattern\": str, \"question\": str, \"cited\": [trade ids]}. "
    "'happened' summarises the week. 'pattern' names one thing worth noticing, from this week compared with the last "
    "90 days. 'question' is one open question for the trader to think about (not advice)."
)


def week_of(today: date) -> tuple[date, date]:
    """The last finished Monday-to-Sunday week before `today`."""
    monday = today - timedelta(days=today.weekday())
    return monday - timedelta(days=7), monday - timedelta(days=1)


def _local_day(value, zone) -> date | None:
    t = tradelog._when(value)
    return t.astimezone(zone).date() if t else None


def facts(trips: list[dict], snaps: dict, week: tuple[date, date], zone, scope: str = "all") -> dict:
    """Everything the review may use, as plain numbers. Copied trades are left out."""
    own = [t for t in trips if not t.get("copied")]
    if scope.startswith("class:"):
        own = [t for t in own if t.get("asset_class") == scope[6:]]
    elif scope.startswith("platform:"):
        own = [t for t in own if t.get("platform") == scope[9:]]
    start, end = week
    in_week = [t for t in own if start <= (_local_day(t["closed_at"], zone) or date.min) <= end]
    since = start - timedelta(days=90)
    before = [t for t in own if since <= (_local_day(t["closed_at"], zone) or date.min) < start]
    listed = sorted(in_week, key=lambda t: t["closed_at"])[:MAX_TRADES_SHOWN]

    def reading(t, moment, key):
        return (snaps.get((t["id"], moment)) or {}).get(key)

    def fear(t):
        f = (snaps.get((t["id"], "entry")) or {}).get("fear") or {}
        return f.get("value")

    trades = []
    for i, t in enumerate(listed, 1):
        a, b = tradelog._when(t["opened_at"]), tradelog._when(t["closed_at"])
        trades.append({"id": f"T{i}", "asset": t.get("name") or t.get("symbol"), "class": t.get("asset_class"),
                       "direction": t.get("direction"), "result_usd": t.get("net_result_usd"),
                       "result_pct": t.get("result_pct"), "held_days": round((b - a).total_seconds() / 86400, 1),
                       "invested_usd": t.get("invested_usd"), "leverage": t.get("leverage"),
                       "regime_at_entry": reading(t, "entry", "regime"), "trend_at_entry": reading(t, "entry", "trend"),
                       "stretch_at_exit": reading(t, "exit", "stretch"), "fear_at_entry": fear(t)})
    tagged = [{**t, "regime": reading(t, "entry", "regime") or "unknown"} for t in before + in_week]
    return {"week": f"{start.isoformat()} to {end.isoformat()}", "scope": scope, "trades": trades,
            "week_stats": tradelog.stats(in_week, True), "last_90_days_stats": tradelog.stats(before, True),
            "by_regime_at_entry_incl_this_week": tradelog.stats_by(tagged, "regime", True),
            "patterns_incl_this_week": tradelog.patterns(before + in_week, True),
            "min_trades_for_a_pattern": tradelog.MIN_TRADES}


def problems(review: dict, fact: dict) -> list[str]:
    """Why a review can't be shown (empty when it is fine)."""
    out = []
    if not isinstance(review, dict):
        return ["not an object"]
    for part in ("happened", "pattern", "question"):
        if not isinstance(review.get(part), str) or not review[part].strip():
            out.append(f"missing {part}")
    text = " ".join(str(review.get(p) or "") for p in ("happened", "pattern", "question")).lower()
    for rule in FORBIDDEN:
        if re.search(rule, text):
            out.append(f"advice-like wording ({rule})")
    known = {t["id"] for t in fact["trades"]}
    cited = set(re.findall(r"\bT\d+\b", " ".join(str(review.get(p) or "") for p in ("happened", "pattern"))))
    cited |= {str(c) for c in review.get("cited") or []}
    if fact["trades"] and not cited:
        out.append("no trades cited")
    if cited - known:
        out.append(f"unknown trades cited: {sorted(cited - known)}")
    return out


def plain_review(fact: dict) -> dict:
    """The fallback when the AI's answer fails the checks (or no AI is available): facts only, no interpretation."""
    w = fact["week_stats"]
    if not w["trades"]:
        happened = "No trades closed this week."
    else:
        happened = (f"{w['trades']} trades closed this week: {w['wins']} wins and {w['losses']} losses, "
                    f"net {w['net']:+,.2f} USD.")
    pattern = "Not enough trades this week to call anything a pattern."
    return {"happened": happened, "pattern": pattern,
            "question": "Looking back at this week's trades, which one would you take again the same way?",
            "cited": [t["id"] for t in fact["trades"]], "plain": True}


def _parse(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def _translate(review: dict, language: str, chat) -> dict | None:
    """The checked English review in the member's language, same meaning, nothing added."""
    try:
        out = _parse(chat("Translate the JSON values into " + language + ". Keep the meaning exactly, add nothing, "
                          "keep trade ids like (T3) as they are. Answer with the same JSON keys only.",
                          [{"role": "user", "content": json.dumps({k: review[k] for k in
                                                                   ("happened", "pattern", "question")})}]))
    except Exception:
        return None
    if not isinstance(out, dict) or not all(isinstance(out.get(k), str) for k in ("happened", "pattern", "question")):
        return None
    return {**review, **{k: out[k] for k in ("happened", "pattern", "question")}}


def write(fact: dict, provider: str, chat=None, language: str = "English") -> dict:
    """The review for these facts: the AI's, checked, with one retry; otherwise the plain one. Written in the
    member's language (the advice check reads English, so other languages are checked on the AI's English draft)."""
    if not fact["trades"]:
        return plain_review(fact)
    if chat is None:
        import ai_providers

        chat = lambda system, msgs: ai_providers.chat(provider, system, msgs, max_tokens=900, json_only=True)[0]  # noqa: E731
    messages = [{"role": "user", "content": "Facts:\n" + json.dumps(fact, default=str)}]
    translated = language != "English"
    for _attempt in range(2):
        try:
            review = _parse(chat(SYSTEM, messages))
        except Exception:
            break
        issues = problems(review, fact)
        if not issues:
            if translated:
                review = _translate(review, language, chat) or review
            return {**review, "plain": False}
        messages = messages + [{"role": "assistant", "content": json.dumps(review) if review else ""},
                               {"role": "user", "content": "That answer broke these rules: " + "; ".join(issues)
                                + ". Write it again following every rule, JSON only."}]
    return plain_review(fact)
