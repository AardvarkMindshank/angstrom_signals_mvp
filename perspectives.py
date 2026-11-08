"""
What a Group or Set looks at, as small icons worked out from its ingredients (no hand tagging), plus the plain
explanations and evidence status of the provided Groups and Sets (agreed plan, Stage A).

Every signal has a category; each category maps to one perspective icon. A part pinned to another asset (or a
market-wide reading) adds 🔭. The same rule works for anyone's own Groups and Sets.
"""

from __future__ import annotations

import signal_library as sl

# (key, icon, hover) in display order.
ICONS = (
    ("trend", "📈", "Looks at trend"),
    ("stretch", "🎯", "Looks at momentum or stretch"),
    ("volume", "🔊", "Looks at volume"),
    ("structure", "🧱", "Looks at support, resistance or structure"),
    ("volatility", "🌊", "Looks at volatility or regime"),
    ("other", "🔭", "Looks at another asset or the wider market"),
    ("sentiment", "💬", "Looks at news sentiment"),
    ("positioning", "🏦", "Looks at positioning or fund flows"),
)
ICON = {k: i for k, i, _ in ICONS}
HOVER = {k: h for k, _, h in ICONS}
CATEGORY = {"trend": "trend", "momentum": "stretch", "volume": "volume", "structure": "structure",
            "regime": "volatility", "sentiment": "sentiment", "positioning": "positioning", "flows": "positioning"}

EVIDENCE = {
    "untested": ("🔬", "Evidence: not yet studied. It describes conditions; nobody has checked what usually "
                       "followed them."),
}


def _refs(doc: dict):
    """(signal ref, pinned?) for every ingredient of a Group or Set document."""
    for m in doc.get("members") or []:
        yield m.get("ref") or {}, False
    for g in doc.get("groups") or []:
        pinned = bool(g.get("subject"))
        for m in (g.get("snapshot") or {}).get("members") or []:
            yield m.get("ref") or {}, pinned
    for s in doc.get("standalone") or []:
        yield s.get("ref") or {}, bool(s.get("subject"))


def of_doc(doc: dict | None) -> list[str]:
    """The perspective keys a Group or Set uses, in display order."""
    found = set()
    for ref, pinned in _refs(doc or {}):
        try:
            definition = sl.REGISTRY.get(ref["id"], ref.get("version", 1))
        except Exception:
            continue
        if definition.category in CATEGORY:
            found.add(CATEGORY[definition.category])
        if pinned or str(getattr(definition, "scope", "") or "").startswith("market:"):
            found.add("other")
    if (doc or {}).get("market_context"):
        found.add("other")
    return [k for k, _, _ in ICONS if k in found]


def icons(doc: dict | None) -> str:
    return " ".join(ICON[k] for k in of_doc(doc))


def chips(doc: dict | None) -> list[dict]:
    """[{icon, hover}] for screens that draw each icon with its own hover."""
    return [{"icon": ICON[k], "hover": HOVER[k], "key": k} for k in of_doc(doc)]


# ----------------------------------------------------------------------------------------------- explanations
# For each provided Group (starter alias) and Set (demo key): one line, then what it measures, why traders watch it,
# and what it does not prove. Plain words for someone new to trading.

EXPLAIN = {
    "starter:trend": (
        "Which way prices have been heading over weeks to months.",
        "Price against its 50- and 200-day averages, the Ichimoku cloud and the MACD line, averaged into one number "
        "from −100 (down) to +100 (up).",
        "Many traders prefer to trade in the direction of the bigger trend rather than against it.",
        "A trend describes the past. It can end at any time, and an up trend is not a forecast of further rises."),
    "starter:stretch": (
        "Extended versus its recent range: how far price has run up or down.",
        "RSI, Stochastic, Bollinger position, the 7-day move and the MACD histogram, from −100 (stretched down) to "
        "+100 (stretched up).",
        "Stretched moves often pause or pull back; traders use it to avoid chasing, or to look for dips.",
        "Stretched up is not a reason to sell: in strong trends prices can stay stretched for a long time."),
    "starter:flow": (
        "Whether volume is backing the moves.",
        "On-balance volume and heavy-volume days, from −100 (volume on down days) to +100 (volume on up days).",
        "A move with heavy volume behind it is often seen as more convincing than one on thin trading.",
        "Volume data differs between sources, and some coins report little or none."),
    "starter:trend-confirmation": (
        "Whether different views of the trend agree with each other.",
        "Trend direction on two timeframes, swing structure, momentum direction and regime, with three rules.",
        "Agreement between views makes a trend reading less likely to be a one-off.",
        "All its parts come from price, so agreement is consistency, not independent proof."),
    "starter:reversal-evidence": (
        "Clues that the current move may be running out of steam.",
        "RSI and MACD divergences, structure breaks, support and resistance and Chaikin Money Flow.",
        "Traders look for several clues together before treating a turn as possible.",
        "These clues arrive late by design and are often wrong in strong trends."),
    "demo:agree": (
        "Trend and Flow both Bullish (a teaching example).",
        "Yes when the daily Trend and Flow are both Bullish.",
        "Shows how a Set combines two Groups.",
        "A teaching example only."),
    "demo:entry": (
        "Trend up, not overstretched, news not negative (a teaching example).",
        "Yes when Trend is Bullish, Stretch is not stretched up, and headline sentiment is above −20.",
        "Shows how a Set mixes Groups with a single signal.",
        "A teaching example only."),
    "demo:pullback": (
        "A dip inside an uptrend.",
        "Yes when the daily Trend is +30 or more and the Stretch is −30 or lower.",
        "Buying dips in an uptrend is one of the most common approaches traders use.",
        "Some dips keep going and turn into downtrends; nothing here says which ones."),
    "demo:rally": (
        "A bounce inside a downtrend.",
        "Yes when the daily Trend is −30 or lower and the Stretch is +30 or more.",
        "Traders treat bounces in downtrends with caution: they often fade.",
        "Some bounces turn into new uptrends; nothing here says which ones."),
    "demo:alignment": (
        "The daily and weekly trends agree.",
        "Yes when the daily and the weekly Trend are both Bullish.",
        "A trend seen on two timeframes is often treated as more established.",
        "Weekly readings change slowly, so this can stay Yes after a turn has started."),
    "demo:breakout": (
        "An upward break in the last 3 days on heavy volume.",
        "Yes when price closed through recent structure upwards in the last 3 daily candles and the latest candle "
        "traded at least 1.5 times its usual volume.",
        "Breakouts with heavy volume are a classic setup: the volume suggests real interest behind the move.",
        "Many breakouts fail and fall back. One heavy-volume day can be news or a one-off."),
    "demo:squeeze": (
        "Unusually quiet trading.",
        "Yes when the Bollinger bands are narrower than on 80% of days in the past year.",
        "Quiet periods often come before bigger moves, so traders watch for the move that follows.",
        "It says nothing about which way the next move will go, or when."),
    "demo:range_low": (
        "Near the bottom of a sideways market.",
        "Yes when the market is ranging (no clear trend) and RSI is 30 or lower or Stochastic %K is 20 or lower.",
        "In sideways markets, traders look to buy near the bottom of the range and sell near the top.",
        "Ranges break. A ranging reading can change to a downtrend just as price looks cheap."),
    "demo:near_support": (
        "Close to a support level in a sideways market.",
        "Yes when the market is ranging and the nearest support zone is within half a typical daily move.",
        "Support zones are prices where falls have stopped before; traders watch how price behaves there.",
        "Support can break, and the zones are estimated from past swings."),
    "demo:btc_filter": (
        "Bitcoin itself is in an uptrend.",
        "Yes when Bitcoin's own daily Trend is Bullish, whatever asset is being looked at.",
        "Most coins tend to move with Bitcoin, so many crypto traders check Bitcoin first. Copy it into your own Sets "
        "as a market filter.",
        "Some coins move on their own news regardless of Bitcoin."),
    "demo:overextended": (
        "Price has run far up within its recent range.",
        "Yes when the Stretch is +50 or more.",
        "A caution against chasing: buying after a big run often means buying near a short-term top.",
        "It is not a signal to sell; strong trends can stay overextended for weeks."),
}


# ----------------------------------------------------------------------------------------------- what followed
# Results of the "What followed" study (what_followed.py, run in CI on saved prices before the hold-out). A result
# counts only for the exact Set it was worked out for: change the Set and it goes back to "not yet studied".

RESULTS_FILE = "data/what_followed.json"
VERDICT_MARK = {
    "Too few to judge": ("🔬", "What followed: too few past Yes moments to judge."),
    "No clear difference": ("⚖️", "What followed: no clear difference from comparable days."),
    "Some difference, not established": ("〰️", "What followed: some difference from comparable days, not "
                                                "established."),
    "Consistent difference": ("🧭", "What followed: a consistent difference from comparable days, in the past. "
                                    "Not a forecast."),
}
FILTER_MARK = ("🔗", "A filter for other Sets: it is not studied on its own.")
TYPICAL = ("A typical move is the asset's average daily range over the 20 candles before the Yes, so Bitcoin and "
           "Apple can be compared.")
_results: dict = {}


def results() -> dict:
    if "data" not in _results:
        import json
        from pathlib import Path

        try:
            _results["data"] = json.loads((Path(__file__).resolve().parent / RESULTS_FILE).read_text())
        except Exception:
            _results["data"] = {}
    return _results["data"]


def study_for(doc: dict | None, key: str | None = None) -> dict | None:
    """The study of this exact Set, or None (not studied, or the Set changed since)."""
    if not doc:
        return None
    import what_followed

    try:
        h = what_followed.logic_hash(doc)
    except Exception:
        return None
    sets = results().get("sets") or {}
    if key and key in sets and sets[key].get("hash") == h:
        return sets[key]
    return next((s for s in sets.values() if s.get("hash") == h), None)


def evidence(doc: dict | None, key: str | None = None) -> tuple[str, str]:
    s = study_for(doc, key)
    if s is None:
        return EVIDENCE["untested"]
    if s.get("type") == "filter":
        return FILTER_MARK
    return VERDICT_MARK.get(s.get("verdict"), EVIDENCE["untested"])


def _month(day: str) -> str:
    import pandas as pd

    return pd.Timestamp(day).strftime("%b %Y")


def _signed(v: float) -> str:
    return f"{v:+.1f}"


def followed_card(doc: dict | None, key: str | None = None) -> dict | None:
    """{title, lines, verdict, note} in plain words, or None when this Set has not been studied."""
    s = study_for(doc, key)
    if s is None:
        return None
    if s.get("type") == "filter":
        return {"title": "What followed", "lines": [], "verdict": None, "note": FILTER_MARK[1]}
    data = results()
    title = "What followed"
    lines = []
    if s.get("episodes"):
        title += f" · {_month(data.get('start', s['first']))} to {_month(data.get('through', s['last']))}"
        if s.get("coin_assets") is not None:
            lines.append(f"Studied on {s['coin_assets']} major coins and {s['share_assets']} large US shares.")
        lines.append(f"Turned Yes {s['episodes']} separate times, in {s['weeks']} different weeks.")
        n = s["plain"]
        if s["type"] == "neutral":
            lines.append(f"Size of the move after 10 candles, either way: {n['size']:.1f} typical moves on "
                         f"average (comparable days {n['size_usual']:.1f}).")
        else:
            lines.append(f"Rose a typical move before falling one: {n['gain_first']:.0%} of the time "
                         f"(comparable days {n['gain_first_usual']:.0%}); fell one first: {n['loss_first']:.0%} "
                         f"({n['loss_first_usual']:.0%}).")
            lines.append(f"After 10 candles: {_signed(n['move'])} typical moves on average (comparable days "
                         f"{_signed(n['move_usual'])}); finished higher {n['higher']:.0%} of the time "
                         f"({n['higher_usual']:.0%}).")
        top = ", ".join(f"{a.replace('-USD', '')} {v:.0%}" for a, v in s.get("top_assets") or [])
        lines.append(f"From {s['coins']} coin and {s['shares']} share episodes; most from {top}.")
        m = s.get("rests_on") or next(iter(s.get("tests") or {}), None)
        cons = ((s.get("tests") or {}).get(m) or {}).get("consistency") or {}
        if cons.get("checked"):
            periods = [c for c in cons["checked"] if c not in ("coins", "shares")]
            same = [c for c in cons["same_way"] if c in periods]
            markets = [c for c in ("coins", "shares") if c in cons["checked"]]
            both = all(c in cons["same_way"] for c in markets)
            lines.append(f"Pointed the same way in {len(same)} of {len(periods)} periods"
                         + (", and in both coins and shares." if markets and both else
                            ", but not in both coins and shares." if markets else "."))
    else:
        lines.append("It has not turned Yes often enough in the saved history to study.")
    return {"title": title, "lines": lines, "verdict": s.get("verdict"),
            "note": "Past patterns, measured from the close after each Yes, before costs. Not a forecast. " + TYPICAL}


def explain(key: str) -> dict | None:
    """{line, measures, why, not_proven, evidence: (icon, words)} for a provided Group or Set, else None."""
    if key not in EXPLAIN:
        return None
    line, measures, why, not_proven = EXPLAIN[key]
    return {"line": line, "measures": measures, "why": why, "not_proven": not_proven,
            "evidence": EVIDENCE["untested"]}


# ----------------------------------------------------------------------------------------------- data completeness

DATA = {"Complete": ("●", "Data complete"), "Partial": ("◐", "Some data missing"), "None": ("○", "No data")}


def data_mark(available: str | None) -> tuple[str, str]:
    """(icon, words) for a Prism row's availability ("Complete", "Partial…", "None…")."""
    word = str(available or "")
    for k, v in DATA.items():
        if word.startswith(k):
            return v
    return ("◐", word or "Data completeness unknown")
