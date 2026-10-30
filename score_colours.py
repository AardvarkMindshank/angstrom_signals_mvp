"""One graded colour scale for 0-100 scores and sentiment, used by the site and the emails.

Five steps, matching the labels in the help guide:
    70 and up   strongly positive   deep green
    53 to 69    positive            soft green
    47 to 52    mixed               amber
    30 to 46    negative            soft red
    below 30    strongly negative   deep red
Each step gives (text colour, badge background, arrow, bar colour). Text colours stay dark enough
to read on a white page, so the same text colour works with or without the badge.
"""

from __future__ import annotations

STRONG_HIGH = 70.0
HIGH = 53.0
LOW = 47.0
STRONG_LOW = 30.0

STEPS = {
    "strong_up": ("#14532d", "#86efac", "↑", "#15803d"),
    "up": ("#15803d", "#dcfce7", "↑", "#4ade80"),
    "mixed": ("#b45309", "#fef3c7", "→", "#f59e0b"),
    "down": ("#b91c1c", "#fee2e2", "↓", "#f87171"),
    "strong_down": ("#7f1d1d", "#fca5a5", "↓", "#b91c1c"),
    "none": ("#6b7280", "#f3f4f6", "—", "#6b7280"),
}


def step(score) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "none"
    if value != value:
        return "none"
    if value >= STRONG_HIGH:
        return "strong_up"
    if value >= HIGH:
        return "up"
    if value >= LOW:
        return "mixed"
    if value >= STRONG_LOW:
        return "down"
    return "strong_down"


def score_tone(score) -> tuple[str, str, str, str]:
    """(text colour, badge background, arrow, bar colour) for a 0-100 reading."""
    return STEPS[step(score)]


def tone_js() -> str:
    """The same scale as a JavaScript function body for page components: returns {bg, fg, arrow}."""
    rows = []
    for limit, name in ((STRONG_HIGH, "strong_up"), (HIGH, "up"), (LOW, "mixed"), (STRONG_LOW, "down")):
        fg, bg, arrow, _ = STEPS[name]
        rows.append(f'if (number >= {limit:g}) return {{ bg: "{bg}", fg: "{fg}", arrow: "{arrow}" }};')
    fg, bg, arrow, _ = STEPS["strong_down"]
    rows.append(f'return {{ bg: "{bg}", fg: "{fg}", arrow: "{arrow}" }};')
    return "\n    ".join(rows)
