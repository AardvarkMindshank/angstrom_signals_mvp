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

TIMEFRAMES = ("1D", "12h", "4h")
ENTRY_TIMEFRAME = "1h"
BASE = {"schema": "angstrom.set/1", "lineage_version": 3, "score": None, "market_context": [], "groups": []}


def _item(key: str, label: str, signal: str, timeframe: str, **params) -> dict:
    return {"key": key, "label": label, "role": "condition",
            "ref": {"id": signal, "version": 1, "timeframe": timeframe, "params": params}}


def trend_set(timeframe: str, direction: str) -> dict:
    up = direction == "long"
    word = {"1D": "daily", "12h": "12-hour", "4h": "4-hour", "1h": "1-hour"}[timeframe]
    return {**BASE, "name": f"EMA 20 {'above' if up else 'below'} EMA 50 ({word})",
            "purpose": f"On the {word} candles, the 20-candle EMA is {'above' if up else 'below'} the 50-candle EMA: "
                       f"{'an uptrend' if up else 'a downtrend'} as two averages see it.",
            "standalone": [_item("emas", "EMA 20 vs 50", "ma.pair", timeframe, kind="EMA", fast=20, slow=50)],
            "decision": {"version": 1, "rule": {"member": "emas", "field": "order",
                                                "eq": "fast_above" if up else "fast_below"}}}


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
                {"any": [{"member": "candle", "field": "close_vs_previous", "eq": "higher" if up else "lower"},
                         {"all": [{"member": "candle", "field": "colour", "eq": "green" if up else "red"},
                                  {"member": "candle", "field": "body_vs_average", "gte": 1}]}]},
                {"member": "volume", "gte": 0.7},
            ]}}}


def trend_funnel(direction: str) -> dict:
    """{name, direction, stages: [{label, timeframe, set_body, set_source}]} ready for funnel_save."""
    labels = ("Daily", "12-hour", "Shortlist (4-hour)")
    stages = [{"label": label, "timeframe": tf, "set_body": trend_set(tf, direction),
               "set_source": {"provided": f"funnel:trend:{tf}:{direction}"}} for label, tf in zip(labels, TIMEFRAMES)]
    stages.append({"label": "Entry (1-hour)", "timeframe": ENTRY_TIMEFRAME, "set_body": entry_set(direction),
                   "set_source": {"provided": f"funnel:entry:{direction}"}})
    arrow = "▲" if direction == "long" else "▼"
    return {"name": f"Trend {'longs' if direction == 'long' else 'shorts'} {arrow}", "direction": direction,
            "stages": stages}
