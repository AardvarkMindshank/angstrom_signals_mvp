"""Set cards: the provided Sets shown by trading idea, with long/short twins and timeframe versions on one card
(18 Nov 2026, agreed in the "Lattice simplified" mockup).

This only changes how the list is shown. Every card option still points at one of the existing provided Sets, so a
card dragged onto a scan or a funnel stage hands over exactly the Set it did before: nothing in scanning, studies
or the certified scoring changes. Card names stay in English, like every provided Set's name.
"""

from __future__ import annotations

from i18n import mark, t

import plans

# The five trading ideas, in order, with the plain-language purpose under each heading.
IDEAS = (
    ("trend", mark("Follow the trend"), mark("Ride a move that is already under way")),
    ("dip", mark("Buy the dip / sell the rally"), mark("Enter on a pause inside a trend")),
    ("breakout", mark("Breakouts"), mark("Catch the start of a new move")),
    ("turn", mark("Turning points"), mark("Spot a move running out of steam")),
    ("range", mark("Ranges"), mark("Trade the edges when there is no trend")),
)

TF_LABEL = {"1w": mark("Weekly"), "1d": mark("Daily"), "12h": "12h", "4h": "4h", "1h": "1h"}

# Cards that join several provided Sets. members: (direction or "", timeframe or "", provided key).
# The first member is what the card shows until the options are changed.
MERGED = (
    {"id": "ema", "idea": "trend", "name": "EMA 20 vs EMA 50",
     "line": mark("The 20-candle average above the 50-candle one for an uptrend, below it for a downtrend."),
     "members": [("long", "1d", "demo:ema_up_1d"), ("long", "1w", "demo:ema_up_1w"), ("long", "12h", "demo:ema_up_12h"),
                 ("long", "4h", "demo:ema_up_4h"), ("short", "1d", "demo:ema_down_1d"),
                 ("short", "1w", "demo:ema_down_1w"), ("short", "12h", "demo:ema_down_12h"),
                 ("short", "4h", "demo:ema_down_4h")]},
    {"id": "pullback", "idea": "dip", "name": "Pullback in a trend",
     "line": mark("The trend holds while price steps back towards its average."),
     "members": [("long", "", "demo:pullback"), ("short", "", "demo:rally")]},
    {"id": "entry1h", "idea": "dip", "name": "Pullback entry (1-hour)",
     "line": mark("On the 1-hour chart, price comes back to its average and momentum turns back with the trend."),
     "members": [("long", "", "demo:entry_long_1h"), ("short", "", "demo:entry_short_1h")]},
    {"id": "turn", "idea": "turn", "name": "Momentum turning",
     "line": mark("The daily trend holds, then short-term momentum turns back with it."),
     "members": [("long", "", "demo:turn_up_1d"), ("short", "", "demo:turn_down_1d")]},
    {"id": "wave", "idea": "turn", "name": "WaveTrend turned",
     "line": mark("The Sonar WaveTrend crosses back after a dip, inside the daily trend."),
     "members": [("long", "", "demo:wave_turn_up_1d"), ("short", "", "demo:wave_turn_down_1d")]},
    {"id": "divergence", "idea": "turn", "name": "Divergence on 2+ timeframes",
     "line": mark("Price makes a new extreme but momentum doesn't, on two or more timeframes."),
     "members": [("long", "", "demo:divergence_bullish_mtf"), ("short", "", "demo:divergence_bearish_mtf")]},
    {"id": "sonar", "idea": "turn", "name": "Sonar confluence",
     "line": mark("WaveTrend, money flow and markers agree across timeframes."),
     "members": [("long", "", "demo:sonar_long"), ("short", "", "demo:sonar_short")]},
)

# Single provided Sets and their idea, in the order they're listed.
SINGLE = (
    ("demo:alignment", "trend"), ("demo:btc_filter", "trend"), ("demo:agree", "trend"),
    ("demo:entry", "dip"),
    ("demo:breakout", "breakout"), ("demo:squeeze", "breakout"),
    ("demo:overextended", "turn"),
    ("demo:range_low", "range"), ("demo:near_support", "range"),
)

_ORDER = {"trend": ["demo:alignment", "ema", "demo:btc_filter", "demo:agree"],
          "dip": ["pullback", "entry1h", "demo:entry"],
          "breakout": ["demo:breakout", "demo:squeeze"],
          "turn": ["turn", "wave", "divergence", "sonar", "demo:overextended"],
          "range": ["demo:range_low", "demo:near_support"]}


def placed_keys() -> set[str]:
    return {m[2] for c in MERGED for m in c["members"]} | {k for k, _ in SINGLE}


def tag(entry_plan: str, user_plan: str) -> dict:
    """Plan facts for one list item: its plan, whether this account's plan includes it, and the label shown when
    it doesn't (PLUS or PRO, with the reason on hover)."""
    locked = not plans.includes(user_plan, entry_plan)
    return {"plan": entry_plan, "locked": locked,
            "tag": t(plans.LABEL[entry_plan]) if locked else "",
            "tag_colour": plans.COLOUR.get(entry_plan, ""),
            "tag_hover": t(plans.WHY.get(entry_plan, "")) if locked else ""}


def build(entries: list[dict], docs: dict, user_plan: str, display: str) -> dict:
    """The list as cards. entries: the library's Set entries (prism_board._set_entry), docs: key -> Set document.
    Returns {"ideas": [...], "mine": [...]} where each idea holds its cards, and a card holds its option members
    (each with the Set key a drag or + hands over). Items the plan doesn't include are left out when display is
    "hide", or marked locked for "grey"."""
    by_key = {e["key"]: e for e in entries}
    for e in entries:
        e.update(tag(plans.set_level(docs.get(e["key"])), user_plan))

    cards = {}
    for spec in MERGED:
        members = []
        for direction, tf, key in spec["members"]:
            e = by_key.get(key)
            if not e:
                continue
            if e["locked"] and display == "hide":
                continue
            members.append({"dir": direction, "tf": tf, "tf_label": t(TF_LABEL[tf]) if tf else "", "key": key})
        if not members:
            continue
        lead = by_key[members[0]["key"]]
        worst = max((by_key[m["key"]]["plan"] for m in members), key=lambda p: plans.RANK[p])
        best = min((by_key[m["key"]]["plan"] for m in members), key=lambda p: plans.RANK[p])
        cards[spec["id"]] = {
            "id": spec["id"], "name": spec["name"], "line": t(spec["line"]), "members": members,
            "dirs": sorted({m["dir"] for m in members if m["dir"]}, key=["long", "short"].index),
            "tfs": [tf for tf in ("1w", "1d", "12h", "4h", "1h") if any(m["tf"] == tf for m in members)],
            "more": lead.get("more"), "evidence": lead.get("evidence"), "icons": lead.get("icons"),
            **tag(best, user_plan), "plan_max": worst}
    for key, _idea in SINGLE:
        e = by_key.get(key)
        if not e or (e["locked"] and display == "hide"):
            continue
        cards[key] = {"id": key, "name": e["name"], "line": e.get("line") or "",
                      "members": [{"dir": "", "tf": "", "tf_label": "", "key": key}], "dirs": [], "tfs": [],
                      "more": e.get("more"), "evidence": e.get("evidence"), "icons": e.get("icons"),
                      **{k: e[k] for k in ("plan", "locked", "tag", "tag_colour", "tag_hover")}}

    ideas = []
    for key, title, sub in IDEAS:
        listed = [cards[c] for c in _ORDER[key] if c in cards]
        if listed:
            ideas.append({"key": key, "title": t(title), "sub": t(sub), "cards": listed})
    placed = placed_keys()
    loose = [e for e in entries if e.get("provided") and e["key"] not in placed
             and not (e["locked"] and display == "hide")]
    mine = [e for e in entries if not e.get("provided") and not (e["locked"] and display == "hide")]
    return {"ideas": ideas, "loose": [e["key"] for e in loose], "mine": [e["key"] for e in mine]}
