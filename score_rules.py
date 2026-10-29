"""The scoring rules in plain words, for the info popup next to the weight sliders.

scoring.py is what actually scores. This file only describes it, and
tests/test_score_rules.py runs the real scoring on extreme cases and fails if the
numbers written here stop matching, so the popup cannot drift from the maths.
"""

from __future__ import annotations

START = 50
LOW, HIGH = 0, 100

# weight: the key the slider uses. rows: (when, points at weight 1). max_points: the most it can add or take away.
RULES = [
    {
        "weight": "rsi", "name": "RSI (14)", "max_points": 8,
        "measures": "How stretched recent price moves are. Low means sold hard, high means bought hard.",
        "rows": [("Below 35 (oversold)", 8), ("35 to 45", 4), ("45 to 55", 0), ("55 to 65", -4), ("Above 65 (overbought)", -8)],
    },
    {
        "weight": "stochastic", "name": "Stochastic (14, 3)", "max_points": 5,
        "measures": "Where price closed inside its recent high-to-low range.",
        "rows": [("Below 20 (oversold)", 5), ("20 to 80", 0), ("Above 80 (overbought)", -5)],
    },
    {
        "weight": "sma", "name": "Moving averages", "max_points": 12,
        "measures": "Price against its average of the last 20, 50 and 200 days. Each average counts on its own.",
        "rows": [("Above each average", 4), ("Below each average", -4)],
    },
    {
        "weight": "adx", "name": "ADX trend", "max_points": 4,
        "measures": "How strong a trend is, whichever way it runs. Direction comes from price against the 50-day average.",
        "rows": [("ADX 25 or more, price above the 50-day", 4), ("ADX 25 or more, price below the 50-day", -4), ("ADX under 25", 0)],
    },
    {
        "weight": "macd", "name": "MACD", "max_points": 9,
        "measures": "Whether short-term momentum is rising or falling against longer-term momentum.",
        "rows": [
            ("MACD line above / below zero", 4), ("MACD line above / below its signal line", 3),
            ("Histogram positive / negative", 2),
        ],
    },
    {
        "weight": "ichimoku", "name": "Ichimoku cloud", "max_points": 8,
        "measures": "Price against the cloud, a band built from highs and lows over 9, 26 and 52 days.",
        "rows": [("Price above / below the cloud (inside scores 0)", 5), ("Tenkan above / below Kijun", 3)],
    },
    {
        "weight": "bb", "name": "Bollinger Bands (20, 2)", "max_points": 4,
        "measures": "Where price sits between the lower and upper band.",
        "rows": [("Bottom fifth of the bands", 4), ("Middle", 0), ("Top fifth of the bands", -4)],
    },
    {
        "weight": "volume", "name": "Volume", "max_points": 3,
        "measures": "Only counts when volume is at least 1.3 times its 20-day average.",
        "rows": [("Heavy volume on an up day", 3), ("Heavy volume on a down day", -3), ("Ordinary volume", 0)],
    },
    {
        "weight": "obv", "name": "On-balance volume", "max_points": 3,
        "measures": "Whether volume has been flowing into or out of the asset, against its own 20-day average.",
        "rows": [("OBV above its average", 3), ("OBV below its average", -3)],
    },
    {
        "weight": "performance", "name": "Performance", "max_points": 4,
        "measures": "The 7-day price change. Each 1% moves the score 0.4 points, up to 4 either way.",
        "rows": [("+10% or more over 7 days", 4), ("+5%", 2), ("-5%", -2), ("-10% or less", -4)],
    },
]

# Lowest score in each band, highest band first.
BANDS = [
    (70, "Strongly positive reading"), (60, "Positive reading"), (53, "Slightly positive"),
    (47, "Mixed"), (40, "Slightly negative"), (30, "Negative reading"), (0, "Strongly negative reading"),
]

HOW_IT_ADDS_UP = (
    f"Every score starts at {START}. Each indicator adds or takes away points as listed. "
    f"A weight multiplies that indicator's points: 1 is normal, 2 doubles them, 0 switches it off. "
    f"The total is held between {LOW} and {HIGH}."
)

CONFLUENCE = (
    "Confluence counts the indicators pushing the score up minus those pushing it down. "
    "It shows how much they agree, not how strong the signal is."
)

HONEST_NOTE = (
    "This score describes current conditions. It is not a forecast. In our own backtests over five years "
    "on Bitcoin, Ethereum, Apple and Microsoft, the score did not reliably predict later price moves."
)


def weighted_rows(weights: dict | None = None) -> list[dict]:
    """One row per indicator with the user's weight and the points that weight gives."""
    out = []
    for rule in RULES:
        try:
            weight = float((weights or {}).get(rule["weight"], 1.0))
        except (TypeError, ValueError):
            weight = 1.0
        points = [(when, round(pts * weight, 2)) for when, pts in rule["rows"]]
        out.append({
            "name": rule["name"], "measures": rule["measures"], "weight": weight,
            "max_points": round(rule["max_points"] * weight, 2), "rows": points,
        })
    return out


def band_lines() -> list[str]:
    lines = []
    upper = None
    for low, label in BANDS:
        span = f"{low} or more" if upper is None else f"{low} to {upper - 1}" if low else f"under {upper}"
        lines.append(f"{span}: {label}")
        upper = low
    return lines
