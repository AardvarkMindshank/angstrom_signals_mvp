"""Which panels the chart shows, decided without touching the drawing library.

The price panel always shows, with volume below it. The other indicators, RSI
included (an icon since 13 Nov 2026, off unless picked), are chosen by the user. An indicator whose data is missing (a new
asset with too little history, say) is left out instead of drawing an empty panel.
"""

from __future__ import annotations

# key -> label shown on the toggle, where it is drawn, and the columns it needs
INDICATORS = {
    "sma200": {"label": "SMA 200", "where": "price", "needs": ("sma_200",)},
    "ichimoku": {"label": "Ichimoku cloud", "where": "price", "needs": ("ichi_span_a", "ichi_span_b")},
    "rsi": {"label": "RSI", "where": "panel", "needs": ("rsi",)},
    "macd": {"label": "MACD", "where": "panel", "needs": ("MACD_",), "prefix": True},
    "stoch": {"label": "Stochastic", "where": "panel", "needs": ("stoch_k",)},
    "stochrsi": {"label": "Stoch RSI", "where": "panel", "needs": ("stochrsi_k", "stochrsi_d")},
    "adx": {"label": "ADX", "where": "panel", "needs": ("adx",)},
    "obv": {"label": "OBV", "where": "panel", "needs": ("obv",)},
}

BASE_PANELS = ("volume",)
MAX_EXTRA_PANELS = 5
PRICE_SHARE = 0.5


def _has(columns, spec) -> bool:
    names = [str(name) for name in columns]
    for need in spec["needs"]:
        if spec.get("prefix"):
            if not any(name.startswith(need) for name in names):
                return False
        elif need not in names:
            return False
    return True


def available(columns) -> list[str]:
    """Indicator keys the data can draw, in a steady order."""
    return [key for key, spec in INDICATORS.items() if _has(columns, spec)]


# Curves that always run 0 to 100, so they can share one right-hand axis on the price panel.
BOUNDED = ("rsi", "stoch", "stochrsi", "adx")


def plan(selected, columns, overlay_curves: bool = False) -> dict:
    """overlays: drawn on the price panel. panels: lower panels, top to bottom.
    secondary: 0-100 curves drawn on the price panel's right-hand axis (only when overlay_curves).
    heights: row heights, price first. skipped: chosen but not drawable.
    MACD and OBV have no fixed range, so they always keep their own panel."""
    chosen = [key for key in INDICATORS if key in set(selected or ())]
    ok = set(available(columns))
    skipped = [key for key in chosen if key not in ok]
    drawable = [key for key in chosen if key in ok]
    overlays = [key for key in drawable if INDICATORS[key]["where"] == "price"]
    extra = [key for key in drawable if INDICATORS[key]["where"] == "panel"]
    if len(extra) > MAX_EXTRA_PANELS:
        skipped += extra[MAX_EXTRA_PANELS:]
        extra = extra[:MAX_EXTRA_PANELS]
    secondary = []
    if overlay_curves:
        secondary += [key for key in extra if key in BOUNDED]
        extra = [key for key in extra if key not in BOUNDED]
    panels = list(BASE_PANELS) + extra
    each = (1 - PRICE_SHARE) / len(panels)
    return {
        "overlays": overlays,
        "panels": panels,
        "secondary": secondary,
        "heights": [PRICE_SHARE] + [each] * len(panels),
        "skipped": skipped,
    }
