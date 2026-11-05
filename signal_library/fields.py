"""Field descriptions (docs/design/lattice_prism.md §4.3, extension E3).

For each described signal (id@version): every readable field path of its value, its type, its unit and, where the
calculation fixes it, its range. A path of "" means the value itself. A list index is written "*"
("support.*.distance_atr" describes "support.0.distance_atr").

This table documents existing outputs. No calculation reads it, so it is kept outside the certified calculation
files: changing it never changes a signal's result. The Group and Set validator uses it to refuse comparisons that
cannot make sense (a yes/no field against a number, a threshold outside a fixed range, a field that does not exist).
Signals not described here are checked structurally only, as before.
"""

from __future__ import annotations

NUMBER, LABEL, YESNO, EVENTS, OTHER = "number", "label", "yes/no", "events", "other"
TYPES = (NUMBER, LABEL, YESNO, EVENTS, OTHER)


def num(unit: str, low=None, high=None) -> dict:
    return {"type": NUMBER, "unit": unit, "range": [low, high]}


def label(*labels: str) -> dict:
    return {"type": LABEL, "unit": "label", "labels": list(labels)}


YES_NO = {"type": YESNO, "unit": "yes/no"}
EVENT_LIST = {"type": EVENTS, "unit": "events"}
STANDARD = num("standard score", -1, 1)
DIRECTION = label("up", "down", "mixed")


def _other(unit: str) -> dict:
    return {"type": OTHER, "unit": unit}


FIELDS: dict[str, dict[str, dict]] = {
    # ---- the ten dashboard components (library_completion.md §2)
    "ma.position@1": {
        "close": num("price", 0), "sma_50": num("price", 0), "sma_200": num("price", 0),
        "vs_sma_50_pct": num("% from the 50-period average", -100), "vs_sma_200_pct": num("% from the 200-period average", -100),
        "distance_atr_50": num("ATRs from the 50-period average"), "distance_atr_200": num("ATRs from the 200-period average"),
        "standard_score": STANDARD,
    },
    "ichimoku.position@1": {
        "cloud": label("above", "inside", "below"), "outside_cloud_atr": num("ATRs outside the cloud"),
        "tenkan_kijun_gap_atr": num("ATRs"), "span_a": num("price", 0), "span_b": num("price", 0),
        "tenkan": num("price", 0), "kijun": num("price", 0), "close": num("price", 0), "standard_score": STANDARD,
    },
    "macd.level@1": {"macd_line": num("price"), "macd_line_atr": num("ATRs"), "standard_score": STANDARD},
    "macd.acceleration@1": {"histogram": num("price"), "histogram_quarter_atr": num("quarter-ATRs"),
                            "standard_score": STANDARD},
    "move.seven_day@1": {"change_7d_pct": num("% change", -100), "atr_pct": num("% of price", 0),
                         "expected_7d_move_pct": num("% of price", 0), "move_in_expected_units": num("expected moves"),
                         "standard_score": STANDARD},
    "rsi.level@1": {"rsi": num("RSI (14)", 0, 100), "standard_score": STANDARD},
    "stochastic.level@1": {"stoch_k": num("Stochastic %K", 0, 100), "standard_score": STANDARD},
    "bollinger.position@1": {"position": num("0 = lower band, 1 = upper band"), "upper": num("price"),
                             "lower": num("price"), "close": num("price", 0), "standard_score": STANDARD},
    "obv.balance@1": {"obv": num("volume"), "obv_average_20": num("volume"), "has_volume": YES_NO,
                      "balance_in_scaled_volumes": num("scaled volumes"), "standard_score": STANDARD},
    "volume.heavy_candle@1": {"volume_ratio": num("× average volume", 0), "body_share_of_range": num("share of range", -1, 1),
                              "heaviness": num("heaviness", 0, 1), "standard_score": STANDARD},
    # ---- members of the other starters and the design examples
    "trend.direction@1": {"": DIRECTION},
    "momentum.direction@1": {"": DIRECTION},
    "volume.cmf@1": {"": num("Chaikin money flow", -1, 1)},
    "regime.observation@1": {
        "state": label("trending", "ranging", "transitional"), "direction": DIRECTION, "in_transition": YES_NO,
        "adx": num("ADX", 0, 100), "adx_change_5": num("ADX points"), "efficiency_ratio_20": num("ratio", 0, 1),
        "atr_pct": num("% of price", 0), "atr_pct_percentile": num("percentile", 0, 100), "band_width": num("ratio", 0),
        "band_width_percentile": num("percentile", 0, 100), "volatility": _other("label"),
    },
    "structure.swings@1": {"structure": DIRECTION, "swings": _other("list of swings"), "tentative": _other("swing")},
    "mtf.alignment@1": {
        "timeframes.*.trend": DIRECTION, "timeframes.*.momentum": DIRECTION, "timeframes.*.timeframe": _other("timeframe"),
        "timeframes.*.status": _other("status"), "trend_counts.up": num("timeframes", 0),
        "trend_counts.down": num("timeframes", 0), "trend_counts.mixed": num("timeframes", 0),
        "conflicts": _other("list"), "momentum_against_trend": _other("list"), "summary": _other("text"),
    },
    "structure.breaks@1": {"": EVENT_LIST},
    "ta.divergence.rsi@1": {"": EVENT_LIST},
    "ta.divergence.macd@1": {"": EVENT_LIST},
    "levels.zones@1": {
        "close": num("price", 0), "atr": num("price", 0),
        "support.*.distance_atr": num("ATRs from price", 0), "resistance.*.distance_atr": num("ATRs from price", 0),
        "support.*.distance_pct": num("% from price", 0), "resistance.*.distance_pct": num("% from price", 0),
        "support.*.touches": num("touches", 0), "resistance.*.touches": num("touches", 0),
        "support.*.mid": num("price", 0), "resistance.*.mid": num("price", 0),
    },
    # ---- sentiment (library_completion.md §4) and flows
    "sentiment.market@1": {"score": num("sentiment, −100 to +100", -100, 100), "change_7d": num("sentiment points", -200, 200),
                           "age_hours": num("hours", 0), "thin_news": YES_NO, "coverage": _other("label")},
    "sentiment.asset@1": {"score": num("sentiment, −100 to +100", -100, 100), "change_7d": num("sentiment points", -200, 200),
                          "age_hours": num("hours", 0), "thin_news": YES_NO, "coverage": _other("label")},
    "flows.btc_etf@1": {"latest_net_flow_usd": num("US$"), "sum_5_sessions_usd": num("US$"),
                        "sum_20_sessions_usd": num("US$"), "change_in_5_session_sum_usd": num("US$"),
                        "sessions_in_window": num("sessions", 0)},
}


def _pattern(path: str | None) -> str:
    return ".".join("*" if part.isdigit() else part for part in str(path or "").split(".")) if path else ""


def described(signal_key: str) -> bool:
    return signal_key in FIELDS


def field(signal_key: str, path: str | None) -> dict | None:
    """The description of one field, or None when the signal is not described or the path does not exist."""
    table = FIELDS.get(signal_key)
    if table is None:
        return None
    return table.get(_pattern(path))


def in_range(description: dict, value) -> bool:
    low, high = (description.get("range") or [None, None])
    return (low is None or value >= low) and (high is None or value <= high)


def scale_text(description: dict) -> str:
    """Plain words for the editor: "RSI (14), 0 to 100"."""
    if description["type"] != NUMBER:
        return description["unit"]
    low, high = description["range"]
    if low is not None and high is not None:
        return f"{description['unit']}, {low:g} to {high:g}"
    if low is not None:
        return f"{description['unit']}, at least {low:g}"
    return description["unit"]
