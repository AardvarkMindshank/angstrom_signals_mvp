"""Clean a Google News headline list before it is scored.

Pure functions (no network), so every rule is tested on its own. In order:

1. Promotional junk is dropped (presales, airdrops, price-prediction pieces, paid press-release wires).
2. Freshness: undated, stale (older than MAX_AGE_DAYS) and future-dated items are dropped.
3. Relevance (asset searches only): the headline must name the asset or its ticker.
4. Duplicates: the same headline, a near-copy, or another outlet's report of the same event counts once.
   The kept item notes how many other outlets carried it ("also_reported").
5. Diversity: at most PER_SOURCE_MAX items from one publisher.

Nothing here changes how a score is calculated: each remaining headline is still scored on its own and
averaged. The rules only decide which headlines go in. Thresholds are plain, stated choices.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

MAX_AGE_DAYS = 7
FUTURE_SLACK_SECONDS = 3600          # a feed clock a little ahead is tolerated
PER_SOURCE_MAX = 2
SAME_EVENT_SIMILARITY = 0.5          # share of content words two titles have in common (Jaccard)
COVERAGE_OK_EVENTS = 4               # a reading from fewer independent events, or
COVERAGE_OK_SOURCES = 3              # fewer publishers, is shown as based on thin news

SKIP_WORDS = (
    "presale", "pre-sale", "airdrop", "price prediction", "what will", "be worth", "could reach",
    "openpr", "einpresswire", "prediction market", "live chart", "stock forecast",
    # automated fund-filing notices ("X LLC increases stake in ..."): no news content
    "increases stake", "decreases stake", "raises stake", "lowers stake", "trims stake", "boosts stake",
    "cuts stake", "holdings increased by", "holdings decreased by", "holdings trimmed by", "holdings lifted by",
)
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "at", "by", "with", "from", "as", "is",
    "are", "was", "were", "be", "its", "it", "this", "that", "after", "amid", "over", "into", "new", "says",
    "said", "report", "reports", "update", "today", "here", "why", "how", "what", "will", "has", "have",
    "stock", "stocks", "shares", "crypto", "price", "news", "vs", "s",
}
_NAME_SUFFIXES = {
    "inc", "inc.", "corp", "corp.", "corporation", "co", "co.", "company", "ltd", "ltd.", "plc", "holdings",
    "group", "sa", "nv", "ag", "class", "a", "b", "c", "the", "limited", "incorporated", "&",
}
_GENERIC_FIRST = {
    "bank", "first", "united", "american", "general", "international", "global", "digital", "the", "new",
    "national", "royal", "advanced", "applied", "western", "eastern", "north", "south", "meta",
}


def _norm(text) -> str:
    return " ".join(re.sub(r"[^a-z0-9$%. ]+", " ", str(text or "").lower()).split())


def article_id(item: dict) -> str:
    """A stable id for one article: its cleaned title and publisher. Same story, same id."""
    raw = f"{_norm(item.get('title'))}|{_norm(item.get('source'))}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def published_ts(value) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError, IndexError, OverflowError, OSError):
        return None


def content_words(title) -> frozenset:
    return frozenset(w for w in _norm(title).replace(".", " ").split() if w not in _STOP and len(w) > 1)


def same_event(a: frozenset, b: frozenset) -> bool:
    """Two titles about the same thing: most content words shared, or one is a near-subset of the other."""
    if not a or not b:
        return False
    shared = len(a & b)
    if shared / len(a | b) >= SAME_EVENT_SIMILARITY:
        return True
    small = min(len(a), len(b))
    return small >= 4 and shared / small >= 0.8


def asset_terms(query: str) -> dict:
    """What a relevant headline must mention, from a search built by sentiment.sentiment_query:
    '<name> [TICKER] cryptocurrency|stock'. Empty for anything else (market searches)."""
    words = str(query or "").split()
    if not words or words[-1] not in ("cryptocurrency", "stock"):
        return {}
    words = words[:-1]
    ticker = ""
    if len(words) > 1 and words[-1].isupper() and len(words[-1]) <= 6:
        ticker = words.pop()
    name_words = [w for w in words if w.lower().strip(",.") not in _NAME_SUFFIXES]
    if not name_words:
        name_words = words
    name = " ".join(name_words).strip(",. ")
    names = {name.lower()} if name else set()
    first = name_words[0].strip(",.") if name_words else ""
    aliases = []
    # The first word of a longer name ("Microsoft" for Microsoft Corporation) also counts, but only
    # with its capital letter, so "Near Protocol" is not matched by "stocks near highs".
    if len(name_words) > 1 and len(first) >= 4 and first.lower() not in _GENERIC_FIRST and first[:1].isupper():
        aliases.append(first)
    if not ticker and len(words) == 1 and words[0].isupper() and len(words[0]) <= 6:
        ticker = words[0]      # a stock listed under its ticker only
    return {"names": sorted(names), "aliases": aliases, "ticker": ticker}


def is_relevant(title: str, terms: dict) -> bool:
    if not terms:
        return True
    lower = f" {_norm(title)} "
    for name in terms.get("names") or []:
        if f" {_norm(name)} " in lower:
            return True
    for alias in terms.get("aliases") or []:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![a-z0-9])", str(title or "")):
            return True
    ticker = terms.get("ticker") or ""
    if len(ticker) >= 2 and re.search(rf"(?<![A-Za-z0-9])\$?{re.escape(ticker)}(?![A-Za-z0-9])", str(title or "")):
        return True
    return False


def clean_headlines(items: list[dict], now: float, terms: dict | None = None, limit: int = 8) -> tuple[list[dict], dict]:
    """(kept headlines newest first, counts of what was dropped and why). Each kept item gets an "id",
    and "also_reported" / "also_sources" when other outlets carried the same event."""
    stats = {"candidates": len(items or []), "junk": 0, "stale": 0, "undated": 0, "irrelevant": 0,
             "duplicates": 0, "same_source_cap": 0}
    fresh = []
    oldest = now - MAX_AGE_DAYS * 86400
    for item in items or []:
        title = str(item.get("title") or "").strip()
        blob = f"{title} {item.get('source') or ''}".lower()
        if not title or any(word in blob for word in SKIP_WORDS):
            stats["junk"] += 1
            continue
        stamp = published_ts(item.get("published"))
        if stamp is None:
            stats["undated"] += 1
            continue
        if stamp < oldest or stamp > now + FUTURE_SLACK_SECONDS:
            stats["stale"] += 1
            continue
        if not is_relevant(title, terms or {}):
            stats["irrelevant"] += 1
            continue
        fresh.append((stamp, item))
    fresh.sort(key=lambda pair: -pair[0])

    events = []          # [kept item, its words]
    for stamp, item in fresh:
        words = content_words(item.get("title"))
        match = next((event for event in events if same_event(words, event[1])), None)
        if match is not None:
            stats["duplicates"] += 1
            kept = match[0]
            kept["also_reported"] = kept.get("also_reported", 0) + 1
            source = str(item.get("source") or "").strip()
            if source and source != kept.get("source") and source not in kept.setdefault("also_sources", []):
                kept["also_sources"].append(source)
            continue
        row = dict(item)
        row["id"] = article_id(row)
        row["published_at"] = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
        events.append([row, words])

    kept, per_source = [], {}
    for row, _words in events:
        source = str(row.get("source") or "").strip().lower() or "unknown"
        if per_source.get(source, 0) >= PER_SOURCE_MAX:
            stats["same_source_cap"] += 1
            continue
        per_source[source] = per_source.get(source, 0) + 1
        kept.append(row)
        if len(kept) >= limit:
            break
    stats.update(coverage(kept))
    return kept, stats


def coverage(headlines: list[dict]) -> dict:
    """How much independent news a reading rests on. "thin" readings are shown with a warning."""
    events = len(headlines or [])
    sources = len({str(h.get("source") or "").strip().lower() for h in headlines or [] if h.get("source")})
    if events == 0:
        level = "none"
    elif events >= COVERAGE_OK_EVENTS and sources >= COVERAGE_OK_SOURCES:
        level = "ok"
    else:
        level = "thin"
    return {"events": events, "sources": sources, "level": level}
