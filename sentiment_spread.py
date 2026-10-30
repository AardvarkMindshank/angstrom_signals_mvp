"""How much the articles behind a sentiment score agree: a small dot strip and one word.

Each article was scored 0 to 100. The strip puts one dot per article on a 0-100 line, coloured on
the site's five-step scale, with the average marked. The word comes from the spread (standard
deviation): agree under 10 points, mixed 10 to 20, split above 20.
"""

from __future__ import annotations

import html
import math

from score_colours import score_tone

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
    "agree": "they mostly read the same way",
    "mixed": "they lean different ways",
    "split": "they disagree strongly; the average hides two camps",
}


def spread_html(report: dict | None, average: float | None = None, width: int = 190) -> str:
    """The strip and its word, ready to sit beside the score. Empty with fewer than two scored articles."""
    values = article_scores(report)
    word, sd = spread_word(values)
    if not word:
        return ""
    mean = average if average is not None else sum(values) / len(values)
    height, pad = 28, 5

    def x(value: float) -> float:
        return pad + (width - 2 * pad) * value / 100.0

    # Dots close together are stacked on three rows so each one stays visible.
    rows_y = (14, 7, 21)
    placed: list[tuple[float, int]] = []
    dots = []
    for value in sorted(values):
        cx = x(value)
        level = 0
        while any(abs(cx - px) < 6 and pl == level for px, pl in placed) and level < 2:
            level += 1
        placed.append((cx, level))
        colour = score_tone(value)[3]
        dots.append(
            f"<circle cx='{cx:.1f}' cy='{rows_y[level]}' r='3.6' fill='{colour}' fill-opacity='0.85' "
            "stroke='#ffffff' stroke-width='0.6'/>"
        )
    mark = x(mean)
    svg = (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' aria-hidden='true' "
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
    readings = sum(
        1 for group in (report or {}).get("gauges") or [] if isinstance(group, dict)
        for item in group.get("items") or [] if isinstance(item, dict) and item.get("score") is not None
    )
    what = f"{len(values) - readings} news articles and {readings} public readings" if readings else f"{len(values)} articles"
    noun = "sources" if readings else "articles"
    title = (
        f"{what}, each scored 0 to 100. Each dot is one; the marker is the average "
        f"({mean:.0f}). Spread ±{sd:.0f} points: {word}, {_MEANING[word]}."
    )
    colours = {"agree": ("#15803d", "#dcfce7"), "mixed": ("#b45309", "#fef3c7"), "split": ("#b91c1c", "#fee2e2")}
    fg, bg = colours[word]
    label = (
        f"<span style='display:inline-block;padding:1px 7px;border-radius:999px;background:{bg};color:{fg};"
        f"font-size:0.75rem;font-weight:700;'>{word}</span>"
    )
    return (
        f"<span class='sentiment-spread' title='{html.escape(title, quote=True)}' "
        "style='display:inline-flex;align-items:center;gap:8px;cursor:help;'>"
        f"{svg}<span style='display:inline-flex;flex-direction:column;align-items:flex-start;line-height:1.2;'>"
        f"{label}<span style='font-size:0.7rem;color:var(--ang-muted,#6b7280);'>{len(values)} {noun}</span>"
        "</span></span>"
    )
