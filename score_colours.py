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


# ----------------------------------------------------------------------------- signals v2 readings (-100..100)
# Same five colours, on the bands signals_v2 uses for its words: 50 and up strong, 20 and up mild,
# within 20 of zero neutral.

READING_STRONG = 50.0
READING_MILD = 20.0


def reading_step(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "none"
    if number != number:
        return "none"
    if number >= READING_STRONG:
        return "strong_up"
    if number >= READING_MILD:
        return "up"
    if number > -READING_MILD:
        return "mixed"
    if number > -READING_STRONG:
        return "down"
    return "strong_down"


def reading_tone(value) -> tuple[str, str, str, str]:
    """(text colour, badge background, arrow, bar colour) for a -100..100 signals v2 reading."""
    return STEPS[reading_step(value)]


# ----------------------------------------------------------------------------- sentiment shown on -100..+100
# Sentiment is scored and stored on 0..100 (50 = mixed); the site and emails show it on the same
# -100..+100 scale as the technical readings (0 = mixed), with the same five colours and bands.

def sentiment_value(score) -> float | None:
    """A stored 0..100 sentiment score as shown: -100..+100. None when missing."""
    try:
        number = float(score)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return max(-100.0, min(100.0, number * 2.0 - 100.0))


def sentiment_stored(shown) -> float | None:
    """The inverse: a -100..+100 value someone typed, as the 0..100 number that is stored."""
    try:
        number = float(shown)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return max(0.0, min(100.0, (number + 100.0) / 2.0))


def sentiment_text(score) -> str:
    """'+32', '-8', '0' or a dash, from a stored 0..100 score."""
    value = sentiment_value(score)
    if value is None:
        return "—"
    shown = int(round(value))
    return f"{shown:+d}" if shown else "0"


def sentiment_spread(points) -> float | None:
    """A spread measured in stored points, on the shown scale (twice as wide)."""
    try:
        return float(points) * 2.0
    except (TypeError, ValueError):
        return None


def sentiment_tone(score) -> tuple[str, str, str, str]:
    """Colours for a stored 0..100 sentiment score, on the -100..+100 reading bands."""
    return reading_tone(sentiment_value(score))


def sentiment_tone_js() -> str:
    """JavaScript body for page components: `number` is a stored 0..100 score; returns
    {bg, fg, arrow, text} on the -100..+100 scale and bands."""
    rows = ["const v = Math.max(-100, Math.min(100, number * 2 - 100));",
            "const r = Math.round(v);",
            'const text = r > 0 ? "+" + r : String(r);']
    for limit, name in ((READING_STRONG, "strong_up"), (READING_MILD, "up"), (-READING_MILD + 0.0001, "mixed"),
                        (-READING_STRONG + 0.0001, "down")):
        fg, bg, arrow, _ = STEPS[name]
        rows.append(f'if (v >= {limit:g}) return {{ bg: "{bg}", fg: "{fg}", arrow: "{arrow}", text }};')
    fg, bg, arrow, _ = STEPS["strong_down"]
    rows.append(f'return {{ bg: "{bg}", fg: "{fg}", arrow: "{arrow}", text }};')
    return "\n    ".join(rows)
