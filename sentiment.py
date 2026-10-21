"""
Market sentiment from recent headlines for the asset open on the chart.

Headlines come from Google News. A Gemini model turns them into a 0–100 score.
The score is not blended into the technical score.
"""

from __future__ import annotations

import html
import json
import os
import xml.etree.ElementTree as ET

import requests

_MODEL = "gemini-3.8-flash"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SignalsDashboard/1.0)"}


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


def gemini_ready() -> bool:
    """True when a Gemini key is available. Copies a Streamlit secret into the environment once."""
    if (os.getenv("GEMINI_API_KEY") or "").strip():
        return True
    try:
        import streamlit as st
        key = str(st.secrets["ai"]["gemini_api_key"]).strip()
    except Exception:
        return False
    if not key:
        return False
    os.environ["GEMINI_API_KEY"] = key
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


def _summarize(query: str, headlines: list[dict]) -> dict:
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "reason": "missing_key"}

    lines = []
    for index, item in enumerate(headlines, start=1):
        source = item.get("source") or "Unknown source"
        published = item.get("published") or ""
        lines.append(f"{index}. {item['title']} — {source} {published}".strip())
    prompt = (
        "Score market sentiment from these headlines only. "
        "This is research context, not a forecast or advice. "
        f"Asset search: {query}\n"
        "Headlines:\n"
        + "\n".join(lines)
        + "\n\nReturn JSON with score, summary, and drivers. "
        "score is 0 to 100: 0 is strongly bearish coverage, 50 is mixed or thin, "
        "100 is strongly bullish coverage. "
        "summary is two sentences about what the headlines say. "
        "drivers is up to 3 short phrases. "
        "Do not add facts that are not in the headlines. Stay near 50 when coverage is mixed."
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=body,
        timeout=30,
    )
    if response.status_code != 200:
        detail = " ".join((response.text or "").split())[:240]
        return {"ok": False, "reason": "model_error", "detail": f"HTTP {response.status_code} {detail}"}

    parts = (
        ((response.json().get("candidates") or [{}])[0].get("content") or {}).get("parts")
        or []
    )
    texts = [part.get("text") for part in parts if isinstance(part, dict) and part.get("text")]
    if not texts:
        return {"ok": False, "reason": "model_error", "detail": "The model returned no text."}
    parsed = _parse_model_json(texts[-1])
    score = _clamp_score(parsed.get("score"))
    if score is None:
        return {"ok": False, "reason": "model_error", "detail": "The model did not return a score."}
    summary = " ".join(str(parsed.get("summary") or "").split())
    drivers = []
    for item in parsed.get("drivers") or []:
        text = " ".join(str(item).split())
        if text:
            drivers.append(text[:160])
        if len(drivers) == 3:
            break
    return {"ok": True, "score": score, "summary": summary, "drivers": drivers}


def analyze_market_sentiment(query: str, enabled: bool) -> dict:
    """Headlines plus a score when a Gemini key is configured."""
    try:
        headlines = fetch_headlines(query)
    except Exception as exc:
        return {"ok": False, "reason": "headlines_error", "detail": str(exc), "headlines": []}
    if not headlines:
        return {"ok": False, "reason": "no_headlines", "headlines": []}
    if not enabled:
        return {"ok": False, "reason": "missing_key", "headlines": headlines}
    try:
        summary = _summarize(query, headlines)
    except Exception as exc:
        summary = {"ok": False, "reason": "model_error", "detail": str(exc)}
    summary["headlines"] = headlines
    return summary
