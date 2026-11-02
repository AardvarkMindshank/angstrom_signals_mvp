"""HTML pieces for signals v2 in the app: table cells, the asset card, the breakdown and the explainer.

Pure functions (no Streamlit), so they can be tested anywhere. Colours come from score_colours.reading_tone,
the same five colours the site already uses. Every number shown is on -100..+100: positive means up
(above the longer averages, stretched up, volume backing rises). These are descriptions, not forecasts.
"""

from __future__ import annotations

import html

import signals_v2 as v2
from score_colours import reading_tone

BADGES = {
    "unvalidated": ("Not validated", "#6b7280", "#f3f4f6",
                    "Describes the market. Not shown to predict price moves."),
    "validated_size": ("Tested: size only", "#1e40af", "#dbeafe",
                       "Tested once on held-back data: a guide to how big moves may be, never their direction."),
}


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def signed(value) -> str:
    """A reading as +62 / -5. Accepts floats too (a table column with a missing value turns ints into floats)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if number != number:
        return "—"
    return f"{int(round(number)):+d}"


def row_fields(frame, kind: str, now=None) -> dict:
    """Everything a watchlist row needs: the v2 readings (last finished bar) and the live display figures
    (price, today's move, RSI and so on from the latest row, as before)."""
    result = v2.score(frame, kind, now)
    out = dict(v2.flat_fields(result))
    out["signals"] = result
    out["label"] = "" if result.get("status") == "ok" else "No data"
    out["reasons"] = [] if result.get("status") == "ok" else [result.get("message") or "Not enough data yet"]
    trend = (result.get("clusters") or {}).get("trend") or {}
    out["trend_parts"] = {v2.COMPONENT_NAMES[k]: info.get("percent")
                          for k, info in (trend.get("components") or {}).items() if info.get("percent") is not None}
    if frame is None or len(frame) == 0:
        return out
    last = frame.iloc[-1]

    def num(name, digits):
        value = v2._num(last.get(name)) if name else None
        return None if value is None else round(value, digits)

    close = num("close", 8)
    if close is not None:
        out["latest_price"] = round(close, 4) if close < 1 else round(close, 2)
    for name in ("change_1d", "change_7d", "change_30d", "rsi"):
        out[name] = num(name, 1)
    out["adx"] = num("adx", 1)
    out["volume_ratio"] = num("volume_ratio", 2)
    atr = num("atr", 10)
    out["atr_pct"] = round(atr / close * 100, 2) if atr and close else None
    upper, lower = v2._col(frame, "BBU_"), v2._col(frame, "BBL_")
    up, low = num(upper, 10), num(lower, 10)
    out["bb_position"] = round((close - low) / (up - low), 2) if None not in (up, low, close) and up > low else None
    return out


def mini_bar(value, width: int = 64) -> str:
    """A small bar centred on zero: fills right for positive, left for negative."""
    if value is None:
        return (f"<span style='display:inline-block;width:{width}px;height:8px;border-radius:4px;"
                "background:var(--ang-track, #e5e7eb);vertical-align:middle;'></span>")
    half = width // 2
    size = max(1, min(half, round(abs(value) / 100 * half)))
    colour = reading_tone(value)[3]
    left = half if value >= 0 else half - size
    return (
        f"<span style='position:relative;display:inline-block;width:{width}px;height:8px;border-radius:4px;"
        "background:var(--ang-track, #e5e7eb);vertical-align:middle;overflow:hidden;'>"
        f"<span style='position:absolute;left:{left}px;width:{size}px;top:0;bottom:0;background:{colour};'></span>"
        f"<span style='position:absolute;left:{half - 1}px;width:2px;top:0;bottom:0;background:var(--ang-muted, #9ca3af);"
        "opacity:0.5;'></span></span>"
    )


def number_badge(value) -> str:
    fg, bg, _arrow, _bar = reading_tone(value)
    return (f"<span style='display:inline-block;min-width:40px;text-align:center;background:{bg};color:{fg};"
            f"border-radius:4px;padding:2px 6px;font-weight:600;line-height:1;'>{signed(value)}</span>")


def cluster_hint(key: str, cluster: dict | None) -> str:
    spec = v2.CLUSTERS[key]
    if not cluster or cluster.get("value") is None:
        return f"{spec['name']}: not enough data. {spec['question']}"
    have, total = cluster.get("coverage") or (0, 0)
    part = f" Uses {have} of {total} parts." if have < total else ""
    return f"{spec['name']} ({spec['horizon']}): {cluster.get('label')}. {spec['question']}{part} A description, not a forecast."


def table_cell(key: str, row: dict, pick: str | None = None) -> str:
    """One sortable table cell for a cluster: bar plus signed number, with a hover explanation."""
    value = row.get(key)
    cluster = ((row.get("signals") or {}).get("clusters") or {}).get(key)
    sort = "" if value is None else f"{float(value):.4f}"
    inner = f"<span style='display:inline-flex;align-items:center;gap:6px;'>{mini_bar(value)}{number_badge(value)}</span>"
    if pick:
        inner = (f"<button type='button' data-pick='{_esc(pick)}|breakdown' title='{_esc(cluster_hint(key, cluster))}' "
                 "style='display:block;margin:0;padding:0;border:none;background:transparent;text-align:left;"
                 f"cursor:pointer;font:inherit;color:inherit;'>{inner}</button>")
    else:
        inner = f"<span title='{_esc(cluster_hint(key, cluster))}'>{inner}</span>"
    return f"<td data-sort='{sort}' style='padding:10px;white-space:nowrap;'>{inner}</td>"


def header_hint(key: str) -> str:
    spec = v2.CLUSTERS[key]
    return f"{spec['icon']} {spec['name']}: {spec['question']} -100 to +100; positive means up. A description, not a forecast."


def badge(status: str) -> str:
    text, fg, bg, hint = BADGES.get(status, BADGES["unvalidated"])
    return (f"<span title='{_esc(hint)}' style='display:inline-block;padding:1px 7px;border-radius:999px;"
            f"background:{bg};color:{fg};font-size:0.72rem;font-weight:700;white-space:nowrap;'>{_esc(text)}</span>")


def cluster_rows(result: dict) -> str:
    """The three cluster rows for the asset card: icon, name, bar, number, words, evidence badge."""
    rows = []
    for key, spec in v2.CLUSTERS.items():
        c = (result.get("clusters") or {}).get(key) or {}
        rows.append(
            f"<div title='{_esc(cluster_hint(key, c))}' style='display:flex;align-items:center;gap:10px;"
            "padding:6px 0;border-top:1px solid var(--ang-border, #e5e7eb);flex-wrap:wrap;'>"
            f"<span style='width:96px;font-weight:600;'>{spec['icon']} {spec['name']}</span>"
            f"{mini_bar(c.get('percent'), 120)}{number_badge(c.get('percent'))}"
            f"<span style='flex:1 1 140px;'>{_esc(c.get('label') or 'Not enough data')}"
            f"<span class='ang-kicker' style='margin-left:6px;'>{_esc(spec['horizon'])}</span></span>"
            f"{badge(v2.VALIDATION[key]['status'])}</div>"
        )
    return "".join(rows)


def against_note(result: dict) -> str:
    kind = result.get("against_trend")
    if not kind:
        return ""
    return (f"<div style='margin:8px 0 0;padding:6px 10px;border-radius:6px;background:#fef3c7;color:#92400e;'>"
            f"↩️ {_esc(v2.AGAINST_TREND_TEXT[kind])}</div>")


def context_chips(result: dict) -> str:
    """Non-directional context: never colours anything up or down."""
    ctx = result.get("context") or {}
    chips = []
    vol = ctx.get("volatility") or {}
    if vol.get("atr_pct") is not None:
        pct = vol.get("percentile")
        where = f", {vol.get('label', '').lower()} for this asset" if pct is not None else ""
        status = v2.VALIDATION[vol.get("validation", "volatility_crypto")]
        chips.append(_chip("🌊", f"Range {vol['atr_pct']:.2f}%{where}",
                           "Typical daily range (ATR%). " + status["note"], status["status"]))
    strength = ctx.get("trend_strength") or {}
    if strength.get("adx") is not None:
        chips.append(_chip("💪", f"Trend strength {strength['label'].lower()} (ADX {strength['adx']:.0f})",
                           "ADX measures how strongly price is trending, whichever way. It has no direction."))
    regime = ctx.get("regime") or {}
    if regime.get("state"):
        words = {"trending": "Trending", "ranging": "Ranging", "transitional": "Between trend and range"}
        chips.append(_chip("🧭", words.get(regime["state"], str(regime["state"]).title()),
                           "Regime from ADX and the 50/200-day averages. Context only."))
    ratio = (ctx.get("participation") or {}).get("volume_ratio")
    if ratio is not None:
        chips.append(_chip("🔈", f"Volume {ratio:.1f}x usual", "Today's volume against its 20-day average. "
                                                              "How active, not which way."))
    for warning in ctx.get("warnings") or []:
        chips.append(_chip("⚠️", warning.split(":")[0].split(",")[0], warning))
    return "<div style='display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;'>" + "".join(chips) + "</div>"


def _chip(icon: str, text: str, hint: str, status: str | None = None) -> str:
    extra = f" {badge(status)}" if status and status != "unvalidated" else ""
    return (f"<span title='{_esc(hint)}' style='display:inline-flex;align-items:center;gap:4px;padding:3px 9px;"
            "border-radius:999px;border:1px solid var(--ang-border, #e5e7eb);font-size:0.82rem;'>"
            f"{icon} {_esc(text)}{extra}</span>")


def asset_card(result: dict) -> str:
    """The asset's signals at a glance (replaces the 0-100 score card)."""
    if result.get("status") != "ok":
        return f"<div class='ang-card'>{_esc(result.get('message') or 'Not enough data yet')}</div>"
    when = result.get("as_of")
    note = "Daily close of " + _esc(when) + (" (today's bar is still forming)" if result.get("unfinished_bar_skipped") else "")
    return (
        "<div class='ang-card' style='margin-bottom:8px;'>"
        f"<div class='ang-kicker'>Technical signals · {note}</div>"
        f"{cluster_rows(result)}{against_note(result)}{context_chips(result)}</div>"
    )


def breakdown(result: dict) -> str:
    """Every component with its plain reading, grouped by cluster, then the lenses and the version."""
    if result.get("status") != "ok":
        return ""
    readings = result.get("readings") or {}
    parts = []
    for key, spec in v2.CLUSTERS.items():
        c = (result.get("clusters") or {}).get(key) or {}
        parts.append(
            f"<div style='margin-top:12px;'><span style='font-weight:700;'>{spec['icon']} {spec['name']}</span> "
            f"{number_badge(c.get('percent'))} <span class='ang-kicker'>{_esc(spec['question'])}</span></div>"
        )
        for comp, info in (c.get("components") or {}).items():
            pct = info.get("percent")
            reading = v2.component_reading(comp, readings) if pct is not None else "No data from this source"
            parts.append(
                "<div style='display:flex;align-items:center;gap:10px;padding:4px 0 4px 18px;flex-wrap:wrap;'>"
                f"<span style='width:210px;'>{_esc(v2.COMPONENT_NAMES[comp])}</span>{mini_bar(pct, 90)}"
                f"<span style='width:44px;text-align:right;font-weight:600;'>{signed(pct)}</span>"
                f"<span class='ang-kicker'>{_esc(reading)}</span></div>"
            )
    lenses = result.get("lenses") or {}
    parts.append("<div style='margin-top:14px;font-weight:700;'>🔎 Named views (hypotheses, not validated)</div>")
    for key, spec in v2.LENSES.items():
        value = (lenses.get(key) or {}).get("percent")
        parts.append(
            "<div style='display:flex;align-items:center;gap:10px;padding:4px 0 4px 18px;flex-wrap:wrap;'>"
            f"<span style='width:210px;'>{_esc(spec['name'])}</span>{mini_bar(value, 90)}"
            f"<span style='width:44px;text-align:right;font-weight:600;'>{signed(value)}</span>"
            f"<span class='ang-kicker'>{_esc(spec['meaning'])}</span></div>"
        )
    parts.append(
        f"<div class='ang-kicker' style='margin-top:12px;' title='Identifies the exact indicator definitions behind "
        f"these readings'>Definitions ref {result.get('fingerprint')}"
        f" · as of the {_esc(result.get('as_of'))} close</div>"
    )
    return "".join(parts)


EXPLAINER = f"""
**How the technical signals work**

The ten classic indicators are read as **three separate descriptions**, never added into one score:

- 📈 **Trend** (weeks to months): price against its 50- and 200-day averages, the Ichimoku cloud and the MACD
  line, measured in the asset's own typical daily ranges.
- 🎯 **Stretch** (1 to 4 weeks): RSI, Stochastic, Bollinger position, the 7-day move and the MACD histogram.
  How far price has run up or down within its recent range.
- 🔊 **Flow** (days to weeks): on-balance volume and heavy-volume days. Is volume backing rises or falls?

Each runs from **-100 to +100; positive means up** (above the averages, stretched up, volume backing rises).
Readings change smoothly, so one price tick never flips a reading. Missing data (for example a coin with no
volume) shows as missing, never as neutral. Readings use the last **finished** daily bar.

**Context, never directional:** 🌊 typical daily range (ATR%) and how it compares with the asset's own past
year, 💪 trend strength (ADX), 🧭 regime, 🔈 volume against usual.

**Named views** state a hypothesis: a *trend-following* view leans with the Trend; a *mean-reversion* view leans
against the Stretch. When the Trend and the Stretch point opposite ways, the app calls it a pullback (or rally)
inside the trend.

**What is and isn't shown by evidence:** none of the directional readings has been shown to predict price moves.
For large US stocks, a higher-than-usual ATR% has been followed by bigger moves, up or down (tested once on
held-back data).
"""
