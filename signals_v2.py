"""Angstrom technical signals, version 2.

Five layers, kept separate in the output:

1. Readings     what each indicator says, in its own units, plus where that sits in the asset's own past year.
2. Components   directional values from -1 to +1, each tied to one stated hypothesis. Continuous: no cliffs.
3. Clusters     Trend (trend-following), Stretch (mean-reversion) and Flow (volume confirmation). Each is the
                plain average of the components it has data for. They are reported side by side and are never
                added together, because Trend and Stretch are opposite bets on the same price move.
4. Context      non-directional: volatility, trend strength, regime, participation, data coverage. Never
                pushes any reading up or down.
5. Lenses       optional, named combinations with a stated meaning (see LENSES). Not a universal score.

Sign convention for every component and cluster: positive means "under this hypothesis, leans up";
negative means "leans down". That is a description of what the hypothesis says, not a forecast:
none of the directional clusters has passed a validation test (see VALIDATION).

The indicator values come unchanged from scoring.calculate_indicators (pandas-ta). This module only turns
them into readings. Scores use the last COMPLETED daily bar, so they do not change while a day is forming.

Version 1 (the 0-100 points score in scoring.compute_score) is not used by the product any more. It stays
in Git and in the research records (tag holdout-spec-v1) for reproducibility.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, time, timezone

import numpy as np
import pandas as pd

VERSION = "2.0.0"

# Every number the readings depend on. Changing any of them changes FINGERPRINT, which is stored with every
# result so a later reader can tell which definition produced it.
DEFINITIONS = {
    "ma_lengths": [20, 50, 200],
    "ma_scale_per_sqrt_length": 0.5,     # distance from an average, in ATRs, divided by 0.5 * sqrt(length)
    "ichimoku_scale_atr": 1.0,           # distance outside the cloud and Tenkan-Kijun gap, in ATRs
    "macd_level_scale_atr": 1.0,         # MACD line in ATRs
    "macd_accel_scale_atr": 0.25,        # histogram (line minus signal) in quarter-ATRs
    "momentum_days": 7,                  # 7-day return in units of the expected 7-day move (ATR% * sqrt(7))
    "rsi_centre": 50, "rsi_span": 30,    # RSI 20 -> +1 (stretched down), 80 -> -1 (stretched up)
    "stoch_centre": 50, "stoch_span": 50,
    "bb_centre": 0.5, "bb_span": 0.5,
    "obv_scale_sqrt_days": 20,           # OBV minus its 20-day average, in average daily volumes * sqrt(20)
    "heavy_volume_full_at": 2.0,         # volume ratio where a candle counts fully (1.0 counts nothing)
    "percentile_window": 252,            # own-history comparison: up to a year of earlier completed bars
    "percentile_min_history": 60,
    "adx_strong": 25, "adx_weak": 20,
    "label_band_strong": 0.5, "label_band": 0.2,
    "disagreement_level": 0.3,
    "stock_close_new_york": "16:30",
    "lenses": {"trend_following": {"trend": 0.75, "flow": 0.25}, "mean_reversion": {"stretch": 1.0}},
}
FINGERPRINT = hashlib.sha256((VERSION + json.dumps(DEFINITIONS, sort_keys=True)).encode()).hexdigest()[:12]

CLUSTERS = {
    "trend": {
        "name": "Trend", "icon": "📈", "hypothesis": "trend-following",
        "question": "Has price been rising or falling over the last weeks to months?",
        "components": ["moving_averages", "ichimoku", "macd", "momentum"],
    },
    "stretch": {
        "name": "Stretch", "icon": "🎯", "hypothesis": "mean-reversion",
        "question": "Is price unusually low or high within its last 2-4 weeks?",
        "components": ["rsi", "stochastic", "bollinger"],
    },
    "flow": {
        "name": "Flow", "icon": "🔊", "hypothesis": "volume confirmation",
        "question": "Is trading volume backing rises or falls?",
        "components": ["obv", "heavy_volume"],
    },
}

COMPONENT_NAMES = {
    "moving_averages": "Moving averages (20, 50, 200 days)",
    "ichimoku": "Ichimoku cloud",
    "macd": "MACD",
    "momentum": "7-day momentum",
    "rsi": "RSI (14)",
    "stochastic": "Stochastic (14, 3)",
    "bollinger": "Bollinger position (20, 2)",
    "obv": "On-balance volume",
    "heavy_volume": "Heavy-volume candle",
}

LENSES = {
    "trend_following": {
        "name": "Trend-following view",
        "meaning": "What a trend follower would read: Trend, with Flow as a smaller confirmation (75 / 25).",
    },
    "mean_reversion": {
        "name": "Mean-reversion view",
        "meaning": "What a mean-reversion trader would read: Stretch alone.",
    },
}

# What has and has not been shown on data kept aside (hold-out, tag holdout-spec-v1). Badges in the app come
# from here, never from hand-written text.
VALIDATION = {
    "trend": {"status": "unvalidated", "note": "Not shown to predict price moves. A crypto trend-ranking test "
                                              "on held-back data was inconclusive."},
    "stretch": {"status": "unvalidated", "note": "Not shown to predict price moves."},
    "flow": {"status": "unvalidated", "note": "Not shown to predict price moves."},
    "volatility_stock": {"status": "validated_size", "note": "For large US stocks, ATR% higher than usual has "
                         "been followed by bigger moves over the next week, up or down. Tested once on held-back "
                         "data; a modest improvement. It says nothing about direction."},
    "volatility_crypto": {"status": "unvalidated", "note": "For crypto, the same test was inconclusive. "
                          "Treat ATR% as a description of recent behaviour only."},
}

TREND_ALERT_DEFAULT = 50      # alerts: Trend reading (-100..100) crossing +50 / -50
TREND_ALERT_REARM = 20        # it must come back 20 points before the same alert can fire again


# ----------------------------------------------------------------------------- small helpers

def _num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _col(frame: pd.DataFrame, prefix: str) -> str | None:
    for column in frame.columns:
        if str(column).startswith(prefix):
            return column
    return None


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _tanh(value: float) -> float:
    return float(math.tanh(value))


def _mean(values):
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def percent(value) -> int | None:
    """A -1..+1 reading as a whole number from -100 to +100, as the app shows it."""
    return None if value is None else int(round(100 * value))


# ----------------------------------------------------------------------------- completed bars

def last_completed_position(index: pd.Index, kind: str, now: datetime | None = None) -> int | None:
    """Position of the last daily bar that has finished. Crypto days end at 00:00 UTC; US stock days at the
    close in New York (16:30 local, allowing for the closing auction). None if no bar has finished."""
    if len(index) == 0:
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    last_day = pd.Timestamp(index[-1]).date()
    if str(kind).lower().startswith("crypto"):
        finished = last_day < now.astimezone(timezone.utc).date()
    else:
        ny = now.astimezone(_new_york())
        hour, minute = (int(x) for x in DEFINITIONS["stock_close_new_york"].split(":"))
        finished = last_day < ny.date() or (last_day == ny.date() and ny.time() >= time(hour, minute))
    pos = len(index) - 1 if finished else len(index) - 2
    return pos if pos >= 0 else None


def _new_york():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("America/New_York")
    except Exception:  # pragma: no cover - tzdata is in requirements
        return timezone.utc


# ----------------------------------------------------------------------------- readings and components

def _percentile(series: pd.Series, pos: int) -> float | None:
    """Share (0-100) of the earlier values, within the window, that are below today's. Earlier bars only."""
    if series is None or pos is None:
        return None
    today = _num(series.iloc[pos])
    if today is None:
        return None
    start = max(0, pos - DEFINITIONS["percentile_window"])
    past = pd.to_numeric(series.iloc[start:pos], errors="coerce").dropna()
    if len(past) < DEFINITIONS["percentile_min_history"]:
        return None
    below = (past < today).sum() + 0.5 * (past == today).sum()
    return float(100.0 * below / len(past))


def _components(row: pd.Series, frame: pd.DataFrame) -> tuple[dict, dict]:
    """(components, readings). A component is None when its inputs are missing; it never defaults to 0."""
    d = DEFINITIONS
    close, atr = _num(row.get("close")), _num(row.get("atr"))
    comps, readings = {}, {}
    usable_atr = atr if atr and atr > 0 else None

    # Trend: moving averages
    parts = []
    for length in d["ma_lengths"]:
        sma = _num(row.get(f"sma_{length}"))
        if sma is not None and close is not None:
            readings[f"vs_sma_{length}_pct"] = (close / sma - 1) * 100 if sma else None
            if usable_atr:
                parts.append(_tanh((close - sma) / (usable_atr * d["ma_scale_per_sqrt_length"] * math.sqrt(length))))
    comps["moving_averages"] = _mean(parts) if parts else None

    # Trend: Ichimoku (continuous: 0 inside the cloud, growing with distance outside it)
    span_a, span_b = _num(row.get("ichi_span_a")), _num(row.get("ichi_span_b"))
    tenkan, kijun = _num(row.get("ichi_tenkan")), _num(row.get("ichi_kijun"))
    ichi = []
    if None not in (span_a, span_b, close) and usable_atr:
        top, bottom = max(span_a, span_b), min(span_a, span_b)
        outside = close - top if close > top else close - bottom if close < bottom else 0.0
        ichi.append(_tanh(outside / (usable_atr * d["ichimoku_scale_atr"])))
        readings["cloud"] = "above" if close > top else "below" if close < bottom else "inside"
    if None not in (tenkan, kijun) and usable_atr:
        ichi.append(_tanh((tenkan - kijun) / (usable_atr * d["ichimoku_scale_atr"])))
    comps["ichimoku"] = _mean(ichi) if ichi else None

    # Trend: MACD, counted once (level and acceleration averaged; the histogram IS line minus signal)
    line_col, hist_col = _col(frame, "MACD_"), _col(frame, "MACDh_")
    macd_line = _num(row.get(line_col)) if line_col else None
    macd_hist = _num(row.get(hist_col)) if hist_col else None
    macd_parts = []
    if macd_line is not None and usable_atr:
        macd_parts.append(_tanh(macd_line / (usable_atr * d["macd_level_scale_atr"])))
        readings["macd"] = macd_line
    if macd_hist is not None and usable_atr:
        macd_parts.append(_tanh(macd_hist / (usable_atr * d["macd_accel_scale_atr"])))
        readings["macd_histogram"] = macd_hist
    comps["macd"] = _mean(macd_parts) if macd_parts else None

    # Trend: 7-day momentum, scaled by the asset's own volatility
    change_7d = _num(row.get("change_7d"))
    atr_pct = (usable_atr / close * 100) if usable_atr and close else None
    readings["change_7d"] = change_7d
    readings["atr_pct"] = atr_pct
    if change_7d is not None and atr_pct:
        expected = atr_pct * math.sqrt(d["momentum_days"])
        comps["momentum"] = _tanh(change_7d / expected)
    else:
        comps["momentum"] = None

    # Stretch: fixed, continuous maps of bounded oscillators (positive = stretched down = leans up for this view)
    rsi = _num(row.get("rsi"))
    readings["rsi"] = rsi
    comps["rsi"] = _clip((d["rsi_centre"] - rsi) / d["rsi_span"]) if rsi is not None else None
    stoch = _num(row.get("stoch_k"))
    readings["stoch_k"] = stoch
    comps["stochastic"] = _clip((d["stoch_centre"] - stoch) / d["stoch_span"]) if stoch is not None else None
    upper_col, lower_col = _col(frame, "BBU_"), _col(frame, "BBL_")
    upper = _num(row.get(upper_col)) if upper_col else None
    lower = _num(row.get(lower_col)) if lower_col else None
    if None not in (upper, lower, close) and upper > lower:
        position = (close - lower) / (upper - lower)
        readings["bb_position"] = position
        comps["bollinger"] = _clip((d["bb_centre"] - position) / d["bb_span"])
    else:
        comps["bollinger"] = None

    # Flow: only when the source really has volume (CoinGecko fallback coins do not)
    volume = _num(row.get("volume"))
    vol_avg = _num(row.get("vol_sma_20"))
    has_volume = bool(vol_avg and vol_avg > 0 and volume is not None)
    readings["volume_ratio"] = _num(row.get("volume_ratio")) if has_volume else None
    obv, obv_avg = _num(row.get("obv")), _num(row.get("obv_sma_20"))
    if has_volume and None not in (obv, obv_avg):
        comps["obv"] = _tanh((obv - obv_avg) / (vol_avg * math.sqrt(d["obv_scale_sqrt_days"])))
    else:
        comps["obv"] = None
    open_, high, low = _num(row.get("open")), _num(row.get("high")), _num(row.get("low"))
    ratio = readings["volume_ratio"]
    if has_volume and ratio is not None and None not in (open_, high, low, close):
        span = high - low
        body = (close - open_) / span if span > 0 else 0.0
        heavy = max(0.0, min(1.0, (ratio - 1.0) / (d["heavy_volume_full_at"] - 1.0)))
        comps["heavy_volume"] = _clip(heavy * body)
    else:
        comps["heavy_volume"] = None

    readings["adx"] = _num(row.get("adx"))
    readings["close"] = close
    return comps, readings


def _band(value: float | None, words: tuple[str, str, str, str, str]) -> str:
    if value is None:
        return "Not enough data"
    strong, band = DEFINITIONS["label_band_strong"], DEFINITIONS["label_band"]
    if value >= strong:
        return words[0]
    if value >= band:
        return words[1]
    if value > -band:
        return words[2]
    if value > -strong:
        return words[3]
    return words[4]


CLUSTER_WORDS = {
    "trend": ("Strong uptrend", "Uptrend", "No clear trend", "Downtrend", "Strong downtrend"),
    "stretch": ("Very stretched down", "Stretched down", "Not stretched", "Stretched up", "Very stretched up"),
    "flow": ("Volume strongly backing rises", "Volume backing rises", "Volume neutral",
             "Volume backing falls", "Volume strongly backing falls"),
}


# ----------------------------------------------------------------------------- the score

def score(frame: pd.DataFrame, kind: str, now: datetime | None = None) -> dict:
    """Readings, components, clusters, context and lenses for the last completed bar of `frame`.

    `frame` is the output of scoring.calculate_indicators (it may include today's unfinished bar; that bar
    is never scored). The result is JSON-friendly.
    """
    base = {"version": VERSION, "fingerprint": FINGERPRINT, "kind": kind}
    if frame is None or getattr(frame, "empty", True) or "close" not in frame.columns:
        return {**base, "status": "no_data", "message": "No price history"}
    pos = last_completed_position(frame.index, kind, now)
    if pos is None or pos < 14:
        return {**base, "status": "no_data", "message": "Not enough completed daily bars yet"}
    row = frame.iloc[pos]
    comps, readings = _components(row, frame)

    clusters = {}
    for key, spec in CLUSTERS.items():
        members = spec["components"]
        present = [comps[m] for m in members if comps.get(m) is not None]
        value = sum(present) / len(present) if present else None
        clusters[key] = {
            "value": value, "percent": percent(value), "label": _band(value, CLUSTER_WORDS[key]),
            "coverage": [len(present), len(members)], "hypothesis": spec["hypothesis"],
            "components": {m: {"value": comps.get(m), "percent": percent(comps.get(m))} for m in members},
        }

    # Context: never directional
    atr_pct_series = None
    if "atr" in frame.columns:
        atr_pct_series = pd.to_numeric(frame["atr"], errors="coerce") / pd.to_numeric(frame["close"], errors="coerce") * 100
    rsi_series = pd.to_numeric(frame["rsi"], errors="coerce") if "rsi" in frame.columns else None
    vol_pct = _percentile(atr_pct_series, pos) if atr_pct_series is not None else None
    readings["atr_pct_percentile"] = vol_pct
    readings["rsi_percentile"] = _percentile(rsi_series, pos) if rsi_series is not None else None
    adx = readings.get("adx")
    regime = None
    try:
        from regime import latest_regime

        regime = latest_regime(frame.iloc[: pos + 1])
    except Exception:
        regime = None
    warnings = []
    if clusters["flow"]["coverage"][0] == 0:
        warnings.append("No volume data from this source, so Flow is not available.")
    if _num(row.get("sma_200")) is None:
        warnings.append("Less than 200 days of history: the 200-day average is missing, so Trend uses fewer parts.")
    stock = not str(kind).lower().startswith("crypto")
    context = {
        "volatility": {
            "atr_pct": readings.get("atr_pct"), "percentile": vol_pct,
            "label": ("Higher than usual" if vol_pct is not None and vol_pct >= 80 else
                      "Lower than usual" if vol_pct is not None and vol_pct <= 20 else
                      "About usual" if vol_pct is not None else "Not enough history"),
            "validation": "volatility_stock" if stock else "volatility_crypto",
        },
        "trend_strength": {
            "adx": adx,
            "label": ("Strong" if adx is not None and adx >= DEFINITIONS["adx_strong"] else
                      "Weak" if adx is not None and adx < DEFINITIONS["adx_weak"] else
                      "Developing" if adx is not None else "Not enough data"),
        },
        "regime": regime,
        "participation": {"volume_ratio": readings.get("volume_ratio")},
        "warnings": warnings,
    }

    lenses = {}
    for key, weights in DEFINITIONS["lenses"].items():
        parts = [(w, clusters[c]["value"]) for c, w in weights.items() if clusters[c]["value"] is not None]
        total = sum(w for w, _ in parts)
        value = sum(w * v for w, v in parts) / total if parts and total else None
        lenses[key] = {"value": value, "percent": percent(value)}

    t, s = clusters["trend"]["value"], clusters["stretch"]["value"]
    level = DEFINITIONS["disagreement_level"]
    disagree = t is not None and s is not None and abs(t) >= level and abs(s) >= level and (t > 0) != (s > 0)

    as_of = pd.Timestamp(frame.index[pos])
    return {
        **base, "status": "ok", "as_of": str(as_of.date()), "unfinished_bar_skipped": pos < len(frame) - 1,
        "readings": readings, "clusters": clusters, "context": context, "lenses": lenses,
        "disagreement": disagree,
        "summary": summary(clusters, disagree),
    }


def summary(clusters: dict, disagree: bool) -> str:
    parts = [f"{CLUSTERS[k]['name']}: {clusters[k]['label'].lower()}" for k in CLUSTERS if clusters[k]["value"] is not None]
    text = "; ".join(parts) + "." if parts else "Not enough data."
    if disagree:
        text += " Trend and Stretch point opposite ways: trend-following and mean-reversion views disagree."
    return text


def flat_fields(result: dict) -> dict:
    """The few numbers tables, alerts and the digest use, by explicit name (there is no 'score')."""
    clusters = result.get("clusters") or {}
    return {
        "trend": (clusters.get("trend") or {}).get("percent"),
        "stretch": (clusters.get("stretch") or {}).get("percent"),
        "flow": (clusters.get("flow") or {}).get("percent"),
        "signals_version": result.get("version"),
        "signals_fingerprint": result.get("fingerprint"),
        "as_of": result.get("as_of"),
    }


def component_reading(key: str, readings: dict) -> str:
    """The plain-words reading behind a component, for the breakdown."""
    r = readings
    fmt = lambda v, d=1: "-" if v is None else f"{v:.{d}f}"
    if key == "moving_averages":
        bits = [f"{fmt(r.get(f'vs_sma_{n}_pct'))}% vs {n}-day" for n in DEFINITIONS["ma_lengths"]
                if r.get(f"vs_sma_{n}_pct") is not None]
        return ", ".join(bits) or "Not enough history"
    if key == "ichimoku":
        return f"Price {r.get('cloud', 'unknown')} the cloud"
    if key == "macd":
        return f"MACD {fmt(r.get('macd'), 3)}, histogram {fmt(r.get('macd_histogram'), 3)}"
    if key == "momentum":
        return f"{fmt(r.get('change_7d'))}% over 7 days (typical daily range {fmt(r.get('atr_pct'), 2)}%)"
    if key == "rsi":
        pct = r.get("rsi_percentile")
        return f"RSI {fmt(r.get('rsi'))}" + (f", higher than {pct:.0f}% of the past year" if pct is not None else "")
    if key == "stochastic":
        return f"%K {fmt(r.get('stoch_k'))}"
    if key == "bollinger":
        pos = r.get("bb_position")
        return "-" if pos is None else f"{pos * 100:.0f}% of the way from the lower to the upper band"
    if key == "obv":
        return "On-balance volume against its 20-day average"
    if key == "heavy_volume":
        ratio = r.get("volume_ratio")
        return "No volume data" if ratio is None else f"Volume {ratio:.2f}x its 20-day average"
    return ""
