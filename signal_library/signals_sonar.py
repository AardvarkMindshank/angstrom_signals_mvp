"""
🛰️ Sonar markers and the Stoch RSI pair (14 Nov 2026), from Drew's charts.

Drew reads Market Cipher A's symbols on the price chart (the grey band of eight moving averages, a triangle for a
trend change, a yellow cross he calls manipulation, dots, crosses and diamonds), the big dots on the Cipher B strip,
and where the two Stoch RSI curves cross while both are high or both low. The open-source recreations (VuManChu
Cipher A and B) publish the formulas; the defaults below are theirs.

* sonar.markers     every marker as "candles ago" (0 = on the last closed candle), plus where price sits against the
                    band. "Printed in the last 3 candles" is a rule on these: candles ago is at most 2.
* osc.stoch_rsi     Stoch RSI of OHLC4 (as the chart panel draws it): %K, %D, whether both are high or both low, the
                    latest cross, and candles ago for each kind of cross.

A marker not found in the last `lookback` candles reads `lookback` ("not in the window"), a number rather than
nothing, so "not in the last N candles" (candles ago ≥ N) can be answered. Closed candles only. Descriptive readings,
not forecasts; nothing is tuned on outcomes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .core import INSUFFICIENT, OBSERVATION, SCOPE_ASSET, TIMEFRAMES, Param, SignalResult, signal
from .signals_basic import closed_candles
from .signals_oscillators import _ok, _r, _rsi_series, ema, money_flow, wavetrend

RIBBON = (5, 11, 15, 18, 21, 24, 28, 34)        # Cipher A's band of exponential averages of the close

# (field, plain words): every marker, in the order a chart legend shows them
MARKERS = (
    ("trend_turn_up", "Trend turn up (triangle): the 11 average crossed above the 15"),
    ("trend_turn_down", "Trend turn down: the 11 average crossed below the 15 (the triangle's mirror)"),
    ("long_cross", "Green dot: the 11 average crossed above the 34"),
    ("short_cross", "Red dot: the 34 average crossed above the 11"),
    ("red_cross", "Red cross: the 5 average crossed below the 11"),
    ("red_diamond", "Red diamond: the WaveTrend turned down"),
    ("blood_diamond", "Blood diamond: a red diamond and a red cross on the same candle"),
    ("yellow_cross", "Yellow cross: the WaveTrend turned down while RSI was 15 to 30 and money flowed out"),
    ("strength_candle", "Strength candle (yellow diamond): two green candles in a row opening above the 11 and 34"),
    ("big_green_dot", "Big green dot (Sonar strip): the wave turned up at or below −53"),
    ("big_red_dot", "Big red dot (Sonar strip): the wave turned down at or above +53"),
    ("snake_eyes_green", "Green snake eyes: two green wave dots close together (the wave turned up, dipped, turned up again)"),
    ("snake_eyes_red", "Red snake eyes: two red wave dots close together"),
)


def _up(a: pd.Series, b: pd.Series) -> pd.Series:
    return (a > b) & (a.shift(1) <= b.shift(1))


def _pair(dots: pd.Series, levels: pd.Series, gap: int, extreme) -> pd.Series:
    """True on a dot that comes within `gap` candles after the previous dot (both beyond `extreme` when set)."""
    dots = dots.fillna(False).astype(bool)
    if extreme is not None:
        dots = dots & extreme(levels)
    pos = pd.Series(np.where(dots.to_numpy(), np.arange(len(dots)), np.nan), index=dots.index)
    previous = pos.ffill().shift(1)
    return dots & ((pos - previous) <= gap)


def markers_frame(frame: pd.DataFrame, snake_gap: int = 4, snake_zone: str = "any") -> pd.DataFrame:
    """One row per candle: the band (ema_5 … ema_34) and a True/False column per marker (MARKERS). Shared with
    the chart overlay, so the chart and the Sets agree."""
    close, open_ = frame["close"], frame["open"]
    e = {n: ema(close, n) for n in RIBBON}
    # Cipher A's WaveTrend (VuManChu A: channel 9, average 13, signal 3) for the diamonds and the yellow cross
    wa = wavetrend(frame, 9, 13, 3)
    a1, a2 = wa["wt1"], wa["wt2"]
    red_diamond = (a1 < a2) & (a1.shift(1) >= a2.shift(1))
    red_cross = _up(e[11], e[5])
    rsi = _rsi_series(frame, 14)
    flow = money_flow(frame, 60, 150.0, 0.0)
    yellow = red_diamond & (a2 > -80) & (a2 < 45) & (rsi > 15) & (rsi < 30) & (flow < -5)
    green = close > open_
    strength = ((open_ > e[11]) & (open_ > e[34]) & green & green.shift(1, fill_value=False)
                & ~red_diamond & ~red_cross)
    # Cipher B's big dots, the same wave as the 📡 Sonar strip and osc.wavetrend (9, 12, 3; ±53)
    wb = wavetrend(frame, 9, 12, 3)
    b1, b2 = wb["wt1"], wb["wt2"]
    out = {f"ema_{n}": e[n] for n in RIBBON}
    out.update({
        "trend_turn_up": _up(e[11], e[15]), "trend_turn_down": _up(e[15], e[11]),
        "long_cross": _up(e[11], e[34]), "short_cross": _up(e[34], e[11]),
        "red_cross": red_cross, "red_diamond": red_diamond, "blood_diamond": red_diamond & red_cross,
        "yellow_cross": yellow, "strength_candle": strength,
        "big_green_dot": _up(b1, b2) & (b2 <= -53), "big_red_dot": _up(b2, b1) & (b2 >= 53),
        # Snake eyes: two of the strip's wave dots of one colour close together (traders' name, no fixed rule;
        # the gap and whether both must be beyond ±53 are settings)
        "snake_eyes_green": _pair(_up(b1, b2), b2, snake_gap, (lambda x: x <= -53) if snake_zone == "extreme" else None),
        "snake_eyes_red": _pair(_up(b2, b1), b2, snake_gap, (lambda x: x >= 53) if snake_zone == "extreme" else None),
    })
    return pd.DataFrame(out, index=frame.index)


def candles_ago(flags: pd.Series, lookback: int) -> int:
    """Candles since the last True in the last `lookback` rows (0 = the last row); `lookback` when there is none."""
    recent = flags.iloc[-lookback:].fillna(False).astype(bool).to_numpy()
    hits = np.flatnonzero(recent)
    return int(len(recent) - 1 - hits[-1]) if len(hits) else int(lookback)


LOOKBACK = Param(50, "int", 5, 300, doc="candles searched for each marker; one not found reads this number")


@signal(
    id="sonar.markers", version=1, name="Sonar markers", category="momentum",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"lookback": LOOKBACK,
            "snake_gap": Param(4, "int", 1, 20, doc="snake eyes: the second dot comes at most this many candles after "
                                                   "the first"),
            "snake_zone": Param("any", "choice", choices=("any", "extreme"),
                                doc="snake eyes: any two dots, or only dots beyond ±53 (oversold / overbought)")},
    calculation=("Closed candles. Band: exponential averages of the close over 5, 11, 15, 18, 21, 24, 28 and 34 "
                 "candles. Markers (the published open-source formulas): trend turn up = EMA 11 crosses above EMA 15 "
                 "(down: below); long cross = EMA 11 above EMA 34; short cross = EMA 34 above EMA 11; red cross = "
                 "EMA 5 below EMA 11; red diamond = WaveTrend (9, 13, 3) WT1 crosses below WT2; blood diamond = red "
                 "diamond and red cross together; yellow cross = red diamond with WT2 between −80 and 45, RSI 14 "
                 "between 15 and 30 and money flow (SMA 60 of (close − open) / range × 150) below −5; strength "
                 "candle = open above EMA 11 and EMA 34, this and the previous candle green, no red diamond or red "
                 "cross. Big green / red dot (the Sonar strip): WaveTrend (9, 12, 3) crosses up "
                 "with WT2 at or below −53 / down at or above +53. Snake eyes = a WaveTrend (9, 12, 3) cross of one direction "
                 "(a wave dot) at most snake_gap candles after the previous one of that direction (both beyond ±53 "
                 "when snake_zone is extreme). Each marker reads candles ago: 0 = on the last "
                 "closed candle, `lookback` = not in the last `lookback` candles. band = above when the close is "
                 "above every average, below when below every one, else inside; band_order = rising when each "
                 "average is above the next slower one, falling when below, else mixed."),
    interpretation=("Which of the symbols traders read on the price chart (and the Sonar strip's big dots) were printed, and "
                    "how recently, so a rule can say \"a big green dot in the last 3 candles\". A yellow cross is a warning of a sharp flush, not proof of manipulation. "
                    "Descriptive; not a forecast."),
    limitations=("Recreations of a paid, closed indicator: they may differ from it on some candles. Moving-average "
                 "crosses repeat often in sideways markets and on short timeframes. Needs about 70 closed candles."),
    polarity="trend turns up, green dots and strength candles point up; red marks and yellow crosses point down",
)
def sonar_markers(ctx, timeframe, params):
    lookback = params["lookback"]
    frame, loaded, failed = closed_candles(ctx, timeframe, 70)
    if failed:
        return failed
    mk = markers_frame(frame, params["snake_gap"], params["snake_zone"])
    last = mk.iloc[-1]
    close = float(frame["close"].iloc[-1])
    band = [_r(last[f"ema_{n}"]) for n in RIBBON]
    if None in band:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["The band is not ready yet."])
    position = "above" if close > max(band) else "below" if close < min(band) else "inside"
    order = ("rising" if all(a > b for a, b in zip(band, band[1:])) else
             "falling" if all(a < b for a, b in zip(band, band[1:])) else "mixed")
    value = {f"{name}_ago": candles_ago(mk[name], lookback) for name, _words in MARKERS}
    value.update({"band": position, "band_order": order, "close": _r(close)})
    return _ok(ctx, loaded, timeframe, frame, value, {**params, "band": dict(zip(map(str, RIBBON), band))})


# ----------------------------------------------------------------------------------------------- Stoch RSI pair

def stoch_rsi_frame(frame: pd.DataFrame, rsi_length: int = 14, stoch_length: int = 14, k: int = 3,
                    d: int = 3) -> pd.DataFrame:
    """Stoch RSI with RSI source OHLC4 (TradingView's setting Drew uses, and the chart panel's): %K and %D."""
    src = (frame["open"] + frame["high"] + frame["low"] + frame["close"]) / 4
    delta = src.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / rsi_length, adjust=False, min_periods=rsi_length).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / rsi_length, adjust=False, min_periods=rsi_length).mean()
    rsi = (100 - 100 / (1 + gain / loss.replace(0, np.nan))).where(loss != 0, 100.0).where(gain.notna())
    low, high = rsi.rolling(stoch_length).min(), rsi.rolling(stoch_length).max()
    raw = 100 * (rsi - low) / (high - low).replace(0, np.nan)
    k_line = raw.rolling(k).mean()
    return pd.DataFrame({"k": k_line, "d": k_line.rolling(d).mean()}, index=frame.index)


@signal(
    id="osc.stoch_rsi", version=1, name="Stoch RSI pair (OHLC4)", category="momentum",
    output=OBSERVATION, unit="mixed (labelled fields)", scope=SCOPE_ASSET, timeframes=TIMEFRAMES, requires=("candles",),
    params={"rsi_length": Param(14, "int", 3, 100, doc="RSI length"),
            "stoch_length": Param(14, "int", 3, 100, doc="candles in the RSI's high-low range"),
            "smooth_k": Param(3, "int", 1, 20, doc="smoothing of %K"),
            "smooth_d": Param(3, "int", 1, 20, doc="%D: the average of %K"),
            "high": Param(80, "int", 50, 100, doc="both curves at or above this: both high"),
            "low": Param(20, "int", 0, 50, doc="both curves at or below this: both low"),
            "lookback": LOOKBACK},
    calculation=("RSI (Wilder) of OHLC4 = (open + high + low + close) / 4; its position in its own range over "
                 "stoch_length candles, 0 to 100, smoothed into %K (SMA smooth_k) and %D (SMA of %K, smooth_d). pair = "
                 "both_high when %K and %D are both at or above `high`, both_low when both at or below `low`, else "
                 "apart. cross = %K crossing %D on the last closed candle. Candles ago (0 = the last closed candle, "
                 "`lookback` = none in the window) for: any cross up, any cross down, a cross up while both were low "
                 "(on the cross candle or the one before), a cross down while both were high."),
    interpretation=("Where the two Stoch RSI curves sit and when they last crossed, the way Drew reads them: a cross "
                    "up from both low, or down from both high, then a look up the chart for a printed dot. "
                    "Descriptive; not a forecast."),
    limitations="Pinned near 0 or 100 in strong trends, where crosses repeat. Needs about 40 closed candles.",
    polarity="crosses up from both low point up",
)
def osc_stoch_rsi(ctx, timeframe, params):
    frame, loaded, failed = closed_candles(ctx, timeframe, params["rsi_length"] + params["stoch_length"]
                                           + params["smooth_k"] + params["smooth_d"] + 4)
    if failed:
        return failed
    s = stoch_rsi_frame(frame, params["rsi_length"], params["stoch_length"], params["smooth_k"], params["smooth_d"])
    k, d = s["k"], s["d"]
    kl, dl = _r(k.iloc[-1], 2), _r(d.iloc[-1], 2)
    if kl is None or dl is None or _r(k.iloc[-2]) is None or _r(d.iloc[-2]) is None:
        return SignalResult(ref={}, subject=ctx.subject, status=INSUFFICIENT, notes=["The Stoch RSI is not ready."])
    hi, lo, lookback = params["high"], params["low"], params["lookback"]
    up, down = _up(k, d), _up(d, k)
    both_low = (k <= lo) & (d <= lo)
    both_high = (k >= hi) & (d >= hi)
    near_low = both_low | both_low.shift(1, fill_value=False)
    near_high = both_high | both_high.shift(1, fill_value=False)
    value = {
        "k": kl, "d": dl,
        "pair": "both_high" if kl >= hi and dl >= hi else "both_low" if kl <= lo and dl <= lo else "apart",
        "cross": "up" if bool(up.iloc[-1]) else "down" if bool(down.iloc[-1]) else "none",
        "cross_up_ago": candles_ago(up, lookback), "cross_down_ago": candles_ago(down, lookback),
        "cross_up_from_low_ago": candles_ago(up & near_low, lookback),
        "cross_down_from_high_ago": candles_ago(down & near_high, lookback),
    }
    return _ok(ctx, loaded, timeframe, frame, value, {**params})
