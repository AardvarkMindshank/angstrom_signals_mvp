"""Signal families (18 Nov 2026, agreed in the "Lattice simplified" mockup): family → signal → variant.

The 43 library signals are shown as 15 signals in 6 families, headed by the question each family answers. A
signal's variants are library signals in their own right (RSI and Stochastic are variants of Overbought /
oversold), so nothing about how a Group or Set is stored changes: picking a variant adds that library signal.
"""

from __future__ import annotations

from i18n import mark, t

import plans

# (family key, title, question, [(signal name, what it measures, [variant ids, the first is the default])])
FAMILIES = (
    ("trend", mark("Trend"), mark("Which way is it going, and how firmly?"), [
        (mark("Trend direction"), mark("Which way price is moving, and how firmly"),
         ["trend.direction", "mtf.alignment", "ichimoku.position"]),
        (mark("Moving averages"), mark("Price or a fast average against a slow one"),
         ["ma.pair", "ma.line", "ma.position"]),
    ]),
    ("momentum", mark("Momentum and stretch"), mark("Has it run too far, or is it turning?"), [
        (mark("Overbought / oversold"), mark("How far price has run"),
         ["rsi.level", "stochastic.level", "bollinger.position", "osc.stoch_rsi", "osc.stoch_ohlc4"]),
        (mark("MACD"), mark("Momentum from two averages and the gap between them"),
         ["macd.level", "macd.acceleration"]),
        (mark("Price action"), mark("The latest candles and the recent move"),
         ["candle.shape", "move.seven_day", "momentum.direction"]),
        (mark("Divergence"), mark("A new price extreme that momentum doesn't confirm"),
         ["ta.divergence.rsi", "ta.divergence.macd", "divergence.mtf"]),
        (mark("Sonar"), mark("WaveTrend, money flow and markers"),
         ["osc.wavetrend", "flow.money", "sonar.markers"]),
    ]),
    ("volume", mark("Volume and money flow"), mark("Is real money behind the move?"), [
        (mark("Volume"), mark("Is trading heavier than usual?"), ["volume.relative", "volume.heavy_candle"]),
        (mark("Money flow"), mark("Whether volume backs the rises or the falls"), ["obv.balance", "volume.cmf"]),
    ]),
    ("structure", mark("Structure"), mark("Where are the price levels that matter?"), [
        (mark("Support and resistance"), mark("Near a level where price turned before"), ["levels.zones"]),
        (mark("Market structure"), mark("Higher highs and lows, or the reverse"), ["structure.swings", "structure.breaks"]),
        (mark("Chart shapes"), mark("Head and shoulders, double tops and more"), ["shape.classic"]),
    ]),
    ("regime", mark("Regime and sentiment"), mark("What kind of market is it, and what is the news saying?"), [
        (mark("Headline sentiment"), mark("What the news is saying"), ["sentiment.asset", "sentiment.market"]),
        (mark("Regime and volatility"), mark("Trending or ranging, calm or wild"),
         ["regime.state", "volatility.atr_trend", "regime.observation"]),
    ]),
    ("positioning", mark("Positioning and flows"), mark("Where are other traders betting, and where is money moving?"), [
        (mark("Positioning and flows"), mark("Options, leverage and fund flows"),
         ["options.max_pain", "positioning.funding", "positioning.liquidation_levels", "positioning.liquidations",
          "positioning.long_short", "positioning.oi_price", "flows.btc_etf", "flows.stablecoin_supply"]),
    ]),
)


def all_ids() -> list[str]:
    return [i for _k, _t, _q, sigs in FAMILIES for _n, _w, ids in sigs for i in ids]


def build(catalogue: list[dict], user_plan: str, display: str) -> list[dict]:
    """The families for the editors' lists: [{key, title, question, signals: [{name, what, variants: [{id, name,
    plan, locked, tag, tag_colour, tag_hover}], plan, locked, tag...}]}]. Variants the plan doesn't include are left
    out when display is "hide", or marked locked for "grey"; a signal with no variant left is left out."""
    have = {s["id"]: s for s in catalogue}
    out = []
    for key, title, question, sigs in FAMILIES:
        signals = []
        for name, what, ids in sigs:
            variants = []
            for vid in ids:
                s = have.get(vid)
                if not s:
                    continue
                need = plans.signal_plan(vid)
                locked = not plans.includes(user_plan, need)
                if locked and display == "hide":
                    continue
                variants.append({"id": vid, "name": s["name"], "plan": need, "locked": locked,
                                 "tag": t(plans.LABEL[need]) if locked else "",
                                 "tag_colour": plans.COLOUR.get(need, ""),
                                 "tag_hover": t(plans.WHY.get(need, "")) if locked else ""})
            if not variants:
                continue
            best = min((v["plan"] for v in variants), key=lambda p: plans.RANK[p])
            locked = not plans.includes(user_plan, best)
            signals.append({"name": t(name), "what": t(what), "variants": variants, "plan": best, "locked": locked,
                            "tag": t(plans.LABEL[best]) if locked else "", "tag_colour": plans.COLOUR.get(best, ""),
                            "tag_hover": t(plans.WHY.get(best, "")) if locked else ""})
        if signals:
            out.append({"key": key, "title": t(title), "question": t(question), "signals": signals})
    return out
