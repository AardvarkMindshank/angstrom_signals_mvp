"""
Market sentiment from recent headlines for the asset open on the chart.

Headlines come from Google News. Grok turns them into a 0–100 score.
The score is not blended into the technical score.
"""

from __future__ import annotations

import html
import json
import os
import time
import xml.etree.ElementTree as ET

import requests

# grok-4.3 can turn reasoning off, so a short headline score returns quickly.
# grok-4.5 is only used if that model name is rejected.
_MODELS = (
    {"model": "grok-4.3", "reasoning_effort": "none"},
    {"model": "grok-4.3"},
    {"model": "grok-4.5"},
)
_CHAT_URL = "https://api.x.ai/v1/chat/completions"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}
_BUSY_UNTIL: dict[str, float] = {}
_SCORE_CACHE: dict[str, tuple[float, dict]] = {}


def sentiment_query(kind: str, label: str, ticker: str | None) -> str:
    """Search text for one asset. The extra word keeps the name from matching the wrong thing."""
    name = " ".join((label or "").replace("(", " ").replace(")", " ").split())
    symbol = (ticker or "").strip().upper()
    parts = [name]
    if symbol and symbol not in name.upper():
        parts.append(symbol)
    parts.append("cryptocurrency" if kind == "Crypto" else "stock")
    return " ".join(part for part in parts if part)


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
        if len(headlines) >= limit:
            break
    return headlines


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


def _parse_model_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Sentiment response was not a JSON object.")
    return data


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
        + "\n\nReturn JSON with score, summary, and drivers. "
        "articles is one object per headline, using the same index numbers, "
        "each with a score from 0 to 100 for that headline alone. "
        "0 is strongly bearish, 50 is mixed or unclear, 100 is strongly bullish. "
        "summary is two sentences about the set of headlines. "
        "drivers is up to 3 short phrases. "
        "Do not add facts that are not in the headlines."
    )


def _message_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    content = ((choices[0].get("message") or {}).get("content"))
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and part.get("text"):
                chunks.append(str(part["text"]))
        return "\n".join(chunks)
    return ""


def _read_model_text(response: requests.Response) -> dict:
    text = _message_text(response.json())
    if not text:
        return {"ok": False, "reason": "model_error"}
    parsed = _parse_model_json(text)
    scores = {}
    for item in parsed.get("articles") or []:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        score = _clamp_score(item.get("score"))
        if score is not None:
            scores[index] = score
    if not scores:
        return {"ok": False, "reason": "model_error"}
    summary = " ".join(str(parsed.get("summary") or "").split())
    drivers = []
    for item in parsed.get("drivers") or []:
        text = " ".join(str(item).split())
        if text:
            drivers.append(text[:160])
        if len(drivers) == 3:
            break
    return {"ok": True, "scores": scores, "summary": summary, "drivers": drivers}


def _post_grok(key: str, prompt: str, attempt: dict) -> requests.Response:
    body = {
        "model": attempt["model"],
        "messages": [
            {
                "role": "system",
                "content": "You score headlines and reply with one JSON object only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_completion_tokens": 900,
        "response_format": {"type": "json_object"},
    }
    if attempt.get("reasoning_effort"):
        body["reasoning_effort"] = attempt["reasoning_effort"]
    return requests.post(
        _CHAT_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=body,
        timeout=40,
    )


def _scored_report(parsed: dict, headlines: list[dict]) -> dict | None:
    scored = []
    values = []
    for index, item in enumerate(headlines, start=1):
        row = dict(item)
        if index in parsed["scores"]:
            row["score"] = parsed["scores"][index]
            values.append(row["score"])
        scored.append(row)
    if not values:
        return None
    return {
        "ok": True,
        "score": sum(values) / len(values),
        "summary": parsed.get("summary") or "",
        "drivers": parsed.get("drivers") or [],
        "headlines": scored,
    }


def _summarize(query: str, headlines: list[dict]) -> dict:
    key = (os.getenv("XAI_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "reason": "missing_key"}
    if time.time() < _BUSY_UNTIL.get(query, 0):
        return {"ok": False, "reason": "model_busy"}

    prompt = _prompt(query, headlines)
    saw_busy = False
    saw_auth = False
    for attempt in _MODELS:
        try:
            response = _post_grok(key, prompt, attempt)
        except requests.RequestException:
            saw_busy = True
            break
        if response.status_code == 200:
            try:
                parsed = _read_model_text(response)
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
        if response.status_code in (400, 404):
            continue
        if response.status_code in (429, 500, 503):
            saw_busy = True
            continue
        saw_busy = True

    if saw_auth:
        return {"ok": False, "reason": "bad_key"}
    if saw_busy:
        _BUSY_UNTIL[query] = time.time() + 60
        return {"ok": False, "reason": "model_busy"}
    return {"ok": False, "reason": "model_error"}


def sentiment_cached_at(query: str) -> float | None:
    """When the current score was stored, or None when this asset has no saved score."""
    cached = _SCORE_CACHE.get(query)
    if not cached:
        return None
    return cached[0]


def analyze_market_sentiment(query: str, enabled: bool, force: bool = False) -> dict:
    """Headlines plus a score when an xAI key is configured.

    A successful score is reused for one hour. A busy model is not cached,
    so the next look can try again. force skips that hour and asks again.
    """
    if force:
        _SCORE_CACHE.pop(query, None)
        _BUSY_UNTIL.pop(query, None)
    cached = _SCORE_CACHE.get(query)
    if enabled and not force and cached and time.time() - cached[0] < 3600:
        stored = cached[1]
        stored_rows = stored.get("headlines") or []
        if stored.get("ok") and stored_rows and all(row.get("score") is not None for row in stored_rows):
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
