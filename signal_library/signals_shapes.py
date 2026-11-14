"""
📐 Chart shapes (14 Nov 2026): head and shoulders (and its inverse), double top and double bottom, found by code from
the confirmed swing points the structure signals use (swings.pivots: a swing is known only `right` candles later).

A shape goes through stages, and the signal reports where the latest one of each kind is:

* forming    the swing points are in place (the right shoulder, or the second top, is confirmed) and price has not
             yet closed through the neckline; it lapses after `wait` candles without a break;
* confirmed  a candle closed through the neckline (the usual trigger);
* failed     price closed back beyond the head (or beyond the tops) before or after the break: the shape did not hold;
* none       no such shape in the last `lookback` candles.

Each kind also reads candles ago since one was last confirmed (`lookback` = none in the window, as Sonar markers), so a
rule can say "an inverse head and shoulders confirmed in the last 3 candles", plus the neckline and the usual
"measured move" target (the head's distance from the neckline, projected from the break).

Every step uses only candles up to the one being judged, so the answer at a candle never changes when later candles
arrive. Descriptive readings, not forecasts; nothing is tuned on outcomes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import swings as sw
from .core import OBSERVATION, SCOPE_ASSET, TIMEFRAMES, Param, signal
from .signals_basic import closed_candles
from .signals_oscillators import _ok, _r

KINDS = ("head_shoulders", "inverse_head_shoulders", "double_top", "double_bottom")
WORDS = {
    "head_shoulders": "Head and shoulders (bearish): three peaks, the middle one highest; the break of the neckline under them",
    "inverse_head_shoulders": "Inverse head and shoulders (bullish): three troughs, the middle one lowest; the break of the neckline over them",
    "double_top": "Double top (bearish): two peaks at about the same price; the break below the low between them",
    "double_bottom": "Double bottom (bullish): two troughs at about the same price; the break above the high between them",
}
BEARISH = ("head_shoulders", "double_top")


def atr(frame: pd.DataFrame, length: int = 14) -> pd.Series:
    """Wilder's average true range."""
    prev = frame["close"].shift(1)
    tr = pd.concat([frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()],
                   axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def _alternating(points: list[dict]) -> list[dict]:
    """Swings alternating high, low, high…: of two in a row of one kind, the more extreme stays."""
    out: list[dict] = []
    for p in points:
        if out and out[-1]["kind"] == p["kind"]:
            better = p["price"] > out[-1]["price"] if p["kind"] == "high" else p["price"] < out[-1]["price"]
            if better:
                out[-1] = p
            continue
        out.append(p)
    return out


def _line(a: dict, b: dict):
    """Price on the straight line through two swings, at a candle index."""
    if b["index"] == a["index"]:
        return lambda i: a["price"]
    slope = (b["price"] - a["price"]) / (b["index"] - a["index"])
    return lambda i: a["price"] + slope * (i - a["index"])


def find_shapes(frame: pd.DataFrame, left: int = 5, right: int = 5, tolerance_atr: float = 1.0,
                max_span: int = 120, wait: int = 30) -> list[dict]:
    """Every shape whose last swing is confirmed by the last candle of `frame`, in time order. Each:
    {kind, points: [(index, price)…], neck: [(index, price), (index, price)], ready (index the last swing was
    confirmed), stage, confirmed_index or None, failed_index or None, neckline (at the break, or at the last candle),
    target}."""
    high, low, close = (frame[c].to_numpy(dtype=float) for c in ("high", "low", "close"))
    last = len(close) - 1
    rng = atr(frame).to_numpy()
    sw_ = _alternating(sw.pivots(high, low, left, right))
    out = []

    def judge(kind, points, neck_at, beyond, ready, extreme):
        """Walk forward from the candle the shape became known: the first close through the neckline confirms it,
        a close beyond `extreme` (the head, or the tops) fails it."""
        bull = kind not in BEARISH
        confirmed = failed = None
        for t in range(ready, last + 1):
            if confirmed is None and t - ready > wait:
                break                                      # no break in time: the shape lapsed
            c = close[t]
            if (c < extreme) if bull else (c > extreme):
                failed = t
                break
            if confirmed is None and ((c > neck_at(t)) if bull else (c < neck_at(t))):
                confirmed = t
        if failed is not None:
            stage = "failed"
        elif confirmed is not None:
            stage = "confirmed"
        else:
            stage = "forming" if last - ready <= wait else "lapsed"
        at = confirmed if confirmed is not None else failed if failed is not None else last
        neck = neck_at(at)
        target = max(0.0, neck - beyond) if not bull else neck + beyond     # a price never falls below zero
        out.append({"kind": kind, "points": [(p["index"], p["price"]) for p in points], "ready": ready,
                    "neck": [(points[1]["index"], neck_at(points[1]["index"])), (at, neck)], "stage": stage,
                    "confirmed_index": confirmed, "failed_index": failed, "neckline": neck, "target": target})

    for j in range(len(sw_)):
        # five swings: shoulder, trough, head, trough, shoulder (tops) or the mirror (bottoms)
        if j + 4 < len(sw_):
            a, b, h, d, e = sw_[j:j + 5]
            size = rng[h["index"]] if h["index"] < len(rng) and rng[h["index"]] == rng[h["index"]] else np.nan
            if size == size and size > 0 and e["index"] - a["index"] <= max_span:
                neck_at = _line(b, d)
                if a["kind"] == "high":
                    if (h["price"] - max(a["price"], e["price"]) >= 0.5 * size
                            and abs(a["price"] - e["price"]) <= tolerance_atr * size
                            and min(a["price"], e["price"]) > max(b["price"], d["price"])):
                        judge("head_shoulders", [a, b, h, d, e], neck_at, h["price"] - neck_at(h["index"]),
                              e["confirmed_index"], h["price"])
                else:
                    if (min(a["price"], e["price"]) - h["price"] >= 0.5 * size
                            and abs(a["price"] - e["price"]) <= tolerance_atr * size
                            and max(a["price"], e["price"]) < min(b["price"], d["price"])):
                        judge("inverse_head_shoulders", [a, b, h, d, e], neck_at, neck_at(h["index"]) - h["price"],
                              e["confirmed_index"], h["price"])
        # three swings: top, trough, top (or the mirror), at least `right` candles apart
        if j + 2 < len(sw_):
            a, b, e = sw_[j:j + 3]
            size = rng[b["index"]] if rng[b["index"]] == rng[b["index"]] else np.nan
            if (size == size and size > 0 and e["index"] - a["index"] <= max_span
                    and e["index"] - a["index"] >= 2 * right and abs(a["price"] - e["price"]) <= 0.5 * tolerance_atr * size):
                flat = lambda i, p=b["price"]: p            # noqa: E731  (the neckline is level at the middle swing)
                if a["kind"] == "high" and min(a["price"], e["price"]) - b["price"] >= size:
                    judge("double_top", [a, b, e], flat, max(a["price"], e["price"]) - b["price"], e["confirmed_index"],
                          max(a["price"], e["price"]))
                elif a["kind"] == "low" and b["price"] - max(a["price"], e["price"]) >= size:
                    judge("double_bottom", [a, b, e], flat, b["price"] - min(a["price"], e["price"]), e["confirmed_index"],
                          min(a["price"], e["price"]))
    return sorted(out, key=lambda s: (s["ready"], s["points"][0][0]))


SHAPE_PARAMS = {
    "left": Param(5, "int", 2, 20, doc="candles before a swing point that must be lower (peaks) / higher (troughs)"),
    "right": Param(5, "int", 2, 20, doc="candles after it needed to confirm it; this is the confirmation delay"),
    "tolerance_atr": Param(1.0, "float", 0.2, 3.0, doc="how far apart the shoulders may be, in ATRs (tops: half this)"),
    "max_span": Param(120, "int", 20, 400, doc="most candles from the first swing of a shape to its last"),
    "wait": Param(30, "int", 5, 120, doc="candles a shape stays forming without a break before it lapses"),
    "lookback": Param(50, "int", 5, 300, doc="candles searched; a shape not confirmed in them reads this number"),
}


@signal(
    id="shape.classic", version=1, name="Chart shapes", category="structure",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params=SHAPE_PARAMS,
    calculation=("Confirmed swing points (left/right candles, as the structure signals), kept alternating peak and "
                 "trough. Head and shoulders: peak, trough, higher peak (the head, at least 0.5 ATR above both "
                 "shoulders), trough, peak, the shoulders within tolerance_atr of each other and above both troughs; "
                 "the neckline joins the two troughs. Inverse: the mirror. Double top: two peaks within half of "
                 "tolerance_atr, at least 2 x right candles apart, at least 1 ATR above the trough between them, "
                 "which is the level neckline; double bottom: the mirror. A shape must span at most max_span candles. "
                 "From the candle its last swing is confirmed, candle by candle: a close through the neckline "
                 "within `wait` candles confirms it; a close beyond the head (or the tops) fails it, before or after "
                 "the break; with neither within `wait` candles it lapses. For each kind, the latest shape found in the last `lookback` candles gives stage (forming, "
                 "confirmed, failed, or none), neckline and target (the head's distance from the neckline, from the "
                 "break); confirmed_ago = candles since one of that kind was last confirmed (0 = the last closed "
                 "candle, `lookback` = none in the window). ATR = Wilder's 14."),
    interpretation=("Which classic chart shapes are on this timeframe and where they stand. Traders read a confirmed "
                    "head and shoulders or double top as a possible turn down, the inverse and the double bottom as a "
                    "possible turn up, with the measured move as a rough first target. Descriptive; not a forecast."),
    limitations=("Shapes are a matter of judgement: the rules here are one fixed reading of them, and two traders "
                 "draw them differently. Swings are known `right` candles late, so a shape is found late. Many "
                 "shapes fail. Needs about 60 closed candles."),
    polarity="inverse head and shoulders and double bottoms point up; head and shoulders and double tops point down",
)
def chart_shapes(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, 60)
    if failed:
        return failed
    lookback = params["lookback"]
    window = lookback + params["max_span"] + params["right"] + 40
    frame = frame.iloc[-window:]
    shapes = find_shapes(frame, params["left"], params["right"], params["tolerance_atr"], params["max_span"],
                         params["wait"])
    last = len(frame) - 1
    start = last - lookback + 1
    value = {}
    for kind in KINDS:
        mine = [s for s in shapes if s["kind"] == kind and s["ready"] >= start]
        latest = mine[-1] if mine else None
        stage = "none" if latest is None or latest["stage"] == "lapsed" else latest["stage"]
        confirmed = [s["confirmed_index"] for s in shapes if s["kind"] == kind and s["confirmed_index"] is not None
                     and s["confirmed_index"] >= start]
        value[f"{kind}_stage"] = stage
        value[f"{kind}_ago"] = int(last - max(confirmed)) if confirmed else int(lookback)
        value[f"{kind}_neckline"] = _r(latest["neckline"]) if latest and stage != "none" else None
        value[f"{kind}_target"] = _r(latest["target"]) if latest and stage != "none" else None
    return _ok(ctx, loaded, timeframe, frame, value, {**params, "shapes_found": len(shapes)})
