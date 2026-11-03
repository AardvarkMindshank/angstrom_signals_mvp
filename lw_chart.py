"""
The data sent to the TradingView Lightweight Charts price chart.

Python does every calculation (indicators come from scoring.calculate_indicators on
the chosen interval's candles, the same formulas as everywhere else). The browser
only draws. This module turns a candle table plus the indicator choices into one
JSON-ready dict; it does not import Streamlit, so it can be tested on its own.

Library: TradingView Lightweight Charts (Apache License 2.0), served from
static/lwc/ with its licence. The chart shows TradingView's attribution logo,
as the licence's notice asks.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

import chart_data

LIBRARY_PATH = "/app/static/lwc/lightweight-charts.standalone.production.js"

UP = "#26a69a"
DOWN = "#ef5350"
UP_FADED = "rgba(38,166,154,0.35)"
DOWN_FADED = "rgba(239,83,80,0.35)"

PANEL_TITLES = {
    "volume": "Volume", "rsi": "RSI (14)", "macd": "MACD", "stoch": "Stochastic (14, 3)",
    "adx": "ADX (14)", "obv": "On-balance volume",
}
# Lower panels that read on a fixed 0 to 100 scale.
FIXED_0_100 = ("rsi", "stoch")
MIN_PANEL_PX = 70


def _find(columns, prefix: str) -> str | None:
    for name in columns:
        if str(name).startswith(prefix):
            return name
    return None


def _values(series: pd.Series, digits: int = 8) -> list:
    """Numbers for JSON; gaps (NaN) become None so the chart leaves a gap."""
    out = []
    for value in pd.to_numeric(series, errors="coerce").tolist():
        if value is None or not math.isfinite(value):
            out.append(None)
        else:
            out.append(round(float(value), digits))
    return out


def theme(dark: bool) -> dict:
    """The same surfaces as the Plotly chart, so switching engines does not change the page."""
    return {
        "dark": bool(dark),
        "bg": "#262730" if dark else "#ffffff",
        "ink": "#e5e7eb" if dark else "#374151",
        "grid": "#3f4654" if dark else "#eef0f3",
        "muted": "#9ca3af" if dark else "#6b7280",
        "up": UP, "down": DOWN, "up_faded": UP_FADED, "down_faded": DOWN_FADED,
    }


def pane_heights(price_px: int, panels: list[str]) -> list[int]:
    """Price pane at the account's chosen height; lower panels share the space the Plotly chart gives them."""
    if not panels:
        return [int(price_px)]
    old_height = 750 + 150 * (len(panels) - 2) if len(panels) > 2 else 750 - 100 * (2 - len(panels))
    panels_px = (old_height - 210) * 0.5
    each = max(MIN_PANEL_PX, int(panels_px / len(panels)))
    return [int(price_px)] + [each] * len(panels)


def _line(sid, name, pane, values, colour, width=1.5, style="solid", scale=None, legend=True, alpha=1.0):
    return {"id": sid, "type": "line", "name": name, "pane": pane, "values": values, "color": colour,
            "width": width, "style": style, "scale": scale, "legend": legend, "alpha": alpha}


def _bars_ahead(last: pd.Timestamp, target: pd.Timestamp, interval: str) -> int | None:
    """How many candles until `target` (a date) after the last candle; shares only."""
    last_day = pd.Timestamp(last).tz_localize(None).normalize() if pd.Timestamp(last).tzinfo else pd.Timestamp(last).normalize()
    target_day = pd.Timestamp(target).tz_localize(None).normalize() if pd.Timestamp(target).tzinfo else pd.Timestamp(target).normalize()
    if target_day <= last_day:
        return None
    if interval == "1D":
        return int(np.busday_count(last_day.date(), target_day.date()))
    if interval == "1W":
        return max(1, int((target_day - last_day).days // 7))
    return None


def _report_day_index(times_local: pd.DatetimeIndex, day) -> int | None:
    """The first candle on a report day, or None when that day is not on the chart."""
    wanted = pd.Timestamp(day).date()
    for position, stamp in enumerate(times_local):
        current = stamp.date()
        if current == wanted:
            return position
        if current > wanted:
            return None
    return None


def build_payload(
    df: pd.DataFrame,
    layout: dict,
    *,
    kind: str,
    interval: str,
    range_key: str,
    session=None,
    range_start=None,
    view_key: str = "",
    price_px: int = 380,
    dark: bool = False,
    past_reports=(),
    next_report=None,
    liquidation: dict | None = None,
    source: str = "",
    title: str = "",
) -> dict:
    """Everything the browser needs to draw one chart. `df` holds candles with indicators
    and a `forming` column (True for an unfinished last candle)."""
    columns = list(df.columns)
    times = chart_data.display_seconds(df.index, interval, kind, session)
    if interval in ("1D", "1W") or kind == "crypto" or not session:
        local = df.index.tz_convert("UTC") if df.index.tz is not None else df.index
    else:
        local = df.index.tz_convert(session[0])
    forming = bool(df["forming"].iloc[-1]) if "forming" in df.columns and len(df) else False

    panels = list(layout.get("panels") or [])
    overlays = list(layout.get("overlays") or [])
    secondary = list(layout.get("secondary") or [])
    pane_of = {name: index + 1 for index, name in enumerate(panels)}
    series: list[dict] = []

    # Price pane: the two moving averages the Plotly chart always shows, then the chosen overlays.
    if "sma_20" in columns:
        series.append(_line("sma20", "SMA 20", 0, _values(df["sma_20"]), "#f59e0b"))
    if "sma_50" in columns:
        series.append(_line("sma50", "SMA 50", 0, _values(df["sma_50"]), "#4169e1"))
    if "sma200" in overlays and "sma_200" in columns:
        series.append(_line("sma200", "SMA 200", 0, _values(df["sma_200"]), "#9333ea"))
    upper, lower = _find(columns, "BBU_"), _find(columns, "BBL_")
    if upper and lower:
        series.append({"id": "bb_fill", "type": "band", "name": "Bollinger", "pane": 0, "legend": False,
                       "a": _values(df[upper]), "b": _values(df[lower]), "fill": "rgba(128,128,128,0.08)"})
        series.append(_line("bb_up", "BB upper", 0, _values(df[upper]), "#9ca3af", width=1, style="dotted"))
        series.append(_line("bb_low", "BB lower", 0, _values(df[lower]), "#9ca3af", width=1, style="dotted"))
    if "ichimoku" in overlays and {"ichi_span_a", "ichi_span_b"} <= set(columns):
        series.append({"id": "cloud", "type": "band", "name": "Ichimoku cloud", "pane": 0, "legend": False,
                       "a": _values(df["ichi_span_a"]), "b": _values(df["ichi_span_b"]),
                       "fill": "rgba(128,128,128,0.12)"})
        series.append(_line("span_a", "Cloud edge A", 0, _values(df["ichi_span_a"]), "rgba(34,197,94,0.6)", width=1))
        series.append(_line("span_b", "Cloud edge B", 0, _values(df["ichi_span_b"]), "rgba(239,68,68,0.6)", width=1))
        if "ichi_tenkan" in columns:
            series.append(_line("tenkan", "Tenkan", 0, _values(df["ichi_tenkan"]), "#0ea5e9", width=1))
        if "ichi_kijun" in columns:
            series.append(_line("kijun", "Kijun", 0, _values(df["ichi_kijun"]), "#f43f5e", width=1))

    # Lower panes (or the price pane's 0 to 100 scale when the account overlays them).
    def place(key):
        if key in secondary:
            return 0, "osc"
        return pane_of.get(key), None

    guides: list[dict] = []
    if "volume" in pane_of:
        volume = pd.to_numeric(df["volume"], errors="coerce").fillna(0.0)
        up = (df["close"] >= df["open"]).tolist()
        series.append({"id": "volume", "type": "hist", "name": "Volume", "pane": pane_of["volume"],
                       "values": _values(volume, 2),
                       "colors": ["rgba(38,166,154,0.6)" if u else "rgba(239,83,80,0.6)" for u in up]})
    if "rsi" in columns and ("rsi" in pane_of or "rsi" in secondary):
        pane, scale = place("rsi")
        series.append(_line("rsi", "RSI", pane, _values(df["rsi"], 2), "#8b5cf6", scale=scale,
                            width=1.1 if scale else 1.5, alpha=0.6 if scale else 1.0))
        guides += [{"series": "rsi", "value": 70, "color": "#ef4444"}, {"series": "rsi", "value": 30, "color": "#22c55e"}]
        if not scale:
            guides.append({"series": "rsi", "value": 50, "color": "#9ca3af", "style": "dotted"})
    if "macd" in pane_of:
        pane = pane_of["macd"]
        hist_col, line_col, signal_col = _find(columns, "MACDh_"), _find(columns, "MACD_"), _find(columns, "MACDs_")
        if hist_col:
            hist = pd.to_numeric(df[hist_col], errors="coerce")
            series.append({"id": "macd_hist", "type": "hist", "name": "MACD histogram", "pane": pane,
                           "values": _values(hist),
                           "colors": ["rgba(38,166,154,0.6)" if (v if v == v else 0) >= 0 else "rgba(239,83,80,0.6)"
                                      for v in hist.tolist()]})
        if line_col:
            series.append(_line("macd", "MACD", pane, _values(df[line_col]), "#4169e1"))
        if signal_col:
            series.append(_line("macd_signal", "Signal", pane, _values(df[signal_col]), "#f59e0b"))
    if "stoch_k" in columns and ("stoch" in pane_of or "stoch" in secondary):
        pane, scale = place("stoch")
        series.append(_line("stoch", "Stoch %K", pane, _values(df["stoch_k"], 2), "#0ea5e9", scale=scale,
                            width=1.1 if scale else 1.5, alpha=0.6 if scale else 1.0))
        if not scale:
            guides += [{"series": "stoch", "value": 80, "color": "#ef4444"}, {"series": "stoch", "value": 20, "color": "#22c55e"}]
    if "adx" in columns and ("adx" in pane_of or "adx" in secondary):
        pane, scale = place("adx")
        series.append(_line("adx", "ADX", pane, _values(df["adx"], 2), "#a16207", scale=scale,
                            width=1.1 if scale else 1.5, alpha=0.6 if scale else 1.0))
        if not scale:
            guides.append({"series": "adx", "value": 25, "color": "#9ca3af"})
    if "obv" in pane_of and "obv" in columns:
        series.append(_line("obv", "OBV", pane_of["obv"], _values(df["obv"], 2), "#14b8a6"))
        if "obv_sma_20" in columns:
            series.append(_line("obv_avg", "OBV average", pane_of["obv"], _values(df["obv_sma_20"], 2), "#f59e0b",
                                width=1.2, style="dotted"))
    for guide in guides:
        guide.setdefault("style", "dashed")

    panes = [{"title": f"{title} · {chart_data.INTERVAL_LABELS.get(interval, interval)}".strip(" ·"),
              "height": 0, "fixed": None}]
    heights = pane_heights(price_px, panels)
    panes[0]["height"] = heights[0]
    for index, name in enumerate(panels):
        panes.append({"title": PANEL_TITLES.get(name, name), "height": heights[index + 1],
                      "fixed": [0, 100] if name in FIXED_0_100 else None})

    # Earnings: dotted lines on past report days, a dashed line on the next one.
    vlines: list[dict] = []
    right_offset = 0
    for day in past_reports or ():
        position = _report_day_index(local, day)
        if position is not None:
            vlines.append({"index": position, "color": "#f59e0b", "style": "dotted", "width": 1.5, "label": ""})
    if next_report is not None:
        target = pd.Timestamp(next_report)
        position = _report_day_index(local, target)
        if position is not None:
            vlines.append({"index": position, "color": "#f59e0b", "style": "dashed", "width": 2,
                           "label": f"Earnings {target:%d %b}"})
        else:
            ahead = _bars_ahead(df.index[-1], target, interval)
            last_day = pd.Timestamp(local[-1]).date()
            if ahead is not None and (target.date() - last_day).days <= 42:
                vlines.append({"index": len(df) - 1 + ahead, "color": "#f59e0b", "style": "dashed", "width": 2,
                               "label": f"Earnings {target:%d %b}"})
                right_offset = ahead + max(3, ahead // 10)

    # Liquidation levels: brighter and thicker where more money would be force-closed.
    price_lines: list[dict] = []
    if liquidation and liquidation.get("status") == "ok":
        rows = [("longs", r) for r in liquidation.get("longs") or []] + [("shorts", r) for r in liquidation.get("shorts") or []]
        clean = []
        for side, row in rows:
            try:
                price, usd = float(row.get("price")), float(row.get("usd"))
            except (TypeError, ValueError):
                continue
            if math.isfinite(price) and math.isfinite(usd) and price > 0 and usd > 0:
                clean.append((side, price, usd))
        biggest = max((usd for _s, _p, usd in clean), default=1.0) or 1.0
        for side, price, usd in clean:
            share = usd / biggest
            rgb = "239,68,68" if side == "longs" else "34,197,94"
            price_lines.append({
                "price": price, "color": f"rgba({rgb},{0.15 + 0.55 * share:.2f})",
                "width": max(1, min(4, int(round(1 + 3 * share)))),
                "side": side, "usd": usd,
            })

    # What the chart opens on: the chosen range, ending at the newest candle.
    start_index = 0
    if range_start is not None:
        start_index = int(np.searchsorted(df.index.values, pd.Timestamp(range_start).to_datetime64()))
        start_index = max(0, min(start_index, len(df) - 1))

    open_ = _values(df["open"])
    high = _values(df["high"])
    low_ = _values(df["low"])
    close = _values(df["close"])
    return {
        "lib": LIBRARY_PATH,
        "key": view_key,
        "interval": interval,
        "range": range_key,
        "intraday": interval not in ("1D", "1W"),
        "theme": theme(dark),
        "times": times,
        "ohlc": [open_, high, low_, close],
        "volume": _values(pd.to_numeric(df.get("volume", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0), 2),
        "forming": forming,
        "series": series,
        "guides": guides,
        "panes": panes,
        "vlines": vlines,
        "price_lines": price_lines,
        "start_index": start_index,
        "right_offset": int(right_offset),
        "source": source,
        "clock": "" if interval in ("1D", "1W") else ("UTC" if (kind == "crypto" or not session) else _clock_name(session[0])),
    }


def _clock_name(zone: str) -> str:
    names = {"America/New_York": "New York time", "Europe/London": "London time", "Asia/Tokyo": "Tokyo time",
             "Asia/Hong_Kong": "Hong Kong time", "Europe/Berlin": "Frankfurt time", "Europe/Paris": "Paris time",
             "Australia/Sydney": "Sydney time", "Asia/Bangkok": "Bangkok time"}
    return names.get(zone, zone.replace("_", " ") + " time")


def payload_size(payload: dict) -> int:
    """Rough JSON size in bytes, for the performance check."""
    import json

    return len(json.dumps(payload, separators=(",", ":")))


def today_utc() -> date:
    return pd.Timestamp.now(tz="UTC").date()
