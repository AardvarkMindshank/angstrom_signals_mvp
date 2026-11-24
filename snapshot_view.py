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

from i18n import mark, t

import html
from datetime import datetime, timezone

GREEN, RED, GREY = "#15803d", "#b91c1c", "#6b7280"
MARKET_WORDS = {"crypto": ("🪙", mark("Crypto")), "equity": ("🏛️", mark("Equities"))}
DIRECTION_WORDS = {"long": mark("longs"), "short": mark("shorts")}
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


def tides_card(snap: dict | None, now: datetime | None = None, min_height: int = 300) -> str:
    """🌊 The Tides card for the top row of Quick Snapshot (24 Nov 2026): the tide and how long it has held, the sea
    and the fear index as two tiles, the wind for crypto and for equity longs with what drives it, and the next storm
    warning; the whole card opens the Tides panel. Tall enough to sit level with the video and the briefings beside
    it. Empty when Tides has no reading."""
    import macro_calendar as mc
    import tides as td

    now = now or datetime.now(timezone.utc)
    t_ = (snap or {}).get("tide") or {}
    if t_.get("status") != "ok" or t_.get("label") not in td.TIDE_WORDS:
        return ""
    name, plain, _icon = td.TIDE_WORDS[t_["label"]]
    colour = {"in": "#22c55e", "out": "#ef4444"}.get(t_["label"], GREY)          # bright enough on both themes
    arrow = {"in": "↗", "out": "↘"}.get(t_["label"], "↔")
    tint = {"in": "rgba(21,128,61,.14)", "out": "rgba(185,28,28,.14)"}.get(t_["label"], "rgba(107,114,128,.12)")
    held = t("held {n} trading days", n=t_.get("held_days")) if t_.get("held_days") else ""
    tiles = []
    sea = (snap or {}).get("sea") or {}
    if sea.get("status") == "ok":
        tiles.append(("⛵ " + t("Sea"), t(str(sea["state"]).capitalize()), t(str(sea.get("plain") or "").capitalize())))
    fear = ((snap or {}).get("currents") or {}).get("fear") or {}
    if fear.get("status") == "ok" and fear.get("value") is not None:
        week = fear.get("change_7")
        tiles.append(("😨 " + t("Fear (VIX)"), f"{float(fear['value']):.1f}",
                      t("{change} pts this week", change=f"{float(week):+.1f}") if week is not None else ""))
    tile_html = "".join(
        "<div style='border:1px solid var(--ang-border);border-radius:9px;padding:7px 10px;min-width:0;'>"
        f"<div class='ang-kicker' style='margin:0;'>{_e(k)}</div><div style='font-weight:700;'>{_e(v)}</div>"
        f"<div class='ang-kicker' style='margin:0;font-weight:500;'>{_e(sub)}</div></div>" for k, v, sub in tiles)
    winds = []
    for key, icon in (("crypto", "🪙"), ("equity", "🏛️")):
        w = ((snap or {}).get("winds") or {}).get(key)
        if not w:
            continue
        word = str(w.get("wind") or "")
        wc = {"tailwind": "#22c55e", "headwind": "#ef4444"}.get(word, GREY)
        drivers = ", ".join(t(td.SPEC[k]["name"]).lower() for k in w.get("drivers") or [] if k in td.SPEC)
        winds.append(f"<div style='font-size:.9rem;'>{icon} {_e(t(w.get('name') or key))}: "
                     f"<b style='color:{wc};'>{_e(t(word))}</b>"
                     + (f"<span class='ang-kicker' style='margin:0;'> · {_e(drivers)}</span>" if drivers else "")
                     + "</div>")
    e = next_event(now)
    storm = ""
    if e:
        storm = ("<div style='display:flex;gap:8px;align-items:center;border-radius:9px;padding:7px 10px;"
                 "background:rgba(245,165,36,.14);font-size:.9rem;'>"
                 f"<span>{_e(mc.pennants(e['tier']) or '📅')}</span><span><b>{_e(e.get('short') or e['name'])}</b>"
                 f"<span class='ang-kicker' style='margin:0;'> · {_e(mc.when_words(e['at'], now))}</span></span></div>")
    tip = t("🌊 Tides: the macro picture (money and rates, safe havens, growth and credit, rotation), what it means for "
            "crypto and equity longs, and the next scheduled event. Click to open the Tides panel. A description, "
            "not a forecast.")
    return (f"<button type='button' data-pick='tides' title='{_e(tip)}' style='{_BUTTON}'>"
            f"<div class='ang-card' style='display:flex;flex-direction:column;gap:9px;min-height:{min_height}px;"
            f"background:linear-gradient(165deg,{tint},transparent 62%),var(--ang-surface);'>"
            f"<div class='ang-kicker' style='margin:0;'>🌊 {_e(t('Tides'))}</div>"
            "<div style='display:flex;align-items:center;gap:12px;'>"
            f"<div style='font-size:2.1rem;line-height:1;color:{colour};'>{arrow}</div>"
            f"<div><div style='font-size:1.25rem;font-weight:800;line-height:1.1;'>{_e(t(name))}</div>"
            f"<div class='ang-kicker' style='margin:0;font-weight:500;'>{_e(t(plain).capitalize())}"
            + (f" · {_e(held)}" if held else "") + "</div></div></div>"
            + (f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;'>{tile_html}</div>" if tiles else "")
            + "".join(winds) + storm
            + f"<div style='margin-top:auto;text-align:right;font-weight:700;opacity:.75;'>{_e(t('Open Tides ›'))}</div>"
            "</div></button>")


def tides_line(snap: dict | None, now: datetime | None = None) -> str:
    """One clickable line: 🌊 tide (plain words) · sea state · next big event ›. Empty when Tides has no reading."""
    import macro_calendar as mc
    import tides as td

    now = now or datetime.now(timezone.utc)
    t_ = (snap or {}).get("tide") or {}
    if t_.get("status") != "ok" or t_.get("label") not in td.TIDE_WORDS:
        return ""
    name, plain, icon = td.TIDE_WORDS[t_["label"]]
    colour = {"in": GREEN, "out": RED}.get(t_["label"], GREY)
    bits = [f"<span style='font-weight:700;color:{colour};'>{_e(icon)} {_e(name)}</span>"
            f"<span class='ang-kicker' style='margin:0;'>&nbsp;{_e(plain)}"
            + (f", {t_.get('held_days')} days" if t_.get("held_days") else "") + "</span>"]
    sea = (snap or {}).get("sea") or {}
    if sea.get("status") == "ok":
        bits.append(f"<span>⛵ Sea {_e(sea['state'])}</span>"
                    f"<span class='ang-kicker' style='margin:0;'>&nbsp;{_e(sea.get('plain', ''))}</span>")
    e = next_event(now)
    if e:
        bits.append(f"<span>{_e(mc.pennants(e['tier']) or '📅')} {_e(e.get('short') or e['name'])}</span>"
                    f"<span class='ang-kicker' style='margin:0;'>&nbsp;{_e(mc.when_words(e['at'], now))}</span>")
    sep = "<span style='opacity:.35;padding:0 4px;'>|</span>"
    tip = (t("🌊 Tides: the macro picture (money and rates, safe havens, growth and credit, rotation) and the next "
           "scheduled event. Open the Tides panel for the currents and the waves. A description, not a forecast."))
    return (f"<button type='button' data-pick='tides' title='{_e(tip)}' style='{_BUTTON}'>"
            "<div class='ang-card' style='display:flex;flex-wrap:wrap;align-items:center;gap:4px 6px;"
            "padding-top:10px;padding-bottom:10px;'>"
            + sep.join(f"<span style='display:inline-flex;align-items:baseline;white-space:nowrap;'>{b}</span>"
                       for b in bits)
            + "<span style='margin-left:auto;opacity:.6;'>" + t("Tides ›") + "</span></div></button>")


# ------------------------------------------------------------------------------------------------ 2. funnel tiles

def _names(names: list[str], limit: int = 6) -> str:
    shown = ", ".join(names[:limit])
    return shown + (t(" and {n} more", n=len(names) - limit) if len(names) > limit else "")


def funnel_tiles(tiles: list[dict]) -> str:
    """The funnel tiles, side by side where there is room. Each opens its funnel's table on its Candidates.
    tile: {id, name, market, direction, paused, line, candidates, flagged, candidate_names, new, gone, seen}."""
    if not tiles:
        return ""
    # Crypto on the left and equities on the right, as in the rows above; shorts before longs (24 Nov 2026, Angus).
    order = {"crypto": 0, "equity": 1}, {"short": 0, "long": 1}
    tiles = sorted(tiles, key=lambda x: (order[0].get(x.get("market") or "crypto", 2),
                                         order[1].get(x.get("direction"), 2), str(x.get("name") or "")))
    groups = [[x for x in tiles if (x.get("market") or "crypto") == m] for m in ("crypto", "equity")]
    groups = [g for g in groups if g] + [[x for x in tiles if (x.get("market") or "crypto") not in order[0]]]
    groups = [g for g in groups if g]
    out = ["<div class='ang-kicker' style='margin:2px 0 6px;'>" + t("🔻 Your funnels") + "</div>",
           "<div style='display:flex;flex-wrap:wrap;gap:10px 1rem;'>"]
    for group in groups:
        # One half per market when both are traded, so each lines up under its own column above.
        out.append("<div style='display:flex;flex-wrap:wrap;gap:10px;flex:1 1 " + ("460px" if len(groups) > 1 else "100%")
                   + ";min-width:0;'>")
        out.extend(_funnel_tile(t_) for t_ in group)
        out.append("</div>")
    out.append("</div>")
    return "".join(out)


def _funnel_tile(t_: dict) -> str:
    """One funnel's tile; it opens the funnel's table on its Candidates."""
    out = []
    mark, market = MARKET_WORDS.get(t_.get("market") or "crypto", MARKET_WORDS["crypto"])
    direction = t(DIRECTION_WORDS.get(t_.get("direction"), t_.get("direction") or ""))
    kicker = f"{mark} {t(market)} · {direction}" + (t(" · ⏸️ paused") if t_.get("paused") else "")
    new, gone = t_.get("new") or [], t_.get("gone") or []
    badges = []
    if new:
        badges.append(f"<span title='{_e(t('New Candidates since your last visit: {names}', names=_names(new)))}' "
                      f"style='color:{GREEN};font-weight:700;'>＋{_e(t('{n} new', n=len(new)))}</span>")
    if gone:
        badges.append(f"<span title='{_e(t('No longer Candidates since your last visit: {names}', names=_names(gone)))}' "
                      f"style='color:{GREY};font-weight:700;'>－{_e(t('{n} left', n=len(gone)))}</span>")
    if not badges and t_.get("seen"):
        badges.append(f"<span style='color:{GREY};'>{_e(t('no change'))}</span>")
    cands = t_.get("candidate_names") or []
    tip = (t("Open {name} in its table, on its Candidates.", name=t_["name"]) + " "
           + (t("Candidates now: {names}.", names=_names(cands, 12)) + " " if cands else t("No Candidates right now. "))
           + t("Stage counts: the pool, then the assets holding each stage in a row."))
    out.append(
        f"<button type='button' data-pick='{_e('funnel|' + str(t_['id']) + '|' + t_['name'])}' title='{_e(tip)}' "
        f"style='{_BUTTON}flex:1 1 230px;max-width:100%;'>"
        "<div class='ang-card' style='height:100%;box-sizing:border-box;'>"
        f"<div class='ang-kicker'>{_e(kicker)}</div>"
        "<div class='ang-title' style='font-size:1.05rem;margin:2px 0 6px;white-space:nowrap;overflow:hidden;"
        f"text-overflow:ellipsis;'>{_e(t_['name'])}</div>"
        "<div style='display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px;'>"
        f"<span style='font-weight:700;font-size:1.05rem;'>✅ {t_.get('candidates', 0)}"
        f"<span class='ang-kicker' style='margin:0;font-weight:400;'>&nbsp;{_e(t('Candidates'))}</span></span>"
        f"<span style='font-weight:600;'>🚩 {t_.get('flagged', 0)}"
        f"<span class='ang-kicker' style='margin:0;font-weight:400;'>&nbsp;{_e(t('Flagged'))}</span></span>"
        + "".join(badges) + "</div>"
        f"<div class='ang-kicker' style='margin:6px 0 0;'>{_e(t_.get('line') or '')}</div>"
        "</div></button>")
    return "".join(out)


def no_funnels_tile(market: str = "crypto") -> str:
    """When the account has no funnels: one quiet tile that opens a table in Dynamic funnel, to copy a provided one."""
    tip = (t("A funnel narrows the market down in stages by itself, to a short list of Candidates. Click to open the "
           "table in Dynamic funnel and make your own copy of a provided funnel."))
    return (t("<button type='button' data-pick='{e_funnel_new_market}' title='{e_tip}' style='{_BUTTON}'><div class='ang-card' style='display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding-top:10px;padding-bottom:10px;'><span style='font-weight:600;'>🔻 Your funnels</span><span class='ang-kicker' style='margin:0;'>none yet: a funnel narrows the market to Candidates by itself</span><span style='margin-left:auto;opacity:.6;'>Make one ›</span></div></button>", e_funnel_new_market=_e('funnel_new|' + market), e_tip=_e(tip), _BUTTON=_BUTTON))


def candidate_changes(before: list[str] | None, now: list[str]) -> tuple[list[str], list[str]]:
    """(new, gone) Candidates against the last visit. No last visit: nothing is new."""
    if before is None:
        return [], []
    was, is_ = set(before), set(now)
    return [c for c in now if c not in was], [c for c in before if c not in is_]
