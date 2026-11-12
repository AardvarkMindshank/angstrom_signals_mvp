"""
📸 Quick Snapshot, reworked (12 Nov 2026): your own picture at a glance, now that 🌊 Tides carries the macro view.

  1. 🌊 the Tides headline: tide, sea state and the next big event, one line (opens the Tides panel below).
  2. 🔻 your funnels: one tile each with how many assets hold each stage, the Candidates and Flagged, and what came
     in or left since your last visit (opens that funnel's table on its Candidates).
  3. 📈📉 strongest and weakest Trend in your own watchlist, one compact card per market (built in app.py, which has
     the logo and colour helpers).
  4. What changed since your last visit (app.py, _what_changed_html).

Nothing here touches Streamlit, so it is tested on its own (tests/test_snapshot_view.py). Every tile is a button with
data-pick, read by the app's click component.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

GREEN, RED, GREY = "#15803d", "#b91c1c", "#6b7280"
MARKET_WORDS = {"crypto": ("🪙", "Crypto"), "equity": ("🏛️", "Equities")}
DIRECTION_WORDS = {"long": "longs", "short": "shorts"}
_BUTTON = ("display:block;width:100%;margin:0;padding:0;border:none;background:transparent;text-align:left;"
           "cursor:pointer;font:inherit;color:inherit;")


def _e(text) -> str:
    return html.escape(str(text), quote=True)


# --------------------------------------------------------------------------------------------- 1. Tides headline

def next_event(now: datetime | None = None, days: int = 14) -> dict | None:
    """The next scheduled Fed, CPI or jobs day (tier 2 or a deadline flag) within two weeks, else the next of any."""
    import macro_calendar as mc

    now = now or datetime.now(timezone.utc)
    ahead = [e for e in mc.upcoming(now, days=days) if e["at"] >= now]
    majors = [e for e in ahead if e["tier"] in (2, "flag")]
    return (majors or ahead or [None])[0]


def tides_line(snap: dict | None, now: datetime | None = None) -> str:
    """One clickable line: 🌊 tide (plain words) · sea state · next big event ›. Empty when Tides has no reading."""
    import macro_calendar as mc
    import tides as td

    now = now or datetime.now(timezone.utc)
    t = (snap or {}).get("tide") or {}
    if t.get("status") != "ok" or t.get("label") not in td.TIDE_WORDS:
        return ""
    name, plain, icon = td.TIDE_WORDS[t["label"]]
    colour = {"in": GREEN, "out": RED}.get(t["label"], GREY)
    bits = [f"<span style='font-weight:700;color:{colour};'>{_e(icon)} {_e(name)}</span>"
            f"<span class='ang-kicker' style='margin:0;'>&nbsp;{_e(plain)}"
            + (f", {t.get('held_days')} days" if t.get("held_days") else "") + "</span>"]
    sea = (snap or {}).get("sea") or {}
    if sea.get("status") == "ok":
        bits.append(f"<span>⛵ Sea {_e(sea['state'])}</span>"
                    f"<span class='ang-kicker' style='margin:0;'>&nbsp;{_e(sea.get('plain', ''))}</span>")
    e = next_event(now)
    if e:
        bits.append(f"<span>{_e(mc.pennants(e['tier']) or '📅')} {_e(e.get('short') or e['name'])}</span>"
                    f"<span class='ang-kicker' style='margin:0;'>&nbsp;{_e(mc.when_words(e['at'], now))}</span>")
    sep = "<span style='opacity:.35;padding:0 4px;'>|</span>"
    tip = ("🌊 Tides: the macro picture (money and rates, safe havens, growth and credit, rotation) and the next "
           "scheduled event. Open the Tides panel for the currents and the waves. A description, not a forecast.")
    return (f"<button type='button' data-pick='tides' title='{_e(tip)}' style='{_BUTTON}'>"
            "<div class='ang-card' style='display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;"
            "padding-top:10px;padding-bottom:10px;'>"
            + sep.join(f"<span style='display:inline-flex;align-items:baseline;white-space:nowrap;'>{b}</span>"
                       for b in bits)
            + "<span style='margin-left:auto;opacity:.6;'>Tides ›</span></div></button>")


# ------------------------------------------------------------------------------------------------ 2. funnel tiles

def _names(names: list[str], limit: int = 6) -> str:
    shown = ", ".join(names[:limit])
    return shown + (f" and {len(names) - limit} more" if len(names) > limit else "")


def funnel_tiles(tiles: list[dict]) -> str:
    """The funnel tiles, side by side where there is room. Each opens its funnel's table on its Candidates.
    tile: {id, name, market, direction, paused, line, candidates, flagged, candidate_names, new, gone, seen}."""
    if not tiles:
        return ""
    out = ["<div class='ang-kicker' style='margin:2px 0 6px;'>🔻 Your funnels</div>",
           "<div style='display:flex;flex-wrap:wrap;gap:10px;'>"]
    for t in tiles:
        mark, market = MARKET_WORDS.get(t.get("market") or "crypto", MARKET_WORDS["crypto"])
        direction = DIRECTION_WORDS.get(t.get("direction"), t.get("direction") or "")
        kicker = f"{mark} {market} · {direction}" + (" · ⏸️ paused" if t.get("paused") else "")
        new, gone = t.get("new") or [], t.get("gone") or []
        badges = []
        if new:
            badges.append(f"<span title='{_e('New Candidates since your last visit: ' + _names(new))}' "
                          f"style='color:{GREEN};font-weight:700;'>＋{len(new)} new</span>")
        if gone:
            badges.append(f"<span title='{_e('No longer Candidates since your last visit: ' + _names(gone))}' "
                          f"style='color:{GREY};font-weight:700;'>－{len(gone)} left</span>")
        if not badges and t.get("seen"):
            badges.append(f"<span style='color:{GREY};'>no change</span>")
        cands = t.get("candidate_names") or []
        tip = (f"Open {t['name']} in its table, on its Candidates. "
               + (f"Candidates now: {_names(cands, 12)}. " if cands else "No Candidates right now. ")
               + "Stage counts: the pool, then the assets holding each stage in a row.")
        out.append(
            f"<button type='button' data-pick='{_e('funnel|' + str(t['id']) + '|' + t['name'])}' title='{_e(tip)}' "
            f"style='{_BUTTON}flex:1 1 230px;max-width:100%;'>"
            "<div class='ang-card' style='height:100%;box-sizing:border-box;'>"
            f"<div class='ang-kicker'>{_e(kicker)}</div>"
            "<div class='ang-title' style='font-size:1.05rem;margin:2px 0 6px;white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis;'>{_e(t['name'])}</div>"
            "<div style='display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;'>"
            f"<span style='font-weight:700;font-size:1.05rem;'>✅ {t.get('candidates', 0)}"
            "<span class='ang-kicker' style='margin:0;font-weight:400;'>&nbsp;Candidates</span></span>"
            f"<span style='font-weight:600;'>🚩 {t.get('flagged', 0)}"
            "<span class='ang-kicker' style='margin:0;font-weight:400;'>&nbsp;Flagged</span></span>"
            + "".join(badges) + "</div>"
            f"<div class='ang-kicker' style='margin:6px 0 0;'>{_e(t.get('line') or '')}</div>"
            "</div></button>")
    out.append("</div>")
    return "".join(out)


def no_funnels_tile(market: str = "crypto") -> str:
    """When the account has no funnels: one quiet tile that opens a table in Dynamic funnel, to copy a provided one."""
    tip = ("A funnel narrows the market down in stages by itself, to a short list of Candidates. Click to open the "
           "table in Dynamic funnel and make your own copy of a provided funnel.")
    return (f"<button type='button' data-pick='{_e('funnel_new|' + market)}' title='{_e(tip)}' style='{_BUTTON}'>"
            "<div class='ang-card' style='display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;"
            "padding-top:10px;padding-bottom:10px;'>"
            "<span style='font-weight:600;'>🔻 Your funnels</span>"
            "<span class='ang-kicker' style='margin:0;'>none yet: a funnel narrows the market to Candidates by "
            "itself</span><span style='margin-left:auto;opacity:.6;'>Make one ›</span></div></button>")


def candidate_changes(before: list[str] | None, now: list[str]) -> tuple[list[str], list[str]]:
    """(new, gone) Candidates against the last visit. No last visit: nothing is new."""
    if before is None:
        return [], []
    was, is_ = set(before), set(now)
    return [c for c in now if c not in was], [c for c in before if c not in is_]
