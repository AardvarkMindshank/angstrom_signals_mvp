"""
Ready-made funnels (a starting point to copy and change), written from Drew's description and his "BTC Hybrid" Pine
script (10 Nov 2026):

* the narrowing stages: EMA 20 above EMA 50 on the daily, then the 12-hour, then the 4-hour (below, for shorts);
* the 1-hour entry check, as his script's entry rules without the parts a scan cannot know (his trade history and
  cool-down after a loss): the 1-hour EMA 20 above EMA 50; the candle pulled back to the EMA 20 and closed above it,
  or crossed back above it; momentum: a higher close than the candle before, or a green candle with a bigger body than
  usual (a Set compares with "at least", so a body exactly average also counts); volume at least 0.7 times its
  20-candle average. Shorts mirror every line.

Descriptions, not forecasts: nobody has tested what followed these answers.
"""

from __future__ import annotations

TIMEFRAMES = ("1D", "12h", "4h")             # crypto: daily, 12-hour, 4-hour
EQUITY_TIMEFRAMES = ("1W", "1D", "4h")        # equities trade 6.5 hours a day, so a 12-hour candle is the daily
LIBRARY_TIMEFRAMES = ("1W", "1D", "12h", "4h")
ENTRY_TIMEFRAME = "1h"
BASE = {"schema": "angstrom.set/1", "lineage_version": 3, "score": None, "market_context": [], "groups": []}


def _item(key: str, label: str, signal: str, timeframe: str, **params) -> dict:
    return {"key": key, "label": label, "role": "condition",
            "ref": {"id": signal, "version": 1, "timeframe": timeframe, "params": params}}


def trend_set(timeframe: str, direction: str) -> dict:
    up = direction == "long"
    word = WORDS[timeframe]
    return {**BASE, "name": f"EMA 20 {'above' if up else 'below'} EMA 50 ({word})",
            "purpose": f"On the {word} candles, the 20-candle EMA is {'above' if up else 'below'} the 50-candle EMA: "
                       f"{'an uptrend' if up else 'a downtrend'} as two averages see it.",
            "standalone": [_item("emas", "EMA 20 vs 50", "ma.pair", timeframe, kind="EMA", fast=20, slow=50)],
            "decision": {"version": 1, "rule": {"member": "emas", "field": "order",
                                                "eq": "fast_above" if up else "fast_below"}}}


TURN_WITHIN = 5          # daily closes
OVERSOLD, OVERBOUGHT = 20, 80


def turn_set(direction: str) -> dict:
    """The daily stage since 10 Nov 2026 (the trend alone let most coins through in a one-way market): the daily trend,
    and daily momentum turning back from an extreme against it in the last few days. Longs: EMA 20 above EMA 50, and
    the Stochastic %K was 20 or lower (oversold) within the last 5 daily closes and is back above 20 now. Shorts mirror
    it (80 or higher, back below 80). Drew's own daily read is momentum turning from oversold or overbought; his
    WaveTrend oscillator is not in the library yet, so the Stochastic stands in."""
    up = direction == "long"
    side = "above" if up else "below"
    extreme = ({"member": "stoch", "field": "stoch_k", "lte": OVERSOLD} if up
               else {"member": "stoch", "field": "stoch_k", "gte": OVERBOUGHT})
    back = ({"member": "stoch", "field": "stoch_k", "gte": OVERSOLD + 0.01} if up
            else {"member": "stoch", "field": "stoch_k", "lte": OVERBOUGHT - 0.01})
    return {**BASE, "name": f"Daily {'uptrend, momentum turning up' if up else 'downtrend, momentum turning down'}",
            "purpose": (f"On the daily candles, EMA 20 {side} EMA 50, and the Stochastic %K was "
                        f"{'20 or lower (oversold)' if up else '80 or higher (overbought)'} within the last "
                        f"{TURN_WITHIN} daily closes and is back {'above 20' if up else 'below 80'} now: a pullback "
                        f"inside the trend whose momentum has turned {'up' if up else 'down'} again."),
            "standalone": [_item("emas", "EMA 20 vs 50", "ma.pair", "1D", kind="EMA", fast=20, slow=50),
                           _item("stoch", "Stochastic %K", "stochastic.level", "1D")],
            "decision": {"version": 1, "rule": {"all": [
                {"member": "emas", "field": "order", "eq": "fast_above" if up else "fast_below"},
                {"sequence": {"first": extreme, "then": back, "within": TURN_WITHIN}}]}}}


def entry_set(direction: str, timeframe: str = ENTRY_TIMEFRAME) -> dict:
    up = direction == "long"
    side = "above" if up else "below"
    return {**BASE, "name": f"Pullback entry ({'long' if up else 'short'}, 1-hour)",
            "purpose": (f"On the 1-hour candles: EMA 20 {side} EMA 50; the candle came back to the EMA 20 and closed "
                        f"{side} it, or crossed back {side} it; momentum agrees (a {'higher' if up else 'lower'} close, "
                        f"or a {'green' if up else 'red'} candle at least its usual size); volume at least 0.7 times usual."),
            "standalone": [
                _item("emas", "EMA 20 vs 50", "ma.pair", timeframe, kind="EMA", fast=20, slow=50),
                _item("ema20", "EMA 20", "ma.line", timeframe, kind="EMA", length=20),
                _item("candle", "Last candle", "candle.shape", timeframe, average=10),
                _item("volume", "Relative volume", "volume.relative", timeframe),
            ],
            "decision": {"version": 1, "rule": {"all": [
                {"member": "emas", "field": "order", "eq": "fast_above" if up else "fast_below"},
                {"any": [{"member": "ema20", "field": "retest_from_above" if up else "retest_from_below", "eq": True},
                         {"member": "ema20", "field": "crossed_up" if up else "crossed_down", "eq": True}]},
                # momentum: a higher close, or a green candle at least its usual size. Written as two "any" lines
                # (higher or green) and (higher or big body), which is the same check in a shape the editor shows.
                {"any": [{"member": "candle", "field": "close_vs_previous", "eq": "higher" if up else "lower"},
                         {"member": "candle", "field": "colour", "eq": "green" if up else "red"}]},
                {"any": [{"member": "candle", "field": "close_vs_previous", "eq": "higher" if up else "lower"},
                         {"member": "candle", "field": "body_vs_average", "gte": 1}]},
                {"member": "volume", "gte": 0.7},
            ]}}}


WORDS = {"1W": "weekly", "1D": "daily", "12h": "12-hour", "4h": "4-hour", "1h": "1-hour"}


def wave_turn_set(direction: str) -> dict:
    """The daily stage since 11 Nov 2026: the daily trend, and Drew's own daily read, WaveTrend turning back from an
    extreme in the last few days (his yellow arrows; it replaces the Stochastic stand-in). Longs: EMA 20 above EMA 50,
    WaveTrend crossed up while oversold within the last 5 daily closes, and the wave is still rising. Shorts mirror it
    (crossed down while overbought, still falling)."""
    up = direction == "long"
    side = "above" if up else "below"
    return {**BASE, "name": f"Daily {'uptrend, WaveTrend turned up' if up else 'downtrend, WaveTrend turned down'}",
            "purpose": (f"On the daily candles, EMA 20 {side} EMA 50, and WaveTrend turned "
                        f"{'up from oversold' if up else 'down from overbought'} within the last {TURN_WITHIN} daily "
                        f"closes and is still {'rising' if up else 'falling'}: a pullback inside the trend whose "
                        "momentum wave has turned back (Market Cipher style)."),
            "standalone": [_item("emas", "EMA 20 vs 50", "ma.pair", "1D", kind="EMA", fast=20, slow=50),
                           _item("wave", "WaveTrend", "osc.wavetrend", "1D")],
            "decision": {"version": 1, "rule": {"all": [
                {"member": "emas", "field": "order", "eq": "fast_above" if up else "fast_below"},
                {"sequence": {"first": {"member": "wave", "field": "turned_up_from_oversold" if up
                                        else "turned_down_from_overbought", "eq": True},
                              "then": {"member": "wave", "field": "direction", "eq": "rising" if up else "falling"},
                              "within": TURN_WITHIN}}]}}}


def divergence_set(direction: str, at_least: int = 2) -> dict:
    up = direction == "long"
    word = "bullish" if up else "bearish"
    return {**BASE, "name": f"{word.title()} divergence on {at_least}+ timeframes",
            "purpose": (f"Regular or hidden {word} divergence between price swings and WaveTrend on at least "
                        f"{at_least} of the daily, 12-hour, 4-hour and 1-hour timeframes at once (crypto set; equities "
                        "read weekly, daily, 4-hour and 1-hour)."),
            "standalone": [_item("div", "Divergence across timeframes", "divergence.mtf", "1D", set="crypto",
                                 oscillator="wavetrend")],
            "decision": {"version": 1, "rule": {"member": "div", "field": f"{word}_count", "gte": at_least}}}


def library_key(timeframe: str | None, direction: str) -> str:
    """The provided-library key of a funnel stage's Set (prism.library_sets embeds exactly these bodies)."""
    if timeframe == "wave":
        return f"demo:wave_turn_{'up' if direction == 'long' else 'down'}_1d"
    if timeframe == "divergence":
        return f"demo:divergence_{'bullish' if direction == 'long' else 'bearish'}_mtf"
    if timeframe == "turn":
        return f"demo:turn_{'up' if direction == 'long' else 'down'}_1d"
    if timeframe is None:
        return f"demo:entry_{direction}_1h"
    return f"demo:ema_{'up' if direction == 'long' else 'down'}_{timeframe.lower()}"


def library() -> dict[str, dict]:
    out = {}
    for direction in ("long", "short"):
        for tf in LIBRARY_TIMEFRAMES:
            out[library_key(tf, direction)] = trend_set(tf, direction)
        out[library_key(None, direction)] = entry_set(direction)
        out[library_key("turn", direction)] = turn_set(direction)
        out[library_key("wave", direction)] = wave_turn_set(direction)
        out[library_key("divergence", direction)] = divergence_set(direction)
    return out


def explanations() -> dict[str, tuple[str, str, str, str]]:
    """Perspectives (perspectives.EXPLAIN) for each provided funnel Set: what, the rule, why traders look, caveat."""
    out = {}
    for direction in ("long", "short"):
        up = direction == "long"
        for tf in LIBRARY_TIMEFRAMES:
            out[library_key(tf, direction)] = (
                f"An {'uptrend' if up else 'downtrend'} on the {WORDS[tf]} candles, as two averages see it.",
                f"Yes when the {WORDS[tf]} EMA 20 is {'above' if up else 'below'} the EMA 50.",
                "Many traders only trade in the direction of the trend, checked on several timeframes. It is a stage "
                "of the ready-made trend funnels.",
                "Averages lag: the trend may already be turning when this changes, and in sideways markets it flips "
                "back and forth.")
        out[library_key(None, direction)] = (
            f"A pullback {'buy' if up else 'sell'} setup on the 1-hour candles.",
            f"Yes when the 1-hour EMA 20 is {'above' if up else 'below'} the EMA 50, the candle came back to the EMA 20 "
            f"and closed {'above' if up else 'below'} it (or crossed back), momentum agrees and volume is at least 0.7 "
            "times usual.",
            "Waiting for a pullback to the average in an established trend is a common entry approach; these are the "
            "entry rules of a beta tester's own script. It is the last stage of the ready-made trend funnels.",
            "Pullbacks can turn into reversals, and one hourly candle says little on its own. Nobody has tested what "
            "followed these answers.")
        out[library_key("turn", direction)] = (
            f"A pullback inside a daily {'uptrend' if up else 'downtrend'} whose momentum has just turned back.",
            f"Yes when the daily EMA 20 is {'above' if up else 'below'} the EMA 50 and the daily Stochastic %K was "
            f"{'20 or lower' if up else '80 or higher'} within the last 5 closes and is back "
            f"{'above 20' if up else 'below 80'} now.",
            "Traders who follow the trend often wait for a pullback and enter when momentum turns back their way. "
            "It is the daily stage of the ready-made trend funnels.",
            "Momentum can turn back and forth several times before a move continues, and a pullback can become a "
            "reversal. Nobody has tested what followed these answers.")
        out[library_key("wave", direction)] = (
            f"A pullback inside a daily {'uptrend' if up else 'downtrend'} whose WaveTrend has just turned back.",
            f"Yes when the daily EMA 20 is {'above' if up else 'below'} the EMA 50 and WaveTrend crossed "
            f"{'up while oversold' if up else 'down while overbought'} within the last 5 closes and is still "
            f"{'rising' if up else 'falling'}.",
            "WaveTrend (the Market Cipher style oscillator) turning from an extreme is a common way to time a re-entry "
            "into a trend. It is the daily stage of the ready-made trend funnels.",
            "Oscillators can turn several times before a move continues. Nobody has tested what followed these "
            "answers.")
        out[library_key("divergence", direction)] = (
            f"{'Bullish' if up else 'Bearish'} momentum divergence on several timeframes at once.",
            f"Yes when at least 2 of the daily, 12-hour, 4-hour and 1-hour timeframes show a recent regular or "
            f"hidden {'bullish' if up else 'bearish'} divergence between price swings and WaveTrend.",
            "Divergence that shows up on more than one timeframe is what multi-timeframe traders look for before a "
            "turn (regular) or a continuation (hidden).",
            "Divergences are confirmed late (5 candles) and repeat in strong trends. Nobody has tested what followed "
            "these answers.")
    return out


def trend_funnel(direction: str, market: str = "crypto") -> dict:
    """{name, direction, market, stages: [{label, timeframe, set_body, set_source}]} ready for funnel_save.
    Crypto: daily, 12-hour, 4-hour, then the 1-hour entry. Equities: weekly, daily, 4-hour (from the session open),
    then the 1-hour entry."""
    if market == "equity":
        labels, tfs = ("Weekly", "Daily", "Shortlist (4-hour)"), EQUITY_TIMEFRAMES
    else:
        labels, tfs = ("Daily", "12-hour", "Shortlist (4-hour)"), TIMEFRAMES
    stages = [{"label": label, "timeframe": tf, "set_body": trend_set(tf, direction),
               "set_source": {"provided": library_key(tf, direction)}} for label, tf in zip(labels, tfs)]
    for st_ in stages:                     # the daily stage also needs momentum turning: WaveTrend (11 Nov 2026)
        if st_["timeframe"] == "1D":
            st_.update({"label": "Daily (trend + WaveTrend turn)", "set_body": wave_turn_set(direction),
                        "set_source": {"provided": library_key("wave", direction)}})
    stages.append({"label": "Entry (1-hour)", "timeframe": ENTRY_TIMEFRAME, "set_body": entry_set(direction),
                   "set_source": {"provided": library_key(None, direction)}})
    arrow = "▲" if direction == "long" else "▼"
    what = "equity" if market == "equity" else "crypto"
    return {"name": f"Trend {what} {'longs' if direction == 'long' else 'shorts'} {arrow}",
            "direction": direction, "market": market, "stages": stages}
