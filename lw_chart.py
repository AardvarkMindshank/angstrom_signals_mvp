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

import chart_candles
import chart_data

LIBRARY_PATH = "/app/static/lwc/lightweight-charts.standalone.production.js"

UP = "#26a69a"
DOWN = "#ef5350"
UP_FADED = "rgba(38,166,154,0.35)"
DOWN_FADED = "rgba(239,83,80,0.35)"

PANEL_TITLES = {
    "volume": "Volume", "rsi": "RSI (14)", "macd": "MACD", "stoch": "Stochastic (14, 3)",
    "stochrsi": "Stoch RSI (3, 3, 14, 14, OHLC4)", "cipher": "Sonar", "adx": "ADX (14)", "obv": "On-balance volume",
}
# Lower panels that read on a fixed 0 to 100 scale.
FIXED_0_100 = ("rsi", "stoch", "stochrsi")
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
    return [int(price_px)] + [max(each * 2, 200) if name == "cipher" else each for name in panels]


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
    if interval == "1Mo":
        return max(1, (target_day.year - last_day.year) * 12 + target_day.month - last_day.month)
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


# Macro events (macro_calendar.py) as dashed lines: the same colours and label rows as the Tides waves.
# The last number is the label's row, counted up from the bottom of the price pane (clear of the legend at the top).
EVENT_MARKS = {"fomc": ("Fed", "#dc2626", -34), "cpi": ("CPI", "#d97706", -21), "jobs": ("Jobs", "#7c3aed", -8)}
_STEP = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4), "12h": pd.Timedelta(hours=12),
         "1D": pd.Timedelta(days=1), "1W": pd.Timedelta(days=7),
         "1Mo": pd.Timedelta(days=30)}


def event_lines(index: pd.DatetimeIndex, interval: str, kind: str, events, ahead_days: int = 14) -> tuple[list, int]:
    """([vline], bars to leave on the right) for Fed, CPI and jobs events on this chart. A past event sits on the
    candle that contains it; an upcoming one (within two weeks) is placed past the last candle, labelled with its
    date. Equities: the event lands on the trading day it moves (a release before the open moves that day)."""
    if not len(index):
        return [], 0
    idx = index.tz_convert("UTC") if index.tz is not None else index.tz_localize("UTC")
    daily = interval in ("1D", "1W", "1Mo")
    zone = "America/New_York" if kind == "equity" else "UTC"
    if daily:       # compare calendar days, in the market's own time zone
        keys = idx.tz_convert(zone).tz_localize(None).normalize()
    else:
        keys = idx
    last = idx[-1]
    step = _STEP.get(interval, pd.Timedelta(days=1))
    now = pd.Timestamp.now(tz="UTC")
    out, ahead_max = [], 0
    for e in events:
        mark = EVENT_MARKS.get(e.get("kind"))
        if not mark:
            continue
        name, colour, row = mark
        at = pd.Timestamp(e["at"]).tz_convert("UTC")
        key = at.tz_convert(zone).tz_localize(None).normalize() if daily else at
        if key < keys[0]:
            continue
        if at <= now:                    # happened: on the candle that holds it
            pos = int(np.searchsorted(keys.values, key.to_datetime64(), side="right")) - 1
            if pos >= 0:
                out.append({"index": pos, "color": colour, "style": "dashed", "width": 1, "label": name,
                            "label_y": row, "event": True})
            continue
        if (at - now) > pd.Timedelta(days=ahead_days):
            continue
        if kind == "equity" and not daily:
            continue                     # session candles: no reliable count of candles ahead
        if kind == "equity" and interval == "1D":
            ahead = int(np.busday_count(keys[-1].date(), key.date()))
        elif daily:
            ahead = int(math.ceil((key - keys[-1]) / step))
        else:
            ahead = int(math.ceil((at - last) / step))
        if ahead <= 0:                   # in the candle still forming
            out.append({"index": len(idx) - 1, "color": colour, "style": "dashed", "width": 1.5,
                        "label": f"{name} {at:%d %b}", "label_y": row, "event": True})
            continue
        out.append({"index": len(idx) - 1 + ahead, "color": colour, "style": "dashed", "width": 1.5,
                    "label": f"{name} {at:%d %b}", "label_y": row, "event": True})
        ahead_max = max(ahead_max, ahead)
    return out, (ahead_max + max(2, ahead_max // 10)) if ahead_max else 0


def cipher_series(df: pd.DataFrame, pane: int, dark: bool = False) -> list[dict]:
    """The 📡 Sonar strip (our version of the oscillator strip Drew reads), drawn as his chart draws it (colours from his Style settings): the light-blue
    and blue waves, the yellow VWAP area, the green / red money flow, the bar along the bottom, the magenta RSI, the
    green / red Stoch RSI, the small cross dots and the big buy and sell dots. Columns from chart_indicators."""
    n = len(df)
    zero = [0.0] * n

    def col(name):
        return pd.to_numeric(df[name], errors="coerce")

    def flag(name):
        return df[name].fillna(False).astype(bool).tolist() if name in df.columns else [False] * n

    def area(sid, name, values, fill):
        return {"id": sid, "type": "band", "name": name, "pane": pane, "legend": False,
                "a": _values(values, 2), "b": zero, "fill": fill}

    mf = col("mc_mf")
    out = [
        area("mc_wt1", "Light-blue wave", col("mc_wt1"), "rgba(144,202,249,0.95)"),
        area("mc_wt2", "Blue wave", col("mc_wt2"), "rgba(13,71,161,0.9)" if dark else "rgba(21,101,192,0.85)"),
        area("mc_vwap", "VWAP", col("mc_vwap"), "rgba(225,212,60,0.6)"),
        area("mc_mf_in", "Money flow in", mf.clip(lower=0), "rgba(56,160,40,0.55)"),
        area("mc_mf_out", "Money flow out", mf.clip(upper=0), "rgba(190,30,30,0.5)"),
    ]
    flow_in = df["mc_mf_in"].tolist() if "mc_mf_in" in df.columns else [True] * n
    out.append({"id": "mc_bar", "type": "hist", "name": "Money flow bar", "pane": pane, "legend": False,
                "base": -100, "values": [None if v != v else -93.0 for v in mf.tolist()],
                "colors": ["rgba(40,130,40,0.85)" if f else "rgba(130,25,25,0.85)" for f in flow_in]})
    out.append(_line("mc_rsi", "RSI", pane, _values(col("mc_rsi"), 2), "#e100e1", width=1))
    k, d = col("mc_sk"), col("mc_sd")
    stoch = _line("mc_sk", "Stoch RSI", pane, _values(k, 2), "#39ff14", width=2)
    stoch["colors"] = ["#39ff14" if (a == a and b == b and a >= b) else "#ff2a1a" for a, b in zip(k.tolist(), d.tolist())]
    out.append(stoch)
    w2 = col("mc_wt2").tolist()
    cross = pd.to_numeric(df["mc_cross"], errors="coerce").fillna(0).tolist()
    for sid, col, tint in (("mc_snake_g", "sm_snake_eyes_green", "rgba(57,255,20,0.35)"),
                           ("mc_snake_r", "sm_snake_eyes_red", "rgba(255,42,26,0.35)")):
        if col in df.columns:        # snake eyes: a soft halo behind the second of two dots close together
            hits = flag(col)
            out.append({"id": sid, "type": "dots", "name": "Snake eyes", "pane": pane, "legend": False, "radius": 7,
                        "color": tint, "values": [round(w, 2) if h and w == w else None for h, w in zip(hits, w2)],
                        "colors": [tint] * n})
    out.append({"id": "mc_dots", "type": "dots", "name": "Wave crosses", "pane": pane, "legend": False, "radius": 3, "color": "#1fbf75",
                "values": [round(w, 2) if c and w == w else None for c, w in zip(cross, w2)],
                "colors": ["#1fbf75" if c > 0 else "#e0474c" for c in cross]})
    buy, sell = flag("mc_buy"), flag("mc_sell")     # big green Buy dots on the bottom bar, big red Sell at the top
    out.append({"id": "mc_buy", "type": "dots", "name": "Buy", "pane": pane, "legend": False, "radius": 5, "color": "#3fff00",
                "values": [-96.5 if b else None for b in buy], "colors": ["#3fff00"] * n})
    out.append({"id": "mc_sell", "type": "dots", "name": "Sell", "pane": pane, "legend": False, "radius": 5,
                "color": "#ff2a1a", "values": [100.0 if x else None for x in sell], "colors": ["#ff2a1a"] * n})
    return out


# 🛰️ Sonar markers on the price chart: (shape, colour, above the candle?, size, hover words). The price chart shows
# the markers drawn over candles; the big dots stay on the 📡 Sonar strip.
SONAR_MARKS = {
    "trend_turn_up": ("triangle_up", "#6366f1", False, 1.1, "Trend turn up: the 11 average crossed above the 15"),
    "trend_turn_down": ("triangle_down", "#6366f1", True, 1.1, "Trend turn down: the 11 average crossed below the 15"),
    "long_cross": ("circle", "#22c55e", False, 1.0, "Green dot: the 11 average crossed above the 34"),
    "short_cross": ("circle", "#ef4444", True, 1.0, "Red dot: the 34 average crossed above the 11"),
    "red_cross": ("x", "#ef4444", True, 0.9, "Red cross: the 5 average crossed below the 11"),
    "red_diamond": ("diamond", "#dc2626", True, 0.9, "Red diamond: the wave turned down"),
    "blood_diamond": ("diamond", "#7f1d1d", True, 1.35, "Blood diamond: a red diamond and a red cross together"),
    "yellow_cross": ("x", "#facc15", True, 1.35, "Yellow cross: the wave turned down while RSI was 15 to 30 and "
                                                 "money flowed out. A warning of a sharp flush"),
    "strength_candle": ("diamond", "#eab308", True, 0.7, "Strength: two green candles opening above the 11 and 34"),
}
SONAR_DEFAULT = tuple(k for k in SONAR_MARKS if k != "strength_candle")     # the yellow diamonds are the noisiest


def sonar_band(df: pd.DataFrame, dark: bool = False) -> list[dict]:
    """The grey band of eight averages (5 to 34), lighter for the slower ones, with a faint fill between the fastest
    and the slowest."""
    from signal_library.signals_sonar import RIBBON

    out = [{"id": "sm_fill", "type": "band", "name": "Sonar band", "pane": 0, "legend": False,
            "a": _values(df["sm_ema_5"]), "b": _values(df["sm_ema_34"]),
            "fill": "rgba(148,163,184,0.16)" if dark else "rgba(100,116,139,0.12)"}]
    for i, n in enumerate(RIBBON):
        alpha = 0.85 - 0.07 * i
        colour = f"rgba(203,213,225,{alpha:.2f})" if dark else f"rgba(100,116,139,{alpha:.2f})"
        line = _line(f"sm_ema_{n}", f"Band {n}", 0, _values(df[f"sm_ema_{n}"]), colour, width=1)
        line["legend"] = False
        out.append(line)
    return out


def sonar_symbols(df: pd.DataFrame, chosen=None) -> list[list]:
    """[candle index, shape, colour, above, size, words] for each marker printed, closed candles only. A blood
    diamond stands for its own red diamond and red cross."""
    keys = [k for k in (chosen if chosen is not None else SONAR_DEFAULT) if k in SONAR_MARKS]
    forming = df["forming"].fillna(False).astype(bool).tolist() if "forming" in df.columns else [False] * len(df)
    blood = df["sm_blood_diamond"].fillna(False).astype(bool).tolist() if "sm_blood_diamond" in df.columns else []
    out = []
    for key in keys:
        col = f"sm_{key}"
        if col not in df.columns:
            continue
        shape, colour, above, size, words = SONAR_MARKS[key]
        for i, hit in enumerate(df[col].fillna(False).astype(bool).tolist()):
            if not hit or forming[i]:
                continue
            if key in ("red_diamond", "red_cross") and blood and blood[i] and "blood_diamond" in keys:
                continue
            out.append([i, shape, colour, above, size, words])
    return out


def candle_closes_at(start, interval: str, kind: str, session=None) -> int | None:
    """When the forming candle that started at `start` closes, in milliseconds since 1970 (UTC), for the countdown
    under the price on the right. Equities' day, week and month candles close at the US market close (16:00 New York)."""
    try:
        start = pd.Timestamp(start)
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
        stock_day = kind != "crypto" and interval in ("1D", "1W", "1Mo")
        if stock_day and not session:
            session = ("America/New_York", 570, 960)
        if interval == "1Mo":
            if not stock_day:
                end = start + pd.offsets.MonthBegin(1)
            else:
                zone, _open, close_minute = session
                last = pd.Timestamp(start.date(), tz=zone) + pd.offsets.MonthEnd(0)     # the candle's own month
                while last.weekday() >= 5:
                    last -= pd.Timedelta(days=1)
                end = (last + pd.Timedelta(minutes=close_minute)).tz_convert("UTC")
        else:
            end = chart_data.candle_end(start, interval, kind, session if (stock_day or kind != "crypto") else None)
        return int(pd.Timestamp(end).timestamp() * 1000)
    except Exception:
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
    events=(),
) -> dict:
    """Everything the browser needs to draw one chart. `df` holds candles with indicators
    and a `forming` column (True for an unfinished last candle)."""
    columns = list(df.columns)
    times = chart_data.display_seconds(df.index, interval, kind, session)
    if interval in ("1D", "1W", "1Mo") or kind == "crypto" or not session:
        local = df.index.tz_convert("UTC") if df.index.tz is not None else df.index
    else:
        local = df.index.tz_convert(session[0])
    forming = bool(df["forming"].iloc[-1]) if "forming" in df.columns and len(df) else False
    closes_at = candle_closes_at(df.index[-1], interval, kind, session) if forming else None

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

    symbols: list = []
    if "sonar_marks" in overlays and "sm_ema_5" in columns:
        series += sonar_band(df, dark)
        symbols = sonar_symbols(df, layout.get("sonar_marks"))

    # Lower panes (or the price pane's 0 to 100 scale when the account overlays them).
    def place(key):
        if key in secondary:
            return 0, "osc"
        return pane_of.get(key), None

    guides: list[dict] = []
    if "cipher" in pane_of and "mc_wt1" in columns:
        series += cipher_series(df, pane_of["cipher"], dark)
        ink = "#e5e7eb" if dark else "#6b7280"
        guides += [{"series": "mc_rsi", "value": 0, "color": ink, "style": "solid"},
                   {"series": "mc_rsi", "value": 60, "color": "#bdbdbd", "style": "solid"},
                   {"series": "mc_rsi", "value": -60, "color": "#bdbdbd", "style": "solid"},
                   {"series": "mc_rsi", "value": 53, "color": "#9e9e9e", "style": "dotted"},
                   {"series": "mc_rsi", "value": -53, "color": "#9e9e9e", "style": "dotted"},
                   {"series": "mc_rsi", "value": 100, "color": "#9e9e9e", "style": "dotted"}]
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
    if {"stochrsi_k", "stochrsi_d"} <= set(columns) and ("stochrsi" in pane_of or "stochrsi" in secondary):
        # As TradingView draws it: %K blue, %D orange, a shaded 20 to 80 band with lines at 80, 50 and 20.
        pane, scale = place("stochrsi")
        if not scale:
            n = len(df)
            series.append({"id": "stochrsi_band", "type": "band", "name": "Stoch RSI band", "pane": pane,
                           "legend": False, "a": [80.0] * n, "b": [20.0] * n, "fill": "rgba(41,98,255,0.08)"})
        series.append(_line("stochrsi_k", "Stoch RSI %K", pane, _values(df["stochrsi_k"], 2), "#2962ff",
                            scale=scale, width=1.1 if scale else 1.5, alpha=0.6 if scale else 1.0))
        series.append(_line("stochrsi_d", "Stoch RSI %D", pane, _values(df["stochrsi_d"], 2), "#ff6d00",
                            scale=scale, width=1.1 if scale else 1.5, alpha=0.6 if scale else 1.0))
        if not scale:
            guides += [{"series": "stochrsi_k", "value": 80, "color": "#9ca3af"},
                       {"series": "stochrsi_k", "value": 50, "color": "#9ca3af", "style": "dotted"},
                       {"series": "stochrsi_k", "value": 20, "color": "#9ca3af"}]
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

    panes = [{"title": f"{title} · {chart_candles.INTERVAL_LABELS.get(interval, interval)}".strip(" ·"),
              "height": 0, "fixed": None}]
    heights = pane_heights(price_px, panels)
    panes[0]["height"] = heights[0]
    for index, name in enumerate(panels):
        panes.append({"title": PANEL_TITLES.get(name, name), "height": heights[index + 1],
                      "fixed": [0, 100] if name in FIXED_0_100 else [-105, 105] if name == "cipher" else None})

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

    if events:
        marks, extra = event_lines(df.index, interval, kind, events)
        vlines += marks
        right_offset = max(right_offset, extra)

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
        "intraday": interval not in ("1D", "1W", "1Mo"),
        "theme": theme(dark),
        "times": times,
        "ohlc": [open_, high, low_, close],
        "volume": _values(pd.to_numeric(df.get("volume", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0), 2),
        "forming": forming,
        "closes_at": closes_at,
        "series": series,
        "guides": guides,
        "panes": panes,
        "vlines": vlines,
        "price_lines": price_lines,
        "symbols": symbols,
        "start_index": start_index,
        "right_offset": int(right_offset),
        "source": source,
        "clock": "" if interval in ("1D", "1W", "1Mo") else ("UTC" if (kind == "crypto" or not session) else _clock_name(session[0])),
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
