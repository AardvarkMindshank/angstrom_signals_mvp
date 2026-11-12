"""
✨ AI Navigator on Tides: what it knows about the macro layer, and Today's AI Passage Plan.

Opened from the Tides panel, the Navigator (the app's one AI, advisor.py) is also given the day's Tides record, the
macro calendar, and this person's watchlist and funnels with their Candidates, so it can answer questions about the
currents and the tide from the readings themselves.

Today's AI Passage Plan is a fixed request with a fixed layout (Conditions, Weather on the route, Your vessels,
Hazards, Things to watch). One plan per person per day: it is saved in the logbook (navigator_logbook,
sql/2026-11-24_navigator_logbook.sql) with the readings it used, so it can be read again later and graded once its
horizon has passed. Without the table, the plan is kept for this browser session only.

House rules (the Tides brief): grounded in the readings only, plain trading words beside the sailing words,
descriptions and things to watch, never buy or sell; facts kept apart from expectations, which are marked as such.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import macro_calendar as mc
import tides as td

PASSAGE_KIND = "passage_plan"

TIDES_RULES = """Tides (the macro layer) is open with you. Its readings are below, with this person's watchlist and
funnels. When they ask about the currents, the tide, the sea state, the winds or the macro calendar:
- Answer only from these readings and events. Quote the reading behind each statement (for example "dollar: rising,
  band high, 30-day change +2.1%"). If something is not in the readings, say so; never bring in outside news, prices
  or forecasts.
- Use the sailing words with the plain trading words beside them: tide coming in (risk-supportive), slack (mixed),
  going out (risk-defensive); sea calm/moderate/rough/storm (low/normal/high/extreme volatility); headwind or
  tailwind for a market and direction.
- Keep facts and expectations apart. Facts are the readings. Anything about what may happen next is an expectation:
  label it "Expectation:" and say what would show it right or wrong, and over what time.
- Describe conditions, risks and what to watch. Never say buy, sell, enter or exit; the person decides.
- Macro conditions are slow: they frame risk, they do not time trades. Say so when someone asks about timing.
- How Tides works (fixed rules): each current's band is its level against its own last 5 years (very low to very
  high, 0-100); its pull is its 30-day move against the usual size of such a move (rising or falling, else flat);
  each family averages its voting currents; the Tide is the weighted sum (money and rates 30%, growth and credit 30%,
  safe havens 20%, rotation 20%): above +0.20 coming in, below -0.20 going out, else slack, and a new label counts
  only after 5 daily closes. Gold, oil and the yield curve are shown but do not vote. Sea state averages the VIX's and
  Bitcoin's volatility scores. Crypto Fear & Greed is shown on its own and never votes."""

PASSAGE_REQUEST = """Write Today's AI Passage Plan for me from the Tides readings, the calendar and my watchlist and
funnels. Use exactly these headings, short and plain, in this order:

**⚓ Conditions** - the tide and the sea in one or two lines, with the plain trading words, and how long the tide has
held or whether it is turning.
**🌦️ Weather on the route** - the scheduled events in the next 7 days, each with the currents it is most likely to
move and which of my assets or funnels lean on those currents.
**⛵ Your vessels** - my funnel Candidates first, then my watchlist assets, grouped by market: the wind for that market
and direction (tailwind, headwind or neither) and the currents behind it. Name the assets.
**🪨 Hazards** - currents running against my positions, events to be careful around, anything at an extreme band.
**🔭 Things to watch** - what would change the picture (for example the tide holding 5 closes, a current turning),
each as a labelled Expectation with what would show it right or wrong and over what time (5 or 20 trading days).

Facts from the readings only, each with the reading behind it. No buy or sell calls. Under 450 words, and always
finish every sentence."""


def _fmt(c: dict) -> str:
    if c.get("status") != "ok":
        return f"{c.get('name', c.get('key'))}: no data"
    ch = c.get("change_30")
    unit = "pts" if c.get("unit") == "pts" else "%"
    change = "n/a" if ch is None else f"{ch:+.2f} {unit}"
    pull = ("neutral" if c["direction"] not in ("rising", "falling")
            else "risk-supportive" if (c.get("contribution") or 0) > 0 else "risk-defensive")
    votes = "votes" if c.get("weight") else "shown, does not vote"
    return (f"{c['name']} ({td.FAMILIES[c['family']][0]}; {votes}): value {c.get('value'):.4g}, {c['direction']}, "
            f"{pull}, band {c['band']} ({c['score']:.0f}/100 against 5 years), 30-day change {change}, "
            f"7-day {('n/a' if c.get('change_7') is None else format(c['change_7'], '+.2f'))}, as of {c['as_of']}. "
            f"Measures: {td.SPEC[c['key']]['measures']}.")


def tides_context(snap: dict | None, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if not snap or (snap.get("tide") or {}).get("status") != "ok":
        return "Tides readings: not available right now."
    t, sea = snap["tide"], snap.get("sea") or {}
    name, plain, _ = td.TIDE_WORDS[t["label"]]
    lines = [f"Tides readings (computed {snap.get('computed_at', '')[:16]} UTC):",
             f"Tide: {name} ({plain}), score {t['score']:+.2f}, held {t['held_days']} trading days"
             + (f"; readings now point to {td.TIDE_WORDS[t['raw_label']][0].lower()} (not yet 5 closes)"
                if t.get("pending") else "") + ".",
             "Family pulls: " + ", ".join(f"{td.FAMILIES[f][0]} {v:+.2f}" for f, v in (t.get("families") or {}).items())]
    if sea.get("status") == "ok":
        lines.append(f"Sea state: {sea['state']} ({sea['plain']}), score {sea['score']:.0f}/100 (VIX score "
                     f"{sea.get('vix_score') or 0:.0f}, Bitcoin volatility score {sea.get('btc_vol_score') or 0:.0f}).")
    for w in (snap.get("winds") or {}).values():
        lines.append(f"Wind for {w['name']}: {w['wind']} (score {w['score']:+.2f}), led by "
                     + ", ".join(td.SPEC[k]["name"] for k in w["drivers"])
                     + (f"; pushing the other way: {', '.join(td.SPEC[k]['name'] for k in w['against'])}"
                        if w.get("against") else "") + ".")
    lines.append("Currents:")
    lines += [f"- {_fmt(c)}" for c in (snap.get("currents") or {}).values()]
    if snap.get("fear_greed") is not None:
        lines.append(f"Crypto Fear & Greed: {snap['fear_greed']:.0f}/100 (shown only, never votes).")
    if snap.get("btc_dominance") is not None:
        lines.append(f"Bitcoin share of the crypto market: {snap['btc_dominance']:.1f}% (shown only).")
    for key, words in (("long_30y", "30-year yield"), ("copper", "Copper")):
        e = (snap.get("extras") or {}).get(key)
        if e:
            lines.append(f"{words}: {e['value']:.3g}, 30-day change {e['change_30']:+.2f}.")
    lines.append("Macro calendar (New York times; a storm warning means an event is near, not a forecast):")
    for e in mc.upcoming(now, days=35):
        local = e["at"].astimezone(mc.NEW_YORK)
        lines.append(f"- {local:%a %d %b %H:%M}: {e['name']} ({e['reference']}), "
                     f"{'two pennants' if e['tier'] == 2 else 'one pennant' if e['tier'] == 1 else 'square flag'}, "
                     f"{mc.when_words(e['at'], now)}. {e['why']}")
    past = [e for e in mc.events() if e["at"] < now][-6:]
    if past:
        lines.append("Recent past events: " + "; ".join(f"{e['short']} {e['at']:%d %b %Y}" for e in past) + ".")
    return "\n".join(lines)


def portfolio_context(supabase, user_id: str, watchlist: dict | None) -> str:
    """The person's watchlist and funnels (with their Candidates), as plain lines."""
    lines = ["This person's watchlist:"]
    crypto = (watchlist or {}).get("crypto") or {}
    stock = (watchlist or {}).get("stock") or {}
    lines.append("- Crypto: " + (", ".join(f"{v}" for v in crypto.values()) or "none"))
    lines.append("- Equities: " + (", ".join(f"{v} ({k})" for k, v in stock.items()) or "none"))
    try:
        import funnel as fn
        import funnel_view as fv

        funnels = fv.load_funnels(supabase, user_id)
    except Exception:
        funnels = []
    if funnels:
        lines.append("This person's funnels:")
    for f in funnels:
        try:
            st = fv.states(f, fv.load_coins(supabase, f["id"]))
            cands = fv.coins_for("candidate", st)
            k = fn.counts(st, len(f["stages"]))
            direction = {"long": "longs", "short": "shorts"}.get(f.get("direction"), f.get("direction") or "")
            lines.append(f"- {f['name']} ({f.get('market') or 'crypto'} {direction}{', paused' if f.get('paused') else ''}): "
                         f"Candidates {', '.join(cands[:15]) or 'none'}; Flagged {k['flagged']}.")
        except Exception:
            lines.append(f"- {f.get('name')}: could not be read.")
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ the logbook

def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def saved_plan(supabase, user_id: str, day: str | None = None) -> dict | None:
    try:
        rows = (supabase.table("navigator_logbook").select("body, created_at, readings").eq("owner_id", user_id)
                .eq("kind", PASSAGE_KIND).eq("day", day or today()).order("created_at", desc=True).limit(1)
                .execute().data or [])
    except Exception:
        return None
    return rows[0] if rows else None


def save_plan(supabase, user_id: str, body: str, snap: dict | None, model: str) -> bool:
    t = (snap or {}).get("tide") or {}
    readings = {"computed_at": (snap or {}).get("computed_at"), "tide": t.get("label"), "score": t.get("score"),
                "sea": ((snap or {}).get("sea") or {}).get("state"), "winds": {k: w.get("wind") for k, w in
                                                                              ((snap or {}).get("winds") or {}).items()}}
    try:
        supabase.table("navigator_logbook").insert({"owner_id": user_id, "kind": PASSAGE_KIND, "day": today(),
                                                    "body": body, "readings": readings, "model": model}).execute()
        return True
    except Exception:
        return False


def complete(body: str) -> bool:
    """A plan ends with a finished sentence (or the cut-short note), never mid-sentence."""
    end = body.rstrip().rstrip("*_ ")
    return end.endswith((".", "!", "?", ")", "”", "\""))


def passage_plan(st, supabase, user_id: str, watchlist: dict | None, snap: dict | None, fresh: bool = False) -> str:
    """Today's plan: from the logbook when already written today, else written now (and saved)."""
    import advisor

    if not fresh:
        kept = saved_plan(supabase, user_id) or st.session_state.get("_passage_plan", {}).get(today())
        body = (kept["body"] if isinstance(kept, dict) else kept) if kept else ""
        if body and complete(body):
            return body                     # a plan that stopped mid-sentence (before 12 Nov's fix) is written again
    import signal_groups_inspector as gi

    saved = gi.saved_configs(supabase)[0] or []
    system = advisor.system_parts(saved, user_id, "tides",
                                  extra=TIDES_RULES + "\n\n" + tides_context(snap) + "\n\n"
                                  + portfolio_context(supabase, user_id, watchlist))
    body = advisor.ask([], PASSAGE_REQUEST, system, max_tokens=4000)
    if not save_plan(supabase, user_id, body, snap, advisor.MODEL):
        st.session_state.setdefault("_passage_plan", {})[today()] = body
    return body
