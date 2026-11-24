"""
Market sentiment from recent headlines for the asset open on the chart.

Headlines come from Google News. Grok turns them into a 0–100 score.
The score is not blended into the technical score.
"""

from __future__ import annotations

import copy
import html
import json
import os
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

import news_filter

# grok-4.3 can turn reasoning off, so a short headline score returns quickly.
# grok-4.5 is only used if that model name is rejected.
_MODELS = (
    {"model": "grok-4.3", "reasoning_effort": "none"},
    {"model": "grok-4.3"},
    {"model": "grok-4.5"},
)
_CHAT_URL = "https://api.x.ai/v1/chat/completions"
# One shared clock for the page and the background worker.
# Change these two numbers to change how often saved results are replaced.
SENTIMENT_REFRESH_SECONDS = 12 * 60 * 60
TECHNICAL_REFRESH_SECONDS = 5 * 60
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}
_BUSY_UNTIL: dict[str, float] = {}
_SCORE_CACHE: dict[str, tuple[float, dict]] = {}
_KEY_REJECTED = False
_PROVIDER: str | None = None            # the admin's choice (ai_providers.py, app_settings); None = Grok
# 🌐 The languages accounts have chosen, besides English (15 Nov 2026). The worker sets them before it scores; the same
# AI call then also writes the summary, the two sides, the drivers and each headline's note in those languages, kept
# in the report under "tr". Only languages someone uses are asked for; a new one fills in at each report's next refresh.
_LANGUAGES: tuple[str, ...] = ()


def set_provider(provider: str | None) -> None:
    """Which AI scores headlines from now on (the page and the worker read the admin's choice and set it)."""
    global _PROVIDER
    _PROVIDER = provider or None


def set_languages(codes) -> None:
    """The languages to write the AI text in as well as English (the worker: every account's chosen language)."""
    global _LANGUAGES
    _LANGUAGES = tuple(sorted({str(c) for c in (codes or []) if c and str(c) != "en"}))


def languages() -> tuple[str, ...]:
    return _LANGUAGES


def _language_names(codes) -> str:
    try:
        import i18n

        return ", ".join(f"{c} ({i18n.BY_CODE[c]['english']})" if c in i18n.BY_CODE else c for c in codes)
    except Exception:
        return ", ".join(codes)


def _with_translations(prompt: str, langs, notes_only: bool = False) -> str:
    """The prompt, asking as well for the English text in each of `langs` (none: the prompt as it was)."""
    if not langs:
        return prompt
    shape = '{"notes":{"1":"..."}}' if notes_only else (
        '{"summary":"...","positive":"...","negative":"...","drivers":["..."],"notes":{"1":"..."}}')
    return (
        prompt
        + "\nAlso add a key \"tr\" to the same JSON object, with one entry per language code listed below, each in "
        f"this shape: {shape}. Each is a faithful translation of the English fields above into that language "
        "(notes keyed by the same index numbers). Keep asset names, tickers and numbers unchanged. "
        "Write the English fields first, then tr. Languages: " + _language_names(langs) + "."
    )


def _read_translations(raw, langs) -> dict:
    """{code: {summary, positive, negative, drivers, notes: {index: text}}} for the asked languages, cleaned."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for code in langs or ():
        entry = raw.get(code)
        if not isinstance(entry, dict):
            continue
        clean = {}
        for name in ("summary", "positive", "negative"):
            text = " ".join(str(entry.get(name) or "").split())
            if text:
                clean[name] = text
        drivers = entry.get("drivers")
        if isinstance(drivers, str):
            drivers = [drivers]
        if isinstance(drivers, list):
            kept = [" ".join(str(d).split())[:160] for d in drivers if str(d).strip()][:3]
            if kept:
                clean["drivers"] = kept
        notes = {}
        raw_notes = entry.get("notes")
        if isinstance(raw_notes, list):
            raw_notes = {str(i): v for i, v in enumerate(raw_notes, start=1)}
        if isinstance(raw_notes, dict):
            for key, value in raw_notes.items():
                try:
                    index = int(str(key).strip())
                except ValueError:
                    continue
                text = _short_note(value)
                if text:
                    notes[index] = text
        if notes:
            clean["notes"] = notes
        if clean:
            out[code] = clean
    return out


def has_languages(report, langs=None) -> bool:
    """True when a stored report already holds every language asked for (so it can be reused as it is)."""
    langs = _LANGUAGES if langs is None else langs
    have = (report or {}).get("tr") if isinstance(report, dict) else None
    return all(isinstance(have, dict) and have.get(code) for code in langs)


def localised(report, code: str | None):
    """A copy of a report with its AI text in `code` where it was translated; the English otherwise."""
    if not isinstance(report, dict) or not code or code == "en":
        return report
    tr = (report.get("tr") or {}).get(code) if isinstance(report.get("tr"), dict) else None

    def note_of(row):
        words = (row.get("tr") or {}).get(code) if isinstance(row, dict) and isinstance(row.get("tr"), dict) else None
        return {**row, "note": words} if words else row

    out = dict(report)
    if isinstance(tr, dict):
        for name in ("summary", "positive", "negative", "drivers"):
            if tr.get(name):
                out[name] = tr[name]
    out["headlines"] = [note_of(row) for row in report.get("headlines") or []]
    lead = report.get("lead")
    if isinstance(lead, dict) and isinstance(lead.get("tr"), dict) and lead["tr"].get(code):
        out["lead"] = {**lead, "why": lead["tr"][code]}
    if report.get("gauges"):
        out["gauges"] = [{**g, "items": [note_of(i) for i in (g.get("items") or [])]} if isinstance(g, dict) else g
                         for g in report.get("gauges") or []]
    return out


def scoring_provider() -> str:
    """The AI that will score: the admin's choice when its key is there, else Grok."""
    import ai_providers

    if _PROVIDER and _PROVIDER != "grok" and ai_providers.available(_PROVIDER):
        return _PROVIDER
    return "grok"


def _api_key() -> str:
    """The xAI key, without a wrapping quote or a pasted Bearer prefix."""
    key = (os.getenv("XAI_API_KEY") or "").strip().strip('"').strip("'")
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def sentiment_query(kind: str, label: str, ticker: str | None) -> str:
    """Search text for one asset: '<name> [TICKER] cryptocurrency|stock'. The ticker is always included
    (unless the name is the ticker), so a headline that only says "ETH" is found too. The extra word keeps
    the name from matching the wrong thing."""
    name = " ".join((label or "").replace("(", " ").replace(")", " ").split())
    symbol = (ticker or "").strip().upper()
    parts = [name]
    if symbol and symbol not in name.split():
        parts.append(symbol)
    parts.append("cryptocurrency" if kind == "Crypto" else "stock")
    return " ".join(part for part in parts if part)


def _published_timestamp(value) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    try:
        return when.timestamp()
    except (OSError, OverflowError, ValueError):
        return None


def newest_first(headlines: list[dict]) -> list[dict]:
    """Dated headlines first, newest at the top. A missing date stays at the bottom."""
    def key(item: dict):
        stamp = _published_timestamp(item.get("published"))
        if stamp is None:
            return (1, 0.0)
        return (0, -stamp)

    return sorted(headlines, key=key)


# Whole-market searches. The wording can change later without a new table.
# 24 Nov 2026: one "outlook" search kept the 8 newest articles of a week and missed the day's story (Jensen Huang back
# at Nvidia, the Nasdaq up 7%). Each market now runs several news searches and keeps the stories most widely reported
# in the last 24 hours; "query" stays the stored name of the search. "moves" are the markets whose latest move the
# story of the day is checked against.
MACRO_MOODS = (
    {
        "key": "crypto",
        "label": "Crypto market",
        "query": "crypto market outlook regulation ETF liquidity",
        "searches": ("crypto market today", "Bitcoin news", "crypto news", "crypto ETF"),
        "moves": (("crypto", "bitcoin", "Bitcoin"), ("crypto", "ethereum", "Ether")),
    },
    {
        "key": "stock",
        "label": "Stock market",
        "query": "stock market outlook inflation interest rates earnings",
        "searches": ("stock market today", "Wall Street stocks", "Nasdaq", "S&P 500"),
        "moves": (("equity", "SPY", "S&P 500"), ("equity", "QQQ", "Nasdaq 100")),
    },
)
MOOD_SPECS = {spec["key"]: spec for spec in MACRO_MOODS}

# Pages that only list a price or a routine event are not news ("ETH price at 6 PM CST", "Current price of Bitcoin
# for November 23", "Rings the Nasdaq opening bell"). "A $1 trillion price on Jensen Huang" is news, so "price on" stays.
NOT_NEWS = re.compile(r"\bprice (at|today|for|now)\b|current price of|live price|price chart|to usd\b|"
                      r"\bprice (index|quote)\b|rings? the .*(opening|closing) bell", re.I)
LEAD_HOURS = 24


def rank_market_headlines(rows: list[dict], now: float) -> list[dict]:
    """Most important first: the last 24 hours before older, then the most widely reported, then the newest."""
    recent = now - LEAD_HOURS * 3600

    def key(row):
        try:
            stamp = datetime.fromisoformat(str(row.get("published_at"))).timestamp()
        except ValueError:
            stamp = 0.0
        return (stamp >= recent, int(row.get("also_reported") or 0), stamp)

    return sorted(rows, key=key, reverse=True)


def gather_market_news(searches, limit: int = 8, now: float | None = None) -> tuple[list[dict], dict]:
    """(the most important whole-market headlines, what was filtered) from several news searches."""
    now = time.time() if now is None else now
    raw, failures = [], 0
    for search in searches:
        try:
            raw += _fetch_raw(search)
        except Exception:
            failures += 1
    if failures == len(searches):
        raise RuntimeError("no headline search succeeded")
    kept_raw = [item for item in raw if not NOT_NEWS.search(str(item.get("title") or ""))]
    rows, stats = news_filter.clean_headlines(kept_raw, now, {}, 400)
    rows = rank_market_headlines(rows, now)[:limit]
    stats.update(news_filter.coverage(rows))
    stats["not_news"] = len(raw) - len(kept_raw)
    return rows, stats


def latest_moves(spec: dict) -> list[dict]:
    """The latest finished 1-day move of each market the story of the day is checked against (the chart's candles,
    as the daily briefing tells them)."""
    import briefing

    out = []
    for kind, asset_id, name in spec.get("moves") or ():
        try:
            moves = briefing._candle_moves(kind, asset_id)
        except Exception:
            moves = {}
        if moves.get("change_1d") is not None:
            out.append({"name": name, "change_1d": moves["change_1d"], "day": moves.get("last_day")})
    return out


def lead_story(spec: dict, headlines: list[dict], moves: list[dict] | None = None, chat=None) -> dict | None:
    """The story of the day: the headline that best explains the market's latest moves, with one sentence on why.
    {"quiet": True, ...} when no headline explains them (a quiet day is said plainly, not dressed up). None when the
    AI didn't answer."""
    if not headlines:
        return None
    moves = latest_moves(spec) if moves is None else moves
    langs = languages()
    lines = "\n".join(f"{i}. {row.get('title')} ({row.get('source') or 'unknown'}, carried by "
                      f"{1 + int(row.get('also_reported') or 0)} outlets)" for i, row in enumerate(headlines, 1))
    moved = "; ".join(f"{m['name']} {m['change_1d']:+.2f}% on {m['day']}" for m in moves) or "not available"
    tr = (', "tr": {' + ", ".join(f'"{code}": "the why sentence in {code}"' for code in langs) + "}"
          if langs else "")
    ask = (f"These are the most widely reported {spec['label'].lower()} headlines, and the market's latest moves "
           f"({moved}). Name the single story that best explains what is moving this market now. On a flat day, "
           "that is the most widely reported story weighing on or lifting the market (for example, money leaving "
           "funds while prices hold). "
           'Reply with JSON only: {"index": n, "why": "one plain, complete sentence", "explains_moves": true or false'
           + tr + "}. Set explains_moves to false only when no headline is about what is driving this market; then "
           "say so in why, in a complete sentence. This is research context, not advice.\n" + lines)
    try:
        if chat is None:
            import ai_providers

            text, _done = ai_providers.chat(scoring_provider(), "You pick the lead market story from headlines. "
                                            "Facts only.", [{"role": "user", "content": ask}], max_tokens=900,
                                            json_only=True, timeout=60)
        else:
            text = chat(ask)
        start, end = text.find("{"), text.rfind("}")
        got = json.loads(text[start:end + 1])
        index = int(got.get("index") or 0)
        why = " ".join(str(got.get("why") or "").split())
    except Exception:
        return None
    lead = {"why": why, "moves": moves, "explains_moves": bool(got.get("explains_moves"))}
    if isinstance(got.get("tr"), dict):
        lead["tr"] = {str(k): str(v) for k, v in got["tr"].items() if v and str(k) in langs}
    if not lead["explains_moves"] or not 1 <= index <= len(headlines):
        return {**lead, "quiet": True}
    row = headlines[index - 1]
    return {**lead, "id": row.get("id"), "title": row.get("title"), "source": row.get("source"),
            "link": row.get("link")}
_MOOD_SKIP = news_filter.SKIP_WORDS


def _fetch_raw(query: str) -> list[dict]:
    """Every headline Google News returns for the search over the last 7 days (up to about 100)."""
    response = requests.get(
        "https://news.google.com/rss/search",
        params={
            "q": f"{query} when:7d",
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        },
        headers=_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)
    headlines = []
    for item in root.iter("item"):
        title = html.unescape((item.findtext("title") or "")).strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith("http"):
            continue
        source = (item.findtext("source") or "").strip()
        if not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
            title = title.strip()
            source = source.strip()
        elif source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        headlines.append({
            "title": title,
            "source": source,
            "published": (item.findtext("pubDate") or "").strip(),
            "link": link,
        })
    return headlines


def asset_searches(query: str) -> list[str]:
    """An asset is searched twice, by name and by ticker ('Ethereum cryptocurrency', 'ETH cryptocurrency').
    The two result lists are merged; the same article found by both searches counts once."""
    words = str(query or "").split()
    terms = news_filter.asset_terms(query)
    ticker = terms.get("ticker") or ""
    if not terms or not ticker or len(words) < 3:
        return [query]
    kind_word = words[-1]
    name = " ".join(words[:-2]) if words[-2] == ticker else " ".join(words[:-1])
    if not name or name.upper() == ticker:
        return [query]
    return [f"{name} {kind_word}", f"{ticker} {kind_word}"]


def gather_headlines(query: str, market: bool = False, limit: int = 8) -> tuple[list[dict], dict]:
    """(cleaned headlines, what was filtered). See news_filter: junk, stale, off-topic (asset searches),
    duplicate and same-event reports and publisher repeats are removed before anything is scored."""
    if market:
        return news_filter.clean_headlines(_fetch_raw(query), time.time(), {}, limit)
    raw, failures = [], 0
    searches = asset_searches(query)
    for search in searches:
        try:
            raw += _fetch_raw(search)
        except Exception:
            failures += 1
    if failures == len(searches):
        raise RuntimeError("no headline search succeeded")
    return news_filter.clean_headlines(raw, time.time(), news_filter.asset_terms(query), limit)


def fetch_headlines(query: str, limit: int = 8) -> list[dict]:
    """Recent, relevant, de-duplicated headlines for one asset search. Empty when the feed has nothing."""
    return gather_headlines(query, market=False, limit=limit)[0]


def fetch_market_headlines(query: str, limit: int = 8) -> list[dict]:
    """Recent, de-duplicated whole-market headlines (no relevance filter: the market is the subject)."""
    return gather_headlines(query, market=True, limit=limit)[0]


def sentiment_ready() -> bool:
    """True when an AI key for scoring is available (the admin's choice, or xAI for Grok). Copies a Streamlit
    secret into the environment once."""
    if scoring_provider() != "grok":
        return True
    if (os.getenv("XAI_API_KEY") or "").strip():
        return True
    try:
        import streamlit as st
        key = str(st.secrets["ai"]["xai_api_key"]).strip()
    except Exception:
        return False
    if not key:
        return False
    os.environ["XAI_API_KEY"] = key
    return True


def _clamp_score(value) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score != score:
        return None
    return max(0.0, min(100.0, score))


def _json_objects(text: str) -> list[dict]:
    """JSON objects in the reply. Grok sometimes wraps the score in words or a code fence."""
    decoder = json.JSONDecoder()
    found = []
    index = 0
    while True:
        start = text.find("{", index)
        if start < 0:
            break
        try:
            data, offset = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(data, dict):
            found.append(data)
        elif isinstance(data, list):
            found.append({"articles": data})
        index = start + max(offset, 1)
    return found


def _prompt(query: str, headlines: list[dict]) -> str:
    lines = []
    for index, item in enumerate(headlines, start=1):
        source = item.get("source") or "Unknown source"
        published = item.get("published") or ""
        lines.append(f"{index}. {item['title']} — {source} {published}".strip())
    return (
        "Score market sentiment from these headlines only. "
        "This is research context, not a forecast or advice. "
        f"Asset search: {query}\n"
        "Headlines:\n"
        + "\n".join(lines)
        + "\n\nReply with JSON only, in this shape: "
        '{"articles":[{"index":1,"score":50,"note":"one sentence"}],"summary":"...","positive":"...","negative":"...","drivers":["..."]}. '
        "Use one article object for every headline, with the same index number. "
        "score is 0 to 100 for that headline alone. "
        "0 is strongly bearish, 50 is mixed or unclear, 100 is strongly bullish. "
        "note is one sentence about that headline only. "
        "summary is two sentences about the set of headlines. "
        "positive is one paragraph on what these headlines treat as favorable. "
        "negative is one paragraph on what these headlines treat as unfavorable. "
        "Each of those paragraphs is two or three sentences. "
        "If the headlines do not support that side, say so in one sentence. "
        "drivers is up to 3 short phrases. "
        "Do not add facts that are not in the headlines."
    )


def _market_prompt(label: str, query: str, headlines: list[dict], readings: str = "") -> str:
    """Same JSON shape as an asset score. Article scores stay on the headlines."""
    lines = []
    for index, item in enumerate(headlines, start=1):
        source = item.get("source") or "Unknown source"
        published = item.get("published") or ""
        lines.append(f"{index}. {item['title']} — {source} {published}".strip())
    reading_block = ""
    if readings.strip():
        reading_block = (
            "\nCurrent readings. These are measurements, not headlines. "
            "summary, positive, and negative may use them. "
            "Each article score and note must stay about that headline only. "
            "Do not invent a reading that is not listed.\n"
            + readings.strip()
            + "\n"
        )
    return (
        "Score market sentiment from these headlines and, where listed, the current readings. "
        "This is research context, not a forecast or advice. "
        f"This is the {label} as a whole, not one asset. Search: {query}\n"
        + reading_block
        + "Headlines:\n"
        + "\n".join(lines)
        + "\n\nReply with JSON only, in this shape: "
        '{"articles":[{"index":1,"score":50,"note":"one sentence"}],"summary":"...","positive":"...","negative":"...","drivers":["..."]}. '
        "Use one article object for every headline, with the same index number. "
        "score is 0 to 100 for that headline alone. "
        "0 is strongly bearish, 50 is mixed or unclear, 100 is strongly bullish. "
        "note is one sentence about that headline only. "
        "summary is two sentences about the headlines and the current readings. "
        "positive is one paragraph on what these treat as favorable. "
        "negative is one paragraph on what these treat as unfavorable. "
        "Each of those paragraphs is two or three sentences. "
        "If the material does not support that side, say so in one sentence. "
        "drivers is up to 3 short phrases. "
        "Do not add facts that are not in the headlines or the current readings."
    )


def _coerce_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and (part.get("text") or part.get("content")):
                chunks.append(str(part.get("text") or part.get("content")))
        return "\n".join(chunks)
    return ""


def _reply_texts(payload: dict) -> list[str]:
    """Visible reply first, then a reasoning trace. Either one may hold the JSON."""
    texts = []
    choices = payload.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        for key in ("content", "reasoning_content"):
            text = _coerce_text(message.get(key))
            if text.strip():
                texts.append(text)
    for item in payload.get("output") or []:
        if isinstance(item, dict):
            text = _coerce_text(item.get("content"))
            if text.strip():
                texts.append(text)
    return texts


def _paragraph(value) -> str:
    """One block of prose. A list of sentences is joined. Empty when there is nothing."""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if str(item).strip())
    return " ".join(str(value or "").split())[:700]


def _field(data: dict, *names):
    lowered = {str(key).lower(): value for key, value in data.items()}
    for name in names:
        if name in lowered:
            return lowered[name]
    return None


def _strict_score(value) -> float | None:
    """A 0-100 article score, or None. Out-of-range values are rejected rather than clamped:
    a model that answers on another scale must not be read as an extreme."""
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score != score or score < 0 or score > 100:
        return None
    return score


def _first_score(item: dict) -> float | None:
    for name in ("score", "sentiment", "sentiment_score", "value", "rating"):
        score = _strict_score(_field(item, name))
        if score is not None:
            return score
    return None


MIN_SCORED_SHARE = 0.5   # a reply that scores fewer than half the headlines is treated as a failed reply


def _first_index(item: dict) -> int | None:
    for name in ("index", "i", "n", "headline", "article", "id"):
        raw = _field(item, name)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 <= value <= 50:
            return value
    return None


def _short_note(value) -> str:
    """One sentence for a headline. Empty when the model did not write one."""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if str(item).strip())
    return " ".join(str(value or "").split())[:240]


def _first_note(item: dict) -> str:
    raw = _field(item, "note", "blurb", "line")
    if raw is None:
        raw = _field(item, "summary")
    return _short_note(raw)


def _collect_scores(raw, count: int) -> dict[int, float]:
    """Map headline numbers to scores. A bare list is read in headline order."""
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("index", key)
                rows.append(row)
            else:
                rows.append({"index": key, "score": value})
        return _collect_scores(rows, count)
    if not isinstance(raw, list):
        return {}

    indexed = {}
    positional = []
    saw_index = False
    for item in raw:
        if isinstance(item, dict):
            score = _first_score(item)
            if score is None:
                continue
            index = _first_index(item)
            if index is None:
                positional.append(score)
            else:
                saw_index = True
                indexed[index] = score
        else:
            score = _clamp_score(item)
            if score is not None:
                positional.append(score)
    if saw_index:
        if 0 in indexed:
            indexed = {index + 1: score for index, score in indexed.items() if index >= 0}
        return {index: score for index, score in indexed.items() if 1 <= index <= max(count, 1)}
    return {
        position: score
        for position, score in enumerate(positional, start=1)
        if position <= max(count, 1)
    }


def _collect_notes(raw, count: int) -> dict[int, str]:
    """Map headline numbers to the one-sentence note. A bare list is read in order."""
    if isinstance(raw, dict):
        rows = []
        for key, value in raw.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("index", key)
                rows.append(row)
            elif isinstance(value, str):
                rows.append({"index": key, "note": value})
        return _collect_notes(rows, count)
    if not isinstance(raw, list):
        return {}
    indexed = {}
    positional = []
    saw_index = False
    for item in raw:
        if not isinstance(item, dict):
            note = _short_note(item)
            if note:
                positional.append(note)
            continue
        note = _first_note(item)
        if not note:
            continue
        index = _first_index(item)
        if index is None:
            positional.append(note)
        else:
            saw_index = True
            indexed[index] = note
    if saw_index:
        if 0 in indexed:
            indexed = {index + 1: note for index, note in indexed.items() if index >= 0}
        return {index: note for index, note in indexed.items() if 1 <= index <= max(count, 1)}
    return {
        position: note
        for position, note in enumerate(positional, start=1)
        if position <= max(count, 1)
    }


def _read_parsed(parsed: dict, headline_count: int) -> dict:
    articles = _field(parsed, "articles", "article_scores", "headlines", "items")
    scores = _collect_scores(articles, headline_count)
    notes = _collect_notes(articles, headline_count)
    overall = None
    for name in ("score", "overall", "overall_score", "sentiment", "sentiment_score"):
        overall = _clamp_score(_field(parsed, name))
        if overall is not None:
            break
    if not scores and overall is None:
        return {"ok": False, "reason": "model_error"}
    summary = " ".join(str(_field(parsed, "summary") or "").split())
    raw_drivers = _field(parsed, "drivers", "driver") or []
    if isinstance(raw_drivers, str):
        raw_drivers = [raw_drivers]
    drivers = []
    if isinstance(raw_drivers, list):
        for item in raw_drivers:
            text = " ".join(str(item).split())
            if text:
                drivers.append(text[:160])
            if len(drivers) == 3:
                break
    return {
        "ok": True,
        "scores": scores,
        "notes": notes,
        "overall": overall,
        "summary": summary,
        "positive": _paragraph(_field(parsed, "positive", "positives", "bullish")),
        "negative": _paragraph(_field(parsed, "negative", "negatives", "bearish")),
        "drivers": drivers,
        "tr": _field(parsed, "tr", "translations"),
    }


def _read_model_text(response: requests.Response, headline_count: int) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "reason": "model_error"}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "model_error"}
    for text in _reply_texts(payload):
        objects = _json_objects(text)
        for parsed in reversed(objects):
            read = _read_parsed(parsed, headline_count)
            if read.get("ok"):
                return read
    return {"ok": False, "reason": "model_error"}


def _post_grok(key: str, prompt: str, attempt: dict, structured: bool = True, langs=()) -> requests.Response:
    """Ask Grok for the score. The plain retry drops fields a model may reject."""
    body = {
        "model": attempt["model"],
        "messages": [
            {
                "role": "system",
                "content": "You score headlines and reply with one JSON object only.",
            },
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": _max_tokens(langs),
    }
    if structured:
        body["temperature"] = 0.2
        body["response_format"] = {"type": "json_object"}
    if attempt.get("reasoning_effort"):
        body["reasoning_effort"] = attempt["reasoning_effort"]
    return requests.post(
        _CHAT_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        timeout=40 + 20 * len(langs or ()),
    )


def _error_text(response: requests.Response) -> str:
    """A short API message with the key removed, for the worker log."""
    message = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or error.get("code") or "")
        elif isinstance(error, str):
            message = error
    if not message:
        message = response.text or ""
    message = " ".join(message.split())
    secret = (os.getenv("XAI_API_KEY") or "").strip()
    if secret:
        message = message.replace(secret, "")
    return message[:180]


def _rejected_key(response: requests.Response) -> bool:
    """xAI reports a bad key as 400, not only as 401."""
    if response.status_code in (401, 403):
        return True
    if response.status_code != 400:
        return False
    return "incorrect api key" in _error_text(response).lower()


def _attempt_note(model: str, response: requests.Response, label: str = "") -> str:
    """Status only. A successful parse is not logged."""
    name = f"{model}{label}"
    if response.status_code != 200:
        return f"{name} {response.status_code} {_error_text(response)}".strip()
    finish = "none"
    refusal = ""
    chars = 0
    try:
        payload = response.json()
    except ValueError:
        return f"{name} 200 not-json"
    if isinstance(payload, dict):
        chars = sum(len(item) for item in _reply_texts(payload))
        choices = payload.get("choices") or []
        if choices and isinstance(choices[0], dict):
            finish = str(choices[0].get("finish_reason") or "none")
            message = choices[0].get("message") or {}
            refusal = " ".join(str(message.get("refusal") or "").split())[:80]
    note = f"{name} 200 finish={finish} chars={chars}"
    if refusal:
        note += f" refusal={refusal}"
    return note


def _scored_report(parsed: dict, headlines: list[dict]) -> dict | None:
    """The report from one valid reply. None when the reply is incomplete: fewer than half the
    headlines scored (then the next model is tried), or no score at all."""
    if headlines and parsed.get("scores") and len(parsed["scores"]) < MIN_SCORED_SHARE * len(headlines):
        return None
    scored = []
    values = []
    for index, item in enumerate(headlines, start=1):
        row = dict(item)
        if index in parsed["scores"]:
            row["score"] = parsed["scores"][index]
            values.append(row["score"])
        note = (parsed.get("notes") or {}).get(index) or ""
        if note:
            row["note"] = note
        scored.append(row)
    if values:
        score = sum(values) / len(values)
    else:
        score = parsed.get("overall")
    if score is None:
        return None
    return {
        "ok": True,
        "score": score,
        "scored": len(values),
        "summary": parsed.get("summary") or "",
        "positive": parsed.get("positive") or "",
        "negative": parsed.get("negative") or "",
        "drivers": parsed.get("drivers") or [],
        "headlines": scored,
    }


def _add_translations(report: dict, raw, langs) -> dict:
    """Put the translated text on a report: per-headline notes on each row, the rest under report["tr"]."""
    tr = _read_translations(raw, langs)
    if not tr:
        return report
    for index, row in enumerate(report.get("headlines") or [], start=1):
        words = {code: entry["notes"][index] for code, entry in tr.items() if index in (entry.get("notes") or {})}
        if words:
            row["tr"] = words
    report["tr"] = {code: {k: v for k, v in entry.items() if k != "notes"} for code, entry in tr.items()}
    return report


def _summarize_with(provider: str, query: str, headlines: list[dict], prompt: str, langs=()) -> dict:
    """The score from another AI than Grok (the admin's choice): the same prompt and the same reading of the reply."""
    import ai_providers

    try:
        text, _done = ai_providers.chat(provider, "You score headlines and reply with one JSON object only.",
                                        [{"role": "user", "content": prompt}], _max_tokens(langs), json_only=True,
                                        timeout=60 + 20 * len(langs))
    except Exception as exc:
        words = str(exc)
        print(f"{ai_providers.label(provider)} did not return a score: {words[:200]}", flush=True)
        if " 401" in words or " 403" in words:
            return {"ok": False, "reason": "bad_key"}
        _BUSY_UNTIL[query] = time.time() + 60
        return {"ok": False, "reason": "model_busy"}
    for parsed in reversed(_json_objects(text)):
        read = _read_parsed(parsed, len(headlines))
        if read.get("ok"):
            report = _scored_report(read, headlines)
            if report:
                _add_translations(report, read.get("tr"), langs)
                report["model"] = f"{provider}:{ai_providers.model(provider)}"
                _BUSY_UNTIL.pop(query, None)
                return report
    print(f"{ai_providers.label(provider)} gave no usable score.", flush=True)
    return {"ok": False, "reason": "model_error"}


def _max_tokens(langs) -> int:
    """Room for the reply: the English, plus about as much again for each language asked for."""
    return min(16000, 1800 + 1300 * len(langs or ()))


def _summarize(query: str, headlines: list[dict], prompt: str | None = None, notes_only: bool = False) -> dict:
    """The score and text, also in the languages accounts use (set_languages). If the longer reply with translations
    fails, it is asked again in English only, so a translation problem never costs the score."""
    langs = _LANGUAGES
    base = prompt or _prompt(query, headlines)
    if langs:
        report = _summarize_once(query, headlines, _with_translations(base, langs, notes_only), langs)
        if report.get("ok") or report.get("reason") != "model_error":
            return report
        print(f"Scoring with translations failed for {query}; asking again in English only.", flush=True)
    return _summarize_once(query, headlines, base, ())


def _summarize_once(query: str, headlines: list[dict], prompt: str, langs) -> dict:
    global _KEY_REJECTED
    provider = scoring_provider()
    if provider != "grok":
        if time.time() < _BUSY_UNTIL.get(query, 0):
            return {"ok": False, "reason": "model_busy"}
        return _summarize_with(provider, query, headlines, prompt, langs)
    key = _api_key()
    if not key:
        return {"ok": False, "reason": "missing_key"}
    if _KEY_REJECTED:
        return {"ok": False, "reason": "bad_key"}
    if time.time() < _BUSY_UNTIL.get(query, 0):
        return {"ok": False, "reason": "model_busy"}

    saw_busy = False
    saw_auth = False
    notes = []
    for attempt in _MODELS:
        try:
            response = _post_grok(key, prompt, attempt, langs=langs)
        except requests.RequestException as exc:
            notes.append(f"{attempt['model']} network {exc.__class__.__name__}")
            saw_busy = True
            break
        notes.append(_attempt_note(attempt["model"], response))
        if _rejected_key(response):
            saw_auth = True
            break
        if response.status_code in (400, 422):
            try:
                response = _post_grok(key, prompt, attempt, structured=False, langs=langs)
            except requests.RequestException as exc:
                notes.append(f"{attempt['model']} plain network {exc.__class__.__name__}")
                saw_busy = True
                break
            notes.append(_attempt_note(attempt["model"], response, " plain"))
            if _rejected_key(response):
                saw_auth = True
                break
        if response.status_code == 200:
            try:
                parsed = _read_model_text(response, len(headlines))
            except (ValueError, json.JSONDecodeError):
                continue
            if parsed.get("ok"):
                report = _scored_report(parsed, headlines)
                if report:
                    _add_translations(report, parsed.get("tr"), langs)
                    report["model"] = attempt["model"]
                    _BUSY_UNTIL.pop(query, None)
                    return report
                notes.append(f"{attempt['model']} incomplete reply")
            continue
        if response.status_code in (401, 403):
            saw_auth = True
            break
        if response.status_code in (400, 404, 422):
            continue
        if response.status_code in (429, 500, 503):
            saw_busy = True
            continue
        saw_busy = True

    if saw_auth:
        _KEY_REJECTED = True
        reason = "bad_key"
        print(f"Grok rejected the API key (length {len(key)}).", flush=True)
    elif saw_busy:
        _BUSY_UNTIL[query] = time.time() + 60
        reason = "model_busy"
        print(f"Grok did not return a score: {' | '.join(notes)}", flush=True)
    else:
        reason = "model_error"
        print(f"Grok did not return a score: {' | '.join(notes)}", flush=True)
    return {"ok": False, "reason": reason}


def sentiment_cached_at(query: str) -> float | None:
    """When the current score was stored, or None when this asset has no saved score."""
    cached = _SCORE_CACHE.get(query)
    if not cached:
        return None
    return cached[0]


def remember_sentiment(query: str, report: dict, stored_at: float) -> None:
    """Keep a shared headline score in this process so the table can show it."""
    if not query or not isinstance(report, dict) or not report.get("ok"):
        return
    _SCORE_CACHE[query] = (float(stored_at), report)


def cached_sentiment_score(query: str) -> float | None:
    """The last saved headline score, including one waiting on the next background update."""
    cached = _SCORE_CACHE.get(query)
    if not cached:
        return None
    stored = cached[1]
    if not stored.get("ok"):
        return None
    try:
        score = float(stored.get("score"))
    except (TypeError, ValueError):
        return None
    if score != score:
        return None
    return score


def _ids(rows) -> list[str]:
    return [str(row.get("id")) for row in rows or [] if isinstance(row, dict) and row.get("id")]


def reuse_scores(report: dict, previous: dict | None) -> dict:
    """An article already scored in the previous report (by the same model) keeps that score and
    note, so the same story is not scored differently on every refresh. The average is recomputed
    the same way as before (each scored headline counts once)."""
    if not (isinstance(previous, dict) and previous.get("ok") and report.get("ok")):
        return report
    if previous.get("model") and report.get("model") and previous["model"] != report["model"]:
        return report
    known = {str(row["id"]): row for row in previous.get("headlines") or []
             if isinstance(row, dict) and row.get("id") and row.get("score") is not None}
    reused = 0
    for row in report.get("headlines") or []:
        old = known.get(str(row.get("id") or ""))
        if old is None:
            continue
        row["score"] = old["score"]
        if old.get("note"):
            row["note"] = old["note"]
            if isinstance(old.get("tr"), dict):          # the old note's own translations, new languages added
                row["tr"] = {**(row.get("tr") or {}), **old["tr"]}
        reused += 1
    if reused:
        values = _scores_in(report.get("headlines"))
        if values:
            report["score"] = sum(values) / len(values)
        report["reused_articles"] = reused
    return report


def _with_quality(report: dict, stats: dict) -> dict:
    report["coverage"] = news_filter.coverage(report.get("headlines") or [])
    report["filtered"] = {k: v for k, v in (stats or {}).items() if k not in ("events", "sources", "level")}
    return report


def analyze_market_sentiment(query: str, enabled: bool, force: bool = False, previous: dict | None = None) -> dict:
    """Headlines plus a score when an xAI key is configured.

    A successful score is reused for 12 hours. A busy model is not cached,
    so the next look can try again. force skips that window and asks again.
    previous is the last stored report: when the cleaned headlines are exactly the ones it scored,
    it is reused without asking the model again; otherwise its article scores are reused.
    """
    if force:
        _SCORE_CACHE.pop(query, None)
        _BUSY_UNTIL.pop(query, None)
    cached = _SCORE_CACHE.get(query)
    if enabled and not force and cached and time.time() - cached[0] < SENTIMENT_REFRESH_SECONDS:
        stored = cached[1]
        stored_rows = stored.get("headlines") or []
        if stored.get("ok") and stored.get("score") is not None and stored_rows:
            return stored
    try:
        headlines, stats = gather_headlines(query)
    except Exception:
        return {"ok": False, "reason": "headlines_error", "headlines": []}
    if not headlines:
        return {"ok": False, "reason": "no_headlines", "headlines": [], "filtered": stats}
    if not enabled:
        return {"ok": False, "reason": "missing_key", "headlines": headlines}
    if (isinstance(previous, dict) and previous.get("ok") and previous.get("model") and has_languages(previous)
            and sorted(_ids(previous.get("headlines"))) == sorted(_ids(headlines))):
        summary = copy.deepcopy(previous)
        summary["reused_report"] = True
        _with_quality(summary, stats)
        _SCORE_CACHE[query] = (time.time(), summary)
        return summary
    try:
        summary = _summarize(query, headlines)
    except Exception:
        summary = {"ok": False, "reason": "model_error"}
    if not summary.get("headlines"):
        summary["headlines"] = headlines
    if summary.get("ok"):
        reuse_scores(summary, previous)
        _with_quality(summary, stats)
        _SCORE_CACHE[query] = (time.time(), summary)
    return summary


def _reading_fingerprint(groups: list[dict]) -> str:
    parts = []
    for group in groups or []:
        for item in group.get("items") or []:
            parts.append("|".join((
                str(item.get("name") or ""),
                str(item.get("value") or ""),
                str(item.get("detail") or ""),
            )))
    return "\n".join(parts)


def _readings_prompt(label: str, groups: list[dict]) -> str:
    lines = []
    index = 1
    for group in groups or []:
        items = group.get("items") or []
        if not items:
            continue
        lines.append(str(group.get("title") or "Readings"))
        for item in items:
            detail = str(item.get("detail") or "").strip()
            source = str(item.get("source") or "").strip()
            lines.append(
                f"{index}. {item.get('name')}: {item.get('value')}. {detail} ({source})".strip()
            )
            index += 1
    return (
        f"Score each reading for the {label} as a whole. "
        "This is research context, not a forecast or advice. "
        "A higher score means the reading is more supportive for this market. "
        "0 is strongly bearish, 50 is mixed or unclear, 100 is strongly bullish. "
        "note is one sentence on what this reading implies for the market. "
        "Use only the figures listed. Do not invent a number or a source.\n"
        + "\n".join(lines)
        + "\n\nReply with JSON only, in this shape: "
        '{"articles":[{"index":1,"score":50,"note":"one sentence"}],"summary":"","positive":"","negative":"","drivers":[]}. '
        "Use one article object for every reading, with the same index number."
    )


_READING_CACHE: dict[str, tuple[float, str, list]] = {}


def score_market_readings(market_key: str, label: str, groups: list[dict]) -> list[dict]:
    """Add a 0–100 score and one sentence to each public reading. Reused for 12 hours."""
    if not groups or not any(group.get("items") for group in groups):
        return groups
    fingerprint = _reading_fingerprint(groups)
    cached = _READING_CACHE.get(market_key)
    if cached and cached[1] == fingerprint and time.time() - cached[0] < SENTIMENT_REFRESH_SECONDS:
        return cached[2]
    if not sentiment_ready():
        return groups
    headlines = []
    for group in groups:
        for item in group.get("items") or []:
            headlines.append({
                "title": f"{item.get('name')}: {item.get('value')}",
                "source": item.get("source") or "",
                "published": item.get("published") or "",
                "link": item.get("href") or "https://fred.stlouisfed.org/",
            })
    try:
        report = _summarize(f"readings:{market_key}", headlines, _readings_prompt(label, groups), notes_only=True)
    except Exception:
        return groups
    scored_rows = report.get("headlines") or []
    if not report.get("ok") or len(scored_rows) != len(headlines):
        return groups
    scored = copy.deepcopy(groups)
    flat = [item for group in scored for item in (group.get("items") or [])]
    for item, row in zip(flat, scored_rows):
        if item.get("stale"):
            continue                                       # out of date: shown, never scored (market_gauges.is_stale)
        if row.get("score") is not None:
            item["score"] = row["score"]
        note = " ".join(str(row.get("note") or "").split())
        if note:
            item["note"] = note
        if row.get("tr"):
            item["tr"] = row["tr"]
    if any(item.get("score") is not None for item in flat):
        _READING_CACHE[market_key] = (time.time(), fingerprint, scored)
        return scored
    return groups


def _scores_in(rows) -> list[float]:
    values = []
    for row in rows or []:
        try:
            value = float((row or {}).get("score"))
        except (TypeError, ValueError, AttributeError):
            continue
        if value == value:
            values.append(value)
    return values


# A score of 45..55 is mixed. A note that says the market is helped (up) with a score under 45, or hurt (down) with a
# score over 55, contradicts itself (24 Nov 2026: "only 5 falling is mildly bullish", scored -30).
MIXED_LOW, MIXED_HIGH = 45, 55


def _review_items(report: dict) -> list[dict]:
    """Every scored row of a report (news, then readings), as the review sees it."""
    rows = [row for row in report.get("headlines") or [] if isinstance(row, dict)]
    rows += [item for group in report.get("gauges") or [] if isinstance(group, dict)
             for item in group.get("items") or [] if isinstance(item, dict)]
    return [row for row in rows if row.get("score") is not None and str(row.get("note") or "").strip()]


def _translations_of(report: dict, rows: list[dict]) -> list[dict]:
    """[{"ref", "english", "translated"}] for every translated piece of AI text in a report."""
    out = []
    for lang, fields in (report.get("tr") or {}).items() if isinstance(report.get("tr"), dict) else ():
        for name in ("summary", "positive", "negative"):
            if isinstance(fields, dict) and fields.get(name) and report.get(name):
                out.append({"ref": f"{lang}:{name}", "english": report[name], "translated": fields[name]})
    lead = report.get("lead") if isinstance(report.get("lead"), dict) else {}
    for lang, words in (lead.get("tr") or {}).items():
        if words and lead.get("why"):
            out.append({"ref": f"{lang}:lead", "english": lead["why"], "translated": words})
    for i, row in enumerate(rows):
        for lang, words in (row.get("tr") or {}).items() if isinstance(row.get("tr"), dict) else ():
            if words and row.get("note"):
                out.append({"ref": f"{lang}:note:{i}", "english": row["note"], "translated": words})
    return out


def _drop_translation(report: dict, rows: list[dict], ref: str) -> bool:
    parts = ref.split(":")
    try:
        if len(parts) == 2 and parts[1] in ("summary", "positive", "negative"):
            return report["tr"][parts[0]].pop(parts[1], None) is not None
        if len(parts) == 2 and parts[1] == "lead":
            return report["lead"]["tr"].pop(parts[0], None) is not None
        if len(parts) == 3 and parts[1] == "note":
            return rows[int(parts[2])]["tr"].pop(parts[0], None) is not None
    except (KeyError, IndexError, ValueError, TypeError, AttributeError):
        return False
    return False


def _contradicts(direction: str, score) -> bool:
    try:
        score = float(score)
    except (TypeError, ValueError):
        return False
    return (direction == "up" and score < MIXED_LOW) or (direction == "down" and score > MIXED_HIGH)


def _ask_json(ask: str, chat=None) -> dict:
    if chat is None:
        import ai_providers

        text, _done = ai_providers.chat(scoring_provider(), "You check market text. Reply with one JSON object only.",
                                        [{"role": "user", "content": ask}], max_tokens=3000, json_only=True,
                                        timeout=90)
    else:
        text = chat(ask)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def review_report(report: dict, chat=None) -> dict:
    """Two checks on every refresh, for any market and any day (24 Nov 2026):
    - a score that contradicts its own sentence is scored once more, and left unscored if it still does;
    - a translation that changes the meaning (up told as down, a different number) is dropped, so the English shows.
    The counts go in report["checks"] and the worker's log. An AI that doesn't answer changes nothing."""
    rows = _review_items(report)
    pieces = _translations_of(report, rows)
    checks = {"rows": len(rows), "rescored": 0, "unscored": 0, "translations": len(pieces), "translations_dropped": 0}
    if not rows and not pieces:
        report["checks"] = checks
        return report
    listing = "\n".join(f"{i}. {row.get('title') or row.get('name')}: {row.get('value') or ''} | note: {row['note']}"
                        for i, row in enumerate(rows))
    trans = "\n".join(f"{p['ref']} | English: {p['english']} | Translation: {p['translated']}" for p in pieces)
    ask = ("Check market text. 1) For each numbered note, say whether the note itself describes the market as helped "
           "(up), hurt (down) or neither (neutral). Judge the note's meaning, not single words. "
           "2) For each translation, say whether it changes the meaning of the English: a different direction (rise "
           "told as fall), a different number, or a different subject. Wording differences are fine.\n"
           'Reply with JSON only: {"directions": {"0": "up|down|neutral", ...}, "bad_translations": ["<ref>", ...]}\n'
           f"Notes:\n{listing or '(none)'}\nTranslations:\n{trans or '(none)'}")
    try:
        got = _ask_json(ask, chat)
    except Exception:
        report["checks"] = {**checks, "skipped": True}
        return report
    directions = {int(k): str(v).lower() for k, v in (got.get("directions") or {}).items() if str(k).isdigit()}
    wrong = [i for i, row in enumerate(rows) if i < len(rows) and _contradicts(directions.get(i, ""), row["score"])]
    if wrong:
        again = "\n".join(f"{i}. {rows[i].get('title') or rows[i].get('name')}: {rows[i].get('value') or ''} | "
                          f"note: {rows[i]['note']}" for i in wrong)
        try:
            fresh = _ask_json("Score each item 0 to 100 for this market as a whole, consistent with its note: 0 is "
                              "strongly bearish, 50 mixed, 100 strongly bullish. "
                              'Reply with JSON only: {"scores": {"<number>": score, ...}}\n' + again, chat)
            scores = {int(k): v for k, v in (fresh.get("scores") or {}).items() if str(k).isdigit()}
        except Exception:
            scores = {}
        for i in wrong:
            new = _clamp_score(scores.get(i))
            if new is not None and not _contradicts(directions[i], new):
                rows[i]["score"] = new
                checks["rescored"] += 1
            else:
                rows[i]["score"] = None
                checks["unscored"] += 1
    for ref in got.get("bad_translations") or []:
        if _drop_translation(report, rows, str(ref)):
            checks["translations_dropped"] += 1
    report["checks"] = checks
    return report


def combine_mood_score(report: dict) -> dict:
    """A market score is the average of every scored item: the news articles and the public
    readings (central banks, yields, Fear & Greed...) alike, each counting once. The two
    separate averages are kept too, for the hover text."""
    news = _scores_in(report.get("headlines"))
    readings = _scores_in(item for group in report.get("gauges") or [] for item in (group or {}).get("items") or [])
    both = news + readings
    if both:
        report["score"] = sum(both) / len(both)
        report["score_parts"] = {
            "news": len(news), "readings": len(readings),
            "news_score": sum(news) / len(news) if news else None,
            "readings_score": sum(readings) / len(readings) if readings else None,
        }
    return report


def analyze_market_mood(market_key: str, label: str, query: str, enabled: bool, force: bool = False,
                        previous: dict | None = None) -> dict:
    """One whole-market score. Reused for 12 hours. Separate from any asset score."""
    cache_key = f"mood:{market_key}"
    if force:
        _SCORE_CACHE.pop(cache_key, None)
        _BUSY_UNTIL.pop(cache_key, None)
        _READING_CACHE.pop(market_key, None)
        _BUSY_UNTIL.pop(f"readings:{market_key}", None)
    cached = _SCORE_CACHE.get(cache_key)
    if enabled and not force and cached and time.time() - cached[0] < SENTIMENT_REFRESH_SECONDS:
        stored = cached[1]
        if stored.get("ok") and stored.get("score") is not None and stored.get("headlines"):
            return stored
    spec = MOOD_SPECS.get(market_key) or {}
    try:
        if spec.get("searches"):
            headlines, stats = gather_market_news(spec["searches"])
        else:
            headlines, stats = gather_headlines(query, market=True)
    except Exception:
        return {"ok": False, "reason": "headlines_error", "headlines": []}
    if not headlines:
        return {"ok": False, "reason": "no_headlines", "headlines": []}
    if not enabled:
        return {"ok": False, "reason": "missing_key", "headlines": headlines}
    gauges = []
    brief = ""
    try:
        from market_gauges import gauge_brief, market_gauge_groups
        gauges = market_gauge_groups(market_key)
        gauges = score_market_readings(market_key, label, gauges)
        brief = gauge_brief(gauges)
    except Exception:
        gauges = []
        brief = ""
    try:
        summary = _summarize(
            cache_key,
            headlines,
            _market_prompt(label, query, headlines, brief),
        )
    except Exception:
        summary = {"ok": False, "reason": "model_error"}
    if isinstance(summary, dict) and gauges:
        summary["gauges"] = gauges
    if not summary.get("headlines"):
        summary["headlines"] = headlines
    if summary.get("ok"):
        reuse_scores(summary, previous)
        _with_quality(summary, stats)
        if spec:
            lead = lead_story(spec, summary.get("headlines") or [])
            if lead:
                summary["lead"] = lead
        review_report(summary)
        combine_mood_score(summary)
        print(f"Market sentiment {market_key}: {json.dumps(summary.get('checks') or {})}", flush=True)
    if summary.get("ok"):
        _SCORE_CACHE[cache_key] = (time.time(), summary)
    return summary
