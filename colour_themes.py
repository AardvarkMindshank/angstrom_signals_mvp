"""Ready-made colour themes for the UI Colours settings, and the little picture that shows each one.

Every theme sets all 14 colours: a day and a night value for each of seven parts of the page.
"""
from __future__ import annotations

import html

PARTS = ("page", "heading", "section", "hover", "sidebar", "social", "border")
KEYS = tuple(f"{part}_{mode}" for part in PARTS for mode in ("day", "night"))


def _theme(day: tuple, night: tuple) -> dict:
    """Seven colours for day and seven for night, in the order of PARTS."""
    out = {}
    for part, d, n in zip(PARTS, day, night):
        out[f"{part}_day"] = d
        out[f"{part}_night"] = n
    return out


#            page       heading    section    hover      sidebar    social     border
THEMES = {
    "Default": _theme(
        ("#d6e8f8", "#ffffff", "#ffffff", "#f3f4f6", "#ffffff", "#ffffff", "#e5e7eb"),
        ("#0e1117", "#262730", "#262730", "#31333f", "#16181f", "#1c1f27", "#000000"),
    ),
    "Slate": _theme(
        ("#e2e8f0", "#f8fafc", "#ffffff", "#e2e8f0", "#f1f5f9", "#f8fafc", "#cbd5e1"),
        ("#0f172a", "#1e293b", "#1e293b", "#334155", "#0b1220", "#172033", "#475569"),
    ),
    "High contrast": _theme(
        ("#ffffff", "#f3f4f6", "#ffffff", "#e5e7eb", "#f9fafb", "#ffffff", "#111827"),
        ("#000000", "#1a1a1a", "#0d0d0d", "#2b2b2b", "#000000", "#0d0d0d", "#e5e7eb"),
    ),
    "Warm paper": _theme(
        ("#f5efe3", "#fbf7ee", "#fffdf8", "#efe6d3", "#f0e8d8", "#fbf7ee", "#d8ccb4"),
        ("#1c1814", "#2a241d", "#26201a", "#3a3228", "#16120e", "#211c16", "#5a4d3c"),
    ),
    "Midnight": _theme(
        ("#dbe7fb", "#f4f8ff", "#ffffff", "#e3ecfb", "#eef3fd", "#f4f8ff", "#b6c8ec"),
        ("#070b1a", "#111a3a", "#0e1530", "#1b2650", "#050816", "#0b1228", "#2f3f7a"),
    ),
    "Forest": _theme(
        ("#e3efe5", "#f6fbf6", "#ffffff", "#dcebdf", "#edf5ee", "#f6fbf6", "#bcd3c0"),
        ("#0c1410", "#16241c", "#12201a", "#1f3328", "#09100c", "#101b15", "#3a5c48"),
    ),
    "Mono": _theme(
        ("#eeeeee", "#ffffff", "#fafafa", "#e0e0e0", "#f5f5f5", "#ffffff", "#bdbdbd"),
        ("#121212", "#1e1e1e", "#1a1a1a", "#2c2c2c", "#0c0c0c", "#181818", "#4d4d4d"),
    ),
}


def clean_set(value, defaults: dict) -> dict:
    """value as a full set of 14 valid #rrggbb colours. Anything missing or odd falls back to defaults."""
    source = value if isinstance(value, dict) else {}
    out = {}
    for key in KEYS:
        text = str(source.get(key) or "").strip().lower()
        ok = len(text) == 7 and text.startswith("#") and all(ch in "0123456789abcdef" for ch in text[1:])
        out[key] = text if ok else defaults[key]
    return out


def swatch_html(colours: dict) -> str:
    """A small picture of the page in day (left) and night (right), drawn with the given colours."""
    def half(mode: str) -> str:
        c = {part: html.escape(str(colours.get(f"{part}_{mode}", "#888888")), quote=True) for part in PARTS}
        edge = f"1px solid {c['border']}"
        return (
            f"<div style='flex:1;background:{c['page']};padding:5px;display:flex;gap:4px;'>"
            f"<div style='width:20%;background:{c['sidebar']};border:{edge};border-radius:3px;'></div>"
            "<div style='flex:1;display:flex;flex-direction:column;gap:3px;'>"
            f"<div style='height:9px;background:{c['heading']};border:{edge};border-radius:3px;'></div>"
            f"<div style='flex:1;background:{c['section']};border:{edge};border-radius:3px;display:flex;gap:3px;padding:3px;'>"
            f"<div style='flex:1;background:{c['hover']};border-radius:2px;'></div>"
            f"<div style='flex:1;background:{c['social']};border-radius:2px;'></div>"
            "</div></div></div>"
        )

    return (
        "<div style='display:flex;height:62px;border:1px solid #8a8f98;border-radius:8px;overflow:hidden;margin-bottom:4px;'>"
        + half("day") + half("night") + "</div>"
    )
