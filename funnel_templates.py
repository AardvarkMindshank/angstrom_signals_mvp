"""
Ready-made funnels (a starting point to copy and change), written from a beta tester's description and a "BTC Hybrid" Pine
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
    it (80 or higher, back below 80). The tester's own daily read is momentum turning from oversold or overbought; his
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
    """The daily stage since 11 Nov 2026: the daily trend, and the tester's own daily read, WaveTrend turning back from an
    extreme in the last few days (his yellow arrows; it replaces the Stochastic stand-in). Longs: EMA 20 above EMA 50,
    WaveTrend crossed up while oversold within the last 5 daily closes, and the wave is still rising. Shorts mirror it
    (crossed down while overbought, still falling)."""
    up = direction == "long"
    side = "above" if up else "below"
    return {**BASE, "name": f"Daily {'uptrend, WaveTrend turned up' if up else 'downtrend, WaveTrend turned down'}",
            "purpose": (f"On the daily candles, EMA 20 {side} EMA 50, and WaveTrend turned "
                        f"{'up from oversold' if up else 'down from overbought'} within the last {TURN_WITHIN} daily "
                        f"closes and is still {'rising' if up else 'falling'}: a pullback inside the trend whose "
                        "momentum wave has turned back (the 📡 Sonar waves)."),
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
    out.update(trader_library())
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
            "WaveTrend (the 📡 Sonar momentum wave) turning from an extreme is a common way to time a re-entry "
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
    out.update(trader_explanations())
    return out


# The check timeframes of earlier provided funnels, so a copy of one is still recognised (and offered Update to the
# latest provided version) after the provided funnel gains or loses a stage.
EARLIER_SHAPES = {"crypto": [("1D", "12h", "4h", "1h")], "equity": []}


def trend_funnel(direction: str, market: str = "crypto") -> dict:
    """{name, direction, market, stages: [{label, timeframe, set_body, set_source}]} ready for funnel_save.
    Crypto: the daily trend (wide), the daily WaveTrend turn, 12-hour, 4-hour, then the 1-hour entry. Equities: weekly, daily, 4-hour (from the session open),
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
    if market != "equity":                 # crypto: a wide first stage, the daily trend alone (12 Nov 2026), so
        stages.insert(0, {"label": "Daily trend", "timeframe": "1D",      # coins build towards the WaveTrend turn
                          "set_body": trend_set("1D", direction),        # instead of the funnel being empty most days
                          "set_source": {"provided": library_key("1D", direction)}})
    stages.append({"label": "Entry (1-hour)", "timeframe": ENTRY_TIMEFRAME, "set_body": entry_set(direction),
                   "set_source": {"provided": library_key(None, direction)}})
    arrow = "▲" if direction == "long" else "▼"
    what = "equity" if market == "equity" else "crypto"
    return {"name": f"Trend {what} {'longs' if direction == 'long' else 'shorts'} {arrow}",
            "direction": direction, "market": market, "stages": stages}


# ------------------------------------------------------------------------------------- a trader's dip entry and top
# warning (19 Nov 2026), from a beta tester's description of his own process: money flow and the higher timeframes
# set the direction; momentum at an extreme on the 4-hour; then the 1-hour confluence (a big Sonar dot, the Stoch RSI
# pair crossing back from an extreme, a candle that closes the right way). The warning is the mirror at the top: daily
# momentum high, bearish divergence or a double top on the 4-hour, then the 1-hour top confluence. Shorts (and the
# "bottom warning") mirror every line.
# Tested 19 Nov 2026 on hourly candles of 30 coins (2021 to Oct 2024): as fixed rules these confluences were not
# followed by better moves than an ordinary hour. They find where the conditions line up, for a trader to look at.

def money_flow_set(direction: str, timeframe: str = "1D") -> dict:
    up = direction == "long"
    word = WORDS[timeframe]
    return {**BASE, "name": f"Money flowing {'in' if up else 'out'} ({word})",
            "purpose": f"On the {word} candles, the Sonar money flow is {'above' if up else 'below'} zero: more money "
                       f"{'coming in than going out' if up else 'going out than coming in'}, as the green and red "
                       "money-flow area shows it.",
            "standalone": [_item("flow", "Money flow", "flow.money", timeframe)],
            "decision": {"version": 1, "rule": {"member": "flow", "field": "value",
                                                **({"gte": 0.01} if up else {"lte": -0.01})}}}


def htf_agree_set(direction: str) -> dict:
    up = direction == "long"
    return {**BASE, "name": f"Higher timeframes agree ({'up' if up else 'down'})",
            "purpose": f"The trend points {'up' if up else 'down'} on at least 2 of the 4-hour, daily and weekly "
                       "timeframes: most of the bigger picture agrees, without needing every one.",
            "standalone": [_item("mtf", "Timeframes agreeing", "mtf.alignment", "1D", set="position")],
            "decision": {"version": 1, "rule": {"member": "mtf", "field": f"trend_counts.{'up' if up else 'down'}",
                                                "gte": 2}}}


def momentum_extreme_set(direction: str, timeframe: str) -> dict:
    """long: momentum low (the dip); short: momentum high (the top)."""
    low = direction == "long"
    word = WORDS[timeframe]
    return {**BASE, "name": f"Momentum {'low' if low else 'high'} ({word})",
            "purpose": (f"On the {word} candles, momentum is at the {'bottom' if low else 'top'} of its range: the "
                        f"Stoch RSI curves are both {'low (20 or under)' if low else 'high (80 or over)'} or crossed "
                        f"{'up from both low' if low else 'down from both high'} in the last 3 candles, or the Sonar "
                        f"wave is {'oversold' if low else 'overbought'}."),
            "standalone": [_item("srsi", "Stoch RSI pair", "osc.stoch_rsi", timeframe),
                           _item("wave", "Sonar wave", "osc.wavetrend", timeframe)],
            "decision": {"version": 1, "rule": {"any": [
                {"member": "srsi", "field": "pair", "eq": "both_low" if low else "both_high"},
                {"member": "srsi", "field": "cross_up_from_low_ago" if low else "cross_down_from_high_ago", "lte": 2},
                {"member": "wave", "field": "zone", "eq": "oversold" if low else "overbought"}]}}}


def confluence_set(direction: str, timeframe: str = "1h") -> dict:
    """long: the bottom confluence; short: the top confluence."""
    low = direction == "long"
    word = WORDS[timeframe]
    return {**BASE, "name": f"{'Bottom' if low else 'Top'} confluence ({word})",
            "purpose": (f"On the {word} candles: a big {'green' if low else 'red'} Sonar dot in the last 3 candles, the "
                        f"Stoch RSI curves crossed {'up from both low' if low else 'down from both high'} in the last "
                        f"3, and the last candle closed {'green' if low else 'red'}. A trader's "
                        f"{'bottoming' if low else 'topping'} checklist; it finds the setup, it doesn't forecast it."),
            "standalone": [_item("marks", "Sonar markers", "sonar.markers", timeframe),
                           _item("srsi", "Stoch RSI pair", "osc.stoch_rsi", timeframe),
                           _item("candle", "Last candle", "candle.shape", timeframe, average=10)],
            "decision": {"version": 1, "rule": {"all": [
                {"member": "marks", "field": "big_green_dot_ago" if low else "big_red_dot_ago", "lte": 2},
                {"member": "srsi", "field": "cross_up_from_low_ago" if low else "cross_down_from_high_ago", "lte": 2},
                {"member": "candle", "field": "colour", "eq": "green" if low else "red"}]}}}


def turn_shape_set(direction: str, timeframe: str = "4h") -> dict:
    """long: bullish divergence or a double bottom (W); short: bearish divergence or a double top (M)."""
    low = direction == "long"
    word = WORDS[timeframe]
    shape = "double_bottom" if low else "double_top"
    return {**BASE, "name": f"{'Bullish divergence or double bottom' if low else 'Bearish divergence or double top'}",
            "purpose": (f"A {'bullish' if low else 'bearish'} divergence between price and WaveTrend on at least one of "
                        f"the daily, 12-hour, 4-hour and 1-hour timeframes, or a "
                        f"{'double bottom (W)' if low else 'double top (M)'} confirmed on the {word} candles in the "
                        "last 10 candles: signs a move is running out of steam."),
            "standalone": [_item("div", "Divergence across timeframes", "divergence.mtf", "1D", set="crypto",
                                 oscillator="wavetrend"),
                           _item("shape", "Chart shapes", "shape.classic", timeframe)],
            "decision": {"version": 1, "rule": {"any": [
                {"member": "div", "field": f"{'bullish' if low else 'bearish'}_count", "gte": 1},
                {"member": "shape", "field": f"{shape}_ago", "lte": 10}]}}}


TRADER_KEYS = {
    ("flow", "long"): "demo:flow_in_1d", ("flow", "short"): "demo:flow_out_1d",
    ("htf", "long"): "demo:htf_up", ("htf", "short"): "demo:htf_down",
    ("extreme_1D", "long"): "demo:mom_low_1d", ("extreme_1D", "short"): "demo:mom_high_1d",
    ("extreme_4h", "long"): "demo:mom_low_4h", ("extreme_4h", "short"): "demo:mom_high_4h",
    ("confluence", "long"): "demo:bottom_1h", ("confluence", "short"): "demo:top_1h",
    ("shape", "long"): "demo:div_or_w_4h", ("shape", "short"): "demo:div_or_m_4h",
}


def trader_library() -> dict[str, dict]:
    out = {}
    for direction in ("long", "short"):
        out[TRADER_KEYS[("flow", direction)]] = money_flow_set(direction)
        out[TRADER_KEYS[("htf", direction)]] = htf_agree_set(direction)
        out[TRADER_KEYS[("extreme_1D", direction)]] = momentum_extreme_set(direction, "1D")
        out[TRADER_KEYS[("extreme_4h", direction)]] = momentum_extreme_set(direction, "4h")
        out[TRADER_KEYS[("confluence", direction)]] = confluence_set(direction)
        out[TRADER_KEYS[("shape", direction)]] = turn_shape_set(direction)
    return out


def _stage(label: str, timeframe: str, kind: str, direction: str) -> dict:
    key = TRADER_KEYS[(kind, direction)]
    return {"label": label, "timeframe": timeframe, "set_body": trader_library()[key], "set_source": {"provided": key}}


def dip_funnel(direction: str, market: str = "crypto") -> dict:
    """Dip entry (long) / rally entry (short): daily money flow, the higher timeframes agreeing, 4-hour momentum at
    the extreme against the trend, then the 1-hour confluence."""
    up = direction == "long"
    stages = [_stage(f"Money {'in' if up else 'out'} (daily)", "1D", "flow", direction),
              _stage("Higher timeframes agree", "1D", "htf", direction),
              _stage(f"4-hour {'dip' if up else 'rally'}", "4h", "extreme_4h", direction),
              _stage("Entry (1-hour confluence)", "1h", "confluence", direction)]
    what = "equity" if market == "equity" else "crypto"
    return {"name": f"{'Dip' if up else 'Rally'} entry {what} {'▲' if up else '▼'}", "direction": direction,
            "market": market, "stages": stages}


def top_funnel(direction: str, market: str = "crypto") -> dict:
    """Top warning (short) / bottom warning (long): daily momentum at the extreme, divergence or a double top/bottom,
    then the 1-hour confluence. For holders, a nudge to tighten a stop or take some profit; for the other side, a
    possible entry."""
    top = direction == "short"
    stages = [_stage(f"Daily momentum {'high' if top else 'low'}", "1D", "extreme_1D", direction),
              _stage(f"Divergence or {'M' if top else 'W'} shape", "4h", "shape", direction),
              _stage(f"{'Top' if top else 'Bottom'} confluence (1-hour)", "1h", "confluence", direction)]
    what = "equity" if market == "equity" else "crypto"
    return {"name": f"{'Top' if top else 'Bottom'} warning {what} {'▼' if top else '▲'}", "direction": direction,
            "market": market, "stages": stages}


PROVIDED_FUNNELS = {"trend": trend_funnel, "dip": dip_funnel, "top": top_funnel}
FUNNEL_NAMES = {"trend": "Trend funnel", "dip": "Dip / rally entry funnel", "top": "Top / bottom warning funnel"}


def provided_funnel(kind: str, direction: str, market: str = "crypto") -> dict:
    return PROVIDED_FUNNELS.get(kind, trend_funnel)(direction, market)


def kind_of(stages: list[dict]) -> str:
    """Which provided funnel a funnel's stages came from (by their provided Set keys); trend when none matches."""
    keys = {str((s.get("set_source") or {}).get("provided") or "") for s in stages}
    trader = set(TRADER_KEYS.values())
    if keys & trader:
        top = {TRADER_KEYS[("extreme_1D", d)] for d in ("long", "short")} | \
              {TRADER_KEYS[("shape", d)] for d in ("long", "short")}
        return "top" if keys & top else "dip"
    return "trend"


def trader_explanations() -> dict[str, tuple[str, str, str, str]]:
    tested = ("Tested on hourly candles of 30 coins (2021 to Oct 2024): as a fixed rule it was not followed by "
              "better moves than an ordinary hour. Use it to find charts worth a look.")
    out = {}
    for d in ("long", "short"):
        up = d == "long"
        out[TRADER_KEYS[("flow", d)]] = (
            f"Money flowing {'in' if up else 'out'} on the daily candles.",
            f"Yes when the daily Sonar money flow is {'above' if up else 'below'} zero.",
            "Traders who read Market Cipher weigh money flow as much as momentum: strong money flow can keep an "
            "overbought market going.", "Money flow is computed from price and range, not from real order flow.")
        out[TRADER_KEYS[("htf", d)]] = (
            f"Most of the bigger picture points {'up' if up else 'down'}.",
            f"Yes when the trend is {'up' if up else 'down'} on at least 2 of the 4-hour, daily and weekly timeframes.",
            "Many traders want the higher timeframes on their side before looking for an entry, though not "
            "necessarily all of them.", "Trends on different timeframes change at different speeds; this lags turns.")
        for tf in ("1D", "4h"):
            out[TRADER_KEYS[(f"extreme_{tf}", d)]] = (
                f"{WORDS[tf].capitalize()} momentum at the {'bottom' if up else 'top'} of its range.",
                f"Yes when the {WORDS[tf]} Stoch RSI curves are both {'low' if up else 'high'} or crossed back in the "
                f"last 3 candles, or the Sonar wave is {'oversold' if up else 'overbought'}.",
                "Entering when momentum is at an extreme of its range, inside a trend, is a common timing approach.",
                "Momentum can stay at an extreme for a long time when the move is strong.")
        out[TRADER_KEYS[("confluence", d)]] = (
            f"The 1-hour {'bottom' if up else 'top'} checklist: dot, Stoch RSI and candle agree.",
            f"Yes when a big {'green' if up else 'red'} Sonar dot printed in the last 3 hourly candles, the Stoch RSI "
            f"crossed {'up from both low' if up else 'down from both high'} in the last 3, and the last candle "
            f"closed {'green' if up else 'red'}.",
            "A beta tester's own confluence for timing entries and exits on the shorter timeframes.", tested)
        out[TRADER_KEYS[("shape", d)]] = (
            f"Signs a {'fall' if up else 'rise'} is running out of steam.",
            f"Yes when {'bullish' if up else 'bearish'} divergence shows on at least one timeframe, or a "
            f"{'double bottom' if up else 'double top'} was confirmed in the last 10 four-hour candles.",
            "Divergence and M or W shapes are classic signs of exhaustion that many traders look for at the edges of "
            "a range.", "Divergence repeats in strong trends, and shapes are confirmed late.")
    return out
