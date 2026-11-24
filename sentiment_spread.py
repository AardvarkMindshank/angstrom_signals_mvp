"""How much the articles behind a sentiment score agree: a small dot strip and one word.

Each article is scored and stored on 0 to 100 and shown on -100 to +100 (0 = mixed), like every score
on the site. The strip puts one dot per article on that line, coloured on the site's five-step scale,
with the average marked. The word comes from the spread (standard deviation, in stored points): agree
under 10 (under 20 on the shown scale), mixed 10 to 20 (20 to 40 shown), split above 20 (above 40 shown).
"""

from __future__ import annotations

from i18n import mark, t

import html
import math

from score_colours import sentiment_text, sentiment_tone

AGREE_BELOW = 10.0
SPLIT_ABOVE = 20.0


def article_scores(report: dict | None) -> list[float]:
    """Every scored item: the articles, and for a market also its public readings."""
    values = []
    rows = list((report or {}).get("headlines") or [])
    for group in (report or {}).get("gauges") or []:
        rows += list((group or {}).get("items") or []) if isinstance(group, dict) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get("score"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            values.append(max(0.0, min(100.0, value)))
    return values


def _when(row: dict) -> str:
    """A row's date as "23 Nov 2026", or ""."""
    from datetime import datetime
    from email.utils import parsedate_to_datetime

    raw = str(row.get("published_at") or row.get("published") or "").strip()
    if not raw:
        return ""
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return ""
    return f"{when.day} {when.strftime('%b %Y')}"


def scored_rows(report: dict | None) -> list[tuple[float, str]]:
    """(score, what it is) for each dot: an article's title, or a reading's name and value; then its date and source
    (24 Nov 2026: hovering a dot names the article behind it)."""
    out = []
    rows = list((report or {}).get("headlines") or [])
    for group in (report or {}).get("gauges") or []:
        rows += list((group or {}).get("items") or []) if isinstance(group, dict) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get("score"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        if row.get("title"):
            name = str(row["title"])
        else:
            name = t(str(row.get("name") or "")) + (f", {row['value']}" if row.get("value") else "")
        meta = " · ".join(part for part in (_when(row), str(row.get("source") or "").strip()) if part)
        out.append((max(0.0, min(100.0, value)), name + (f"\n{meta}" if meta else "")))
    return out


def spread_word(values: list[float]) -> tuple[str, float]:
    """("agree" | "mixed" | "split", standard deviation). Needs two or more articles."""
    if len(values) < 2:
        return "", 0.0
    mean = sum(values) / len(values)
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    if sd < AGREE_BELOW:
        return "agree", sd
    if sd <= SPLIT_ABOVE:
        return "mixed", sd
    return "split", sd


_MEANING = {
    "agree": mark("they mostly read the same way"),
    "mixed": mark("they lean different ways"),
    "split": mark("they disagree strongly; the average hides two camps"),
}
_WORD = {"agree": mark("agree"), "mixed": mark("mixed"), "split": mark("split")}


def coverage_badge(report: dict | None) -> str:
    """A small warning when the score rests on thin news: few independent events or few publishers.
    Empty when coverage is fine or was not recorded."""
    cover = (report or {}).get("coverage") if isinstance(report, dict) else None
    if not isinstance(cover, dict) or cover.get("level") != "thin":
        return ""
    events, sources = int(cover.get("events") or 0), int(cover.get("sources") or 0)
    hint = t("Based on only {events} separate news stories from {sources} publishers (repeats of the same story "
             "count once). Treat this score as a weak reading.", events=events, sources=sources)
    return (f"<span title='{html.escape(hint, quote=True)}' style='display:inline-block;padding:1px 7px;"
            "border-radius:999px;background:#fef3c7;color:#92400e;font-size:0.75rem;font-weight:700;cursor:help;'>"
            + html.escape(t("⚠️ thin news")) + "</span>")


def spread_html(report: dict | None, average: float | None = None, width: int = 190) -> str:
    """The strip and its word, ready to sit beside the score, plus a thin-news warning when it applies.
    Only the warning (or nothing) with fewer than two scored articles."""
    values = article_scores(report)
    word, sd = spread_word(values)
    thin = coverage_badge(report)
    if not word:
        return thin
    mean = average if average is not None else sum(values) / len(values)
    height, pad = 28, 5
    readings = sum(
        1 for group in (report or {}).get("gauges") or [] if isinstance(group, dict)
        for item in group.get("items") or [] if isinstance(item, dict) and item.get("score") is not None
    )
    what = (t("{n} news articles and {m} public readings", n=len(values) - readings, m=readings) if readings
            else t("{n} articles", n=len(values)))
    count = t("{n} sources", n=len(values)) if readings else t("{n} articles", n=len(values))
    title = t("{what}, each scored from -100 (very negative) to +100 (very positive). Each dot is one; the marker is "
              "the average ({avg}). Spread ±{sd:.0f} points: {word}, {meaning}.", what=what, avg=sentiment_text(mean),
              sd=sd * 2, word=t(_WORD[word]), meaning=t(_MEANING[word]))

    def x(value: float) -> float:
        return pad + (width - 2 * pad) * value / 100.0

    # Dots close together are stacked on three rows so each one stays visible. Hovering a dot shows the article or
    # reading behind it, its date and source and its score, then the strip's explanation.
    rows_y = (14, 7, 21)
    placed: list[tuple[float, int]] = []
    dots = []
    for value, label in sorted(scored_rows(report), key=lambda pair: pair[0]):
        cx = x(value)
        level = 0
        while any(abs(cx - px) < 6 and pl == level for px, pl in placed) and level < 2:
            level += 1
        placed.append((cx, level))
        colour = sentiment_tone(value)[3]
        tip = html.escape(f"{label}\n{t('Score')}: {sentiment_text(value)}\n\n{title}")
        dots.append(
            f"<g style='cursor:help;'><title>{tip}</title>"
            f"<circle cx='{cx:.1f}' cy='{rows_y[level]}' r='3.6' fill='{colour}' fill-opacity='0.85' "
            "stroke='#ffffff' stroke-width='0.6'/>"
            f"<circle cx='{cx:.1f}' cy='{rows_y[level]}' r='5' fill='{colour}' fill-opacity='0' "
            "pointer-events='all'/></g>"
        )
    mark = x(mean)
    svg = (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
        "style='display:block;'>"
        f"<line x1='{pad}' y1='14' x2='{width - pad}' y2='14' stroke='var(--ang-track,#e5e7eb)' stroke-width='2' "
        "stroke-linecap='round'/>"
        f"<line x1='{x(50):.1f}' y1='9' x2='{x(50):.1f}' y2='19' stroke='var(--ang-muted,#9ca3af)' "
        "stroke-width='1' opacity='0.5'/>"
        + "".join(dots)
        + f"<path d='M{mark - 4:.1f},1 L{mark + 4:.1f},1 L{mark:.1f},7 Z' fill='var(--ang-text,#111827)'/>"
        f"<line x1='{mark:.1f}' y1='7' x2='{mark:.1f}' y2='{height - 1}' stroke='var(--ang-text,#111827)' "
        "stroke-width='1.2' opacity='0.7'/>"
        "</svg>"
    )
    colours = {"agree": ("#15803d", "#dcfce7"), "mixed": ("#b45309", "#fef3c7"), "split": ("#b91c1c", "#fee2e2")}
    fg, bg = colours[word]
    label = (
        f"<span style='display:inline-block;padding:1px 7px;border-radius:999px;background:{bg};color:{fg};"
        f"font-size:0.75rem;font-weight:700;'>{html.escape(t(_WORD[word]))}</span>"
    )
    return (
        f"<span class='sentiment-spread' title='{html.escape(title, quote=True)}' "
        "style='display:inline-flex;align-items:center;gap:8px;cursor:help;'>"
        f"{svg}<span style='display:inline-flex;flex-direction:column;align-items:flex-start;line-height:1.2;'>"
        f"{label}<span style='font-size:0.7rem;color:var(--ang-muted,#6b7280);'>{html.escape(count)}</span>"
        "</span></span>"
        + (f"<span style='margin-left:8px;'>{thin}</span>" if thin else "")
    )
