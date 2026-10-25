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
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

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


def _api_key() -> str:
    """The xAI key, without a wrapping quote or a pasted Bearer prefix."""
    key = (os.getenv("XAI_API_KEY") or "").strip().strip('"').strip("'")
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def sentiment_query(kind: str, label: str, ticker: str | None) -> str:
    """Search text for one asset. The extra word keeps the name from matching the wrong thing."""
    name = " ".join((label or "").replace("(", " ").replace(")", " ").split())
    symbol = (ticker or "").strip().upper()
    parts = [name]
    if symbol and symbol not in name.upper():
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
MACRO_MOODS = (
    {
        "key": "crypto",
        "label": "Crypto market",
        "query": "crypto market outlook regulation ETF liquidity",
    },
    {
        "key": "stock",
        "label": "Stock market",
        "query": "stock market outlook inflation interest rates earnings",
    },
)
_MOOD_SKIP = ("presale", "airdrop", "openpr", "price prediction", "what will", "be worth")


def fetch_headlines(query: str, limit: int = 8) -> list[dict]:
    """Recent headline, source, time, and link. Empty when the feed has nothing."""
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
    return newest_first(headlines)[:limit]


def fetch_market_headlines(query: str, limit: int = 8) -> list[dict]:
    """Market headlines, without presales and price-prediction repeats."""
    kept = []
    for item in fetch_headlines(query, limit=24):
        blob = f"{item.get('title') or ''} {item.get('source') or ''}".lower()
        if any(word in blob for word in _MOOD_SKIP):
            continue
        kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def sentiment_ready() -> bool:
    """True when an xAI key is available. Copies a Streamlit secret into the environment once."""
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


def _first_score(item: dict) -> float | None:
    for name in ("score", "sentiment", "sentiment_score", "value", "rating"):
        score = _clamp_score(_field(item, name))
        if score is not None:
            return score
    return None


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


def _post_grok(key: str, prompt: str, attempt: dict, structured: bool = True) -> requests.Response:
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
        "max_completion_tokens": 1800,
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
        timeout=40,
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
        "summary": parsed.get("summary") or "",
        "positive": parsed.get("positive") or "",
        "negative": parsed.get("negative") or "",
        "drivers": parsed.get("drivers") or [],
        "headlines": scored,
    }


def _summarize(query: str, headlines: list[dict], prompt: str | None = None) -> dict:
    global _KEY_REJECTED
    key = _api_key()
    if not key:
        return {"ok": False, "reason": "missing_key"}
    if _KEY_REJECTED:
        return {"ok": False, "reason": "bad_key"}
    if time.time() < _BUSY_UNTIL.get(query, 0):
        return {"ok": False, "reason": "model_busy"}

    prompt = prompt or _prompt(query, headlines)
    saw_busy = False
    saw_auth = False
    notes = []
    for attempt in _MODELS:
        try:
            response = _post_grok(key, prompt, attempt)
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
                response = _post_grok(key, prompt, attempt, structured=False)
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
                    _BUSY_UNTIL.pop(query, None)
                    return report
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


def analyze_market_sentiment(query: str, enabled: bool, force: bool = False) -> dict:
    """Headlines plus a score when an xAI key is configured.

    A successful score is reused for 12 hours. A busy model is not cached,
    so the next look can try again. force skips that window and asks again.
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
        headlines = fetch_headlines(query)
    except Exception:
        return {"ok": False, "reason": "headlines_error", "headlines": []}
    if not headlines:
        return {"ok": False, "reason": "no_headlines", "headlines": []}
    if not enabled:
        return {"ok": False, "reason": "missing_key", "headlines": headlines}
    try:
        summary = _summarize(query, headlines)
    except Exception:
        summary = {"ok": False, "reason": "model_error"}
    if not summary.get("headlines"):
        summary["headlines"] = headlines
    if summary.get("ok"):
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
        report = _summarize(f"readings:{market_key}", headlines, _readings_prompt(label, groups))
    except Exception:
        return groups
    scored_rows = report.get("headlines") or []
    if not report.get("ok") or len(scored_rows) != len(headlines):
        return groups
    scored = copy.deepcopy(groups)
    flat = [item for group in scored for item in (group.get("items") or [])]
    for item, row in zip(flat, scored_rows):
        if row.get("score") is not None:
            item["score"] = row["score"]
        note = " ".join(str(row.get("note") or "").split())
        if note:
            item["note"] = note
    if any(item.get("score") is not None for item in flat):
        _READING_CACHE[market_key] = (time.time(), fingerprint, scored)
        return scored
    return groups


def analyze_market_mood(market_key: str, label: str, query: str, enabled: bool, force: bool = False) -> dict:
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
    try:
        headlines = fetch_market_headlines(query)
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
        _SCORE_CACHE[cache_key] = (time.time(), summary)
    return summary
