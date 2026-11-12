"""
🌊 Tides on the page (preview): the sea-state header, the Navigator's factual note, storm warnings, the waves view
and the current cards. Pure HTML and SVG from a snapshot (tides.snapshot), so it is tested without Streamlit.

The header is a drawing driven by the readings: the sky and the waves follow the Sea state (calm, moderate, rough,
storm), the water level follows the Tide's score, and a pennant flies when a storm warning is on. Plain trading words
always sit beside the sailing words (decision 6). Motion is gentle and stops for people who turn motion off.
"""

from __future__ import annotations

import html
import math
from datetime import datetime, timezone

import macro_calendar as mc
import tides as td

SKY = {"calm": ("#7dd3fc", "#e0f2fe"), "moderate": ("#93c5fd", "#e2e8f0"),
       "rough": ("#64748b", "#cbd5e1"), "storm": ("#1e293b", "#475569")}
SEA = {"calm": ("#0ea5e9", "#0284c7", "#0369a1"), "moderate": ("#0284c7", "#0369a1", "#075985"),
       "rough": ("#0f766e", "#115e59", "#134e4a"), "storm": ("#1e3a5f", "#172554", "#0f172a")}
AMPLITUDE = {"calm": 3, "moderate": 7, "rough": 12, "storm": 18}
WIND_ICON = {"tailwind": "⛵", "headwind": "🌬️", "neither": "〰️"}
FAMILY_ORDER = ("money", "havens", "growth", "rotation")
ARROW = {"rising": "▲", "falling": "▼", "flat": "▶", "unknown": "·"}

CSS = """
<style>
.tides{--t-line:rgba(127,127,127,.28);--t-soft:rgba(127,127,127,.08);font-size:14px;line-height:1.4}
.tides .hero{position:relative;border-radius:14px;overflow:hidden;min-height:190px;border:1px solid var(--t-line)}
.tides .hero img.sea{position:absolute;inset:0;width:100%;height:100%;object-fit:fill}
.tides .hero .over{position:relative;z-index:1;display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;
  padding:16px 18px;color:#0f172a}
.tides .hero.dark .over{color:#f8fafc}
.tides .hero .big{font-size:26px;font-weight:700;letter-spacing:-.01em}
.tides .hero .plain{display:inline-block;margin-left:8px;padding:2px 10px;border-radius:999px;font-size:13px;
  font-weight:600;background:rgba(255,255,255,.75);color:#0f172a;vertical-align:middle}
.tides .hero .sub{margin-top:6px;font-weight:600}
.tides .hero .chips{display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.tides .chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;font-size:13px;
  font-weight:600;background:rgba(255,255,255,.8);color:#0f172a;cursor:help;white-space:nowrap}
.tides .chip.head{box-shadow:inset 0 0 0 1.5px #dc2626}.tides .chip.tail{box-shadow:inset 0 0 0 1.5px #16a34a}
.tides .chip.warn{background:#fee2e2;color:#7f1d1d}
.tides .card{border:1px solid var(--t-line);border-radius:12px;padding:10px 12px;background:var(--t-soft)}
.tides .note{margin-top:12px}.tides .note li{margin:2px 0}
.tides .note .who{font-weight:700}
.tides .strip{display:flex;gap:8px;overflow-x:auto;padding:4px 2px 8px;margin-top:12px}
.tides .ev{flex:0 0 auto;min-width:150px;border:1px dashed var(--t-line);border-radius:10px;padding:6px 10px;
  cursor:help;background:var(--t-soft)}
.tides .ev.past{border-style:solid;opacity:.75}.tides .ev.now{border:1.5px solid #dc2626}
.tides .ev .flag{font-size:13px}.tides .ev .nm{font-weight:600}.tides .ev .wh{font-size:12px;opacity:.8}
.tides h4{margin:16px 0 6px;font-size:15px}
.tides .fam{margin-top:10px}.tides .fam .fh{font-weight:700;margin-bottom:6px}
.tides .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px}
.tides .cur{position:relative;cursor:help}
.tides .cur .top{display:flex;justify-content:space-between;align-items:baseline;gap:6px}
.tides .cur .nm{font-weight:700}.tides .cur .val{font-variant-numeric:tabular-nums;font-weight:600}
.tides .cur .band{display:inline-block;margin-top:4px;padding:1px 8px;border-radius:999px;font-size:12px;
  background:rgba(127,127,127,.16)}
.tides .cur .dir{font-size:13px;margin-top:4px}
.tides .cur .dir.pos{color:#16a34a}.tides .cur .dir.neg{color:#dc2626}
.tides .cur .meta{font-size:12px;opacity:.75;margin-top:2px}
.tides .cur img.sp{display:block;width:100%;height:30px;margin-top:4px}
.tides .cur.mute{opacity:.92;border-style:dashed}
.tides .waves img.wv{width:100%;height:auto;display:block}
.tides .foot{margin-top:12px;font-size:12px;opacity:.75}
.tides .pv{display:inline-block;margin-left:6px;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;
  background:#fef3c7;color:#92400e;vertical-align:middle}
</style>
"""


def img(svg: str, cls: str, alt: str = "") -> str:
    """An SVG drawing as an image (the page's HTML filter removes inline SVG; images pass)."""
    import base64

    if "xmlns=" not in svg[:200]:
        svg = svg.replace("<svg ", "<svg xmlns='http://www.w3.org/2000/svg' ", 1)
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"<img class='{cls}' alt='{esc(alt)}' src='data:image/svg+xml;base64,{data}'/>"


def pull_of(c: dict) -> tuple[str, str, str]:
    """(word, css class, colour) for a current's pull. Flat is always neutral, so the two words never disagree."""
    if c.get("direction") not in ("rising", "falling"):
        return "neutral", "", "#64748b"
    if (c.get("contribution") or 0) > 0:
        return "risk-supportive", "pos", "#16a34a"
    return "risk-defensive", "neg", "#dc2626"


def esc(x) -> str:
    return html.escape(str(x), quote=True)


def fmt_value(c: dict) -> str:
    v, key = c.get("value"), c.get("key")
    if v is None:
        return "–"
    if key in ("short_rates", "long_rates", "inflation"):
        return f"{v:.2f}%"
    if key == "curve":
        return f"{v:+.2f} pts"
    if key in ("gold", "oil"):
        return f"${v:,.0f}" if v >= 100 else f"${v:,.2f}"
    if key in ("dollar", "fear"):
        return f"{v:.1f}"
    return ""                                   # ratios: their level means little; the change says it


def fmt_change(c: dict, which: str = "change_30") -> str:
    v = c.get(which)
    if v is None:
        return "–"
    return f"{v:+.2f} pts" if c.get("unit") == "pts" else f"{v:+.1f}%"


def spark(values: list[float], positive_good: bool) -> str:
    vals = [v for v in values or [] if v is not None and math.isfinite(v)]
    if len(vals) < 3:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * 200 / (len(vals) - 1):.1f},{28 - (v - lo) / span * 26:.1f}" for i, v in enumerate(vals))
    up = vals[-1] >= vals[0]
    colour = "#16a34a" if up == positive_good else "#dc2626"
    return img(f"<svg viewBox='0 0 200 30' preserveAspectRatio='none'>"
               f"<polyline points='{pts}' fill='none' stroke='{colour}' stroke-width='1.6' "
               f"vector-effect='non-scaling-stroke'/></svg>", "sp")


def wave_path(amplitude: float, y: float, length: float = 125, width: float = 1500) -> str:
    """A smooth repeating wave (quadratic curves), twice the visible width so it can drift."""
    d = f"M0 {y:.1f}"
    x, up = 0.0, True
    while x < width:
        d += f" q{length / 4:.1f} {(-amplitude if up else amplitude) * 2:.1f} {length / 2:.1f} 0"
        x += length / 2
        up = not up
    return d + f" V220 H0 Z"


def hero(snap: dict, warning: dict | None, now: datetime) -> str:
    t, sea, winds = snap.get("tide") or {}, snap.get("sea") or {}, snap.get("winds") or {}
    state = sea.get("state") or "moderate"
    sky_top, sky_bottom = SKY[state]
    score = t.get("score") or 0.0
    water = 150 - 45 * max(-1.0, min(1.0, score / 0.6))       # high water when the tide is in
    amp = AMPLITUDE[state]
    seas = SEA[state]
    layers = "".join(
        f"<path class='wave' style='animation-duration:{dur}s' d='{wave_path(amp * k, water + off)}' "
        f"fill='{colour}' fill-opacity='{op}'/>"
        for (k, off, dur, op), colour in zip(((1.0, 0, 26, .55), (.8, 10, 18, .75), (.6, 22, 12, 1)), seas))
    extras = ""
    if state in ("calm", "moderate"):
        extras += "<circle cx='860' cy='48' r='26' fill='#fde68a' fill-opacity='.9'/>"
    clouds = {"calm": 0, "moderate": 2, "rough": 4, "storm": 6}[state]
    cloud_fill = "#f8fafc" if state in ("calm", "moderate") else "#94a3b8" if state == "rough" else "#334155"
    for i in range(clouds):
        cx, cy = 120 + i * 150 + (i % 2) * 40, 40 + (i % 3) * 14
        extras += (f"<g fill='{cloud_fill}' fill-opacity='.85'><ellipse cx='{cx}' cy='{cy}' rx='46' ry='14'/>"
                   f"<ellipse cx='{cx + 26}' cy='{cy - 9}' rx='26' ry='13'/></g>")
    if state == "storm":
        extras += "<path d='M640 30 L620 80 L640 80 L615 130 L665 65 L642 65 L660 30Z' fill='#fde047'/>"
    if warning:
        extras += ("<g><line x1='600' y1='40' x2='600' y2='150' stroke='#334155' stroke-width='3'/>"
                   "<path d='M602 42 L638 54 L602 66Z' fill='#dc2626'/>"
                   + ("<path d='M602 70 L638 82 L602 94Z' fill='#dc2626'/>" if warning["tier"] in (2, "flag") else "")
                   + "</g>")
    gauge = ""
    motion = ("<style>@keyframes d{from{transform:translateX(0)}to{transform:translateX(-500px)}}"
              ".wave{animation:d linear infinite}@media (prefers-reduced-motion: reduce){.wave{animation:none}}</style>")
    svg = (f"<svg viewBox='0 0 1000 200' preserveAspectRatio='none'>{motion}<defs><linearGradient id='tides-sky' "
           f"x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='{sky_top}'/><stop offset='1' "
           f"stop-color='{sky_bottom}'/></linearGradient></defs><rect width='1000' height='200' fill='url(#tides-sky)'/>"
           f"{extras}{layers}{gauge}</svg>")
    if t.get("status") == "ok":
        name, plain, _ = td.TIDE_WORDS[t["label"]]
        held = f"for {t['held_days']} trading days"
        pending = ""
        if t.get("pending"):
            pending = (f" · turning: readings point to {td.TIDE_WORDS[t['raw_label']][0].lower()}, "
                       "confirmed after 5 closes")
        title = (f"<div class='big'>{esc(name)}<span class='plain'>{esc(plain)}</span></div>"
                 f"<div class='sub'>{esc(held)}{esc(pending)} · score {t['score']:+.2f}</div>")
    else:
        title = "<div class='big'>Tide unknown</div><div class='sub'>Not enough data yet.</div>"
    if sea.get("status") == "ok":
        title += (f"<div class='sub'>Sea {esc(sea['state'])} <span class='plain'>{esc(sea['plain'])}</span></div>")
    chips = []
    for w in winds.values():
        cls = "head" if w["wind"] == "headwind" else "tail" if w["wind"] == "tailwind" else ""
        word = {"headwind": "headwind (risk against)", "tailwind": "tailwind (risk with)",
                "neither": "no clear wind"}[w["wind"]]
        why = ", ".join(td.SPEC[k]["name"] for k in w["drivers"]) or "no single current"
        tip = f"{w['name']}: {word}. Led by {why}." + (
            f" Pushing the other way: {', '.join(td.SPEC[k]['name'] for k in w.get('against') or [])}."
            if w.get("against") else "")
        chips.append(f"<span class='chip {cls}' title='{esc(tip)}'>{WIND_ICON[w['wind']]} {esc(w['name'])}: "
                     f"{esc(w['wind'] if w['wind'] != 'neither' else 'no clear wind')}</span>")
    if warning:
        tip = f"{warning['name']} ({warning['reference']}): {warning['why']} A scheduled event, not a forecast."
        chips.append(f"<span class='chip warn' title='{esc(tip)}'>{mc.pennants(warning['tier'])} Storm warning: "
                     f"{esc(warning['short'])} {esc(mc.when_words(warning['at'], now))}</span>")
    dark = " dark" if state in ("rough", "storm") else ""
    sea_img = img(svg, "sea", f"Sea {state}, tide {t.get('label', '')}")
    return (f"<div class='hero{dark}'>{sea_img}<div class='over'><div>{title}</div>"
            f"<div class='chips'>{''.join(chips)}</div></div></div>")


def note(snap: dict, upcoming: list[dict], now: datetime) -> str:
    lines = td.summary(snap, upcoming, now)
    if not lines:
        return ""
    items = "".join(f"<li>{esc(line)}</li>" for line in lines)
    return (f"<div class='card note'><span class='who'>🧭 Navigator</span> · today's note, facts only, written "
            f"from the readings below<ul style='margin:6px 0 0 18px;padding:0'>{items}</ul></div>")


def strip(upcoming: list[dict], now: datetime) -> str:
    if not upcoming:
        return ""
    cards = []
    for e in upcoming[:10]:
        delta = (e["at"] - now).total_seconds()
        cls = "past" if delta < 0 else "now" if delta < 24 * 3600 else ""
        local = e["at"].astimezone(mc.NEW_YORK)
        tip = (f"{e['name']} ({e['reference']}) at {local:%H:%M} New York. {e['why']}"
               + (f" ({e['note']})" if e["note"] else "") + " A scheduled event, not a forecast.")
        cards.append(f"<div class='ev {cls}' title='{esc(tip)}'><div class='flag'>{mc.pennants(e['tier'])} {e['icon']}</div>"
                     f"<div class='nm'>{esc(e['short'])} · {esc(e['reference'])}</div>"
                     f"<div class='wh'>{local:%a %d %b} · {esc(mc.when_words(e['at'], now))}</div></div>")
    return ("<h4>⚑ Storm warnings: the macro calendar <span style='font-weight:400;font-size:12px'>(two pennants: "
            "major, one: notable, square flag: extreme)</span></h4><div class='strip'>" + "".join(cards) + "</div>")


RANGES = {"3M": 63, "6M": 126, "1Y": 252, "2Y": 504}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _dated(wave, dates: list[str]) -> dict[str, float]:
    """{date: value} for a current's wave. Older snapshots kept a plain list ending on the Tide's last day."""
    if wave and isinstance(wave[0], (list, tuple)):
        return {d: v for d, v in wave}
    return dict(zip(dates[-len(wave):], wave)) if wave else {}


def waves(snap: dict, range_key: str = "1Y") -> str:
    """Each voting current's pull (-1 to +1) and the swell (the Tide's score) on one time axis, like the charts:
    month ticks along the bottom and past Fed decisions as dashed lines."""
    days = RANGES.get(range_key, 252)
    cur = [c for k in td.CURRENT_KEYS if (c := (snap.get("currents") or {}).get(k)) and c.get("status") == "ok"
           and c.get("weight") and c.get("wave")]
    hist = ((snap.get("tide") or {}).get("history") or [])[-days:]
    if not cur or len(hist) < 20:
        return ""
    dates = [d for d, _v in hist]
    all_dates = [d for d, _v in (snap.get("tide") or {}).get("history") or []]
    x0, x1, lane, top = 170, 980, 34, 140
    rows_bottom = top + lane * len(cur)
    height = rows_bottom + 46
    n = len(dates)
    pos = {d: i for i, d in enumerate(dates)}

    def X(i):
        return x0 + (x1 - x0) * i / max(n - 1, 1)

    def path(points, cy, amp):
        out, pen = [], "M"
        for i, d in enumerate(dates):
            v = points.get(d)
            if v is None:
                pen = "M"
                continue
            out.append(f"{pen}{X(i):.1f} {cy - amp * v:.1f}")
            pen = "L"
        return " ".join(out)

    swell_y = 92
    t = snap.get("tide") or {}
    name, plain, _ = td.TIDE_WORDS.get(t.get("label"), ("Tide", "", ""))
    tide_state = f"{ {'in': '▲', 'out': '▼'}.get(t.get('label'), '▶') } {name.lower()} · {plain}"
    tide_tone = {"in": "#16a34a", "out": "#dc2626"}.get(t.get("label"), "#64748b")
    body = []
    # month ticks (first trading day of each month; every other month when the range is long)
    step = 1 if days <= 130 else 2 if days <= 260 else 3
    seen = []
    for i, d in enumerate(dates):
        ym = d[:7]
        if i and ym == dates[i - 1][:7]:
            continue
        month = int(d[5:7])
        if i == 0 or (month - 1) % step:
            continue
        seen.append((i, d))
    for i, d in seen:
        label = MONTHS[int(d[5:7]) - 1] + (f" '{d[2:4]}" if d[5:7] == "01" or i == seen[0][0] else "")
        body.append(f"<line x1='{X(i):.1f}' x2='{X(i):.1f}' y1='48' y2='{rows_bottom}' stroke='#94a3b8' "
                    f"stroke-opacity='.25'/>")
        body.append(f"<text x='{X(i):.1f}' y='{rows_bottom + 18}' font-size='12' text-anchor='middle' "
                    f"fill='#64748b'>{label}</text>")
    # past Fed decisions, CPI and jobs releases: one colour and one label row each, so they never pile up
    marks = {"fomc": ("Fed", "#dc2626", 12), "cpi": ("CPI", "#d97706", 26), "jobs": ("Jobs", "#7c3aed", 40)}
    for e in mc.events():
        d = e["at"].date().isoformat()
        if e["kind"] not in marks or d not in pos:
            continue
        word, colour, row = marks[e["kind"]]
        x = X(pos[d])
        body.append(f"<line x1='{x:.1f}' x2='{x:.1f}' y1='{row + 4}' y2='{rows_bottom}' stroke='{colour}' "
                    f"stroke-opacity='.45' stroke-dasharray='3 4'/>")
        body.append(f"<text x='{x:.1f}' y='{row}' font-size='10' text-anchor='middle' fill='{colour}'>{word}</text>")
    body += [f"<rect x='{x0}' y='{swell_y - 0.2 * 45:.1f}' width='{x1 - x0}' height='{0.4 * 45:.1f}' "
             f"fill='#94a3b8' fill-opacity='.18'/>",
             f"<line x1='{x0}' x2='{x1}' y1='{swell_y}' y2='{swell_y}' stroke='#94a3b8'/>",
             f"<path d='{path(dict(hist), swell_y, 45)}' fill='none' stroke='#2563eb' stroke-width='2.5'/>",
             f"<text x='12' y='{swell_y - 4}' font-size='13' font-weight='700' fill='#64748b'>Swell = the Tide</text>",
             f"<text x='12' y='{swell_y + 12}' font-size='9.5' fill='{tide_tone}'>{esc(tide_state)}</text>"]
    colours = ("#f97316", "#10b981", "#8b5cf6", "#ec4899", "#14b8a6", "#eab308", "#64748b", "#ef4444", "#0ea5e9")
    for i, c in enumerate(cur):
        cy = top + lane * i + lane / 2
        body.append(f"<line x1='{x0}' x2='{x1}' y1='{cy}' y2='{cy}' stroke='#94a3b8' stroke-opacity='.5'/>")
        body.append(f"<path d='{path(_dated(c['wave'], all_dates), cy, 13)}' fill='none' "
                    f"stroke='{colours[i % len(colours)]}' stroke-width='1.5'/>")
        pull, _cls, tone = pull_of(c)
        body.append(f"<text x='12' y='{cy - 2}' font-size='12' fill='#64748b'>{esc(c['icon'])} {esc(c['name'])}</text>")
        body.append(f"<text x='30' y='{cy + 12}' font-size='9' fill='{tone}'>{ARROW[c['direction']]} "
                    f"{esc(c['direction'])} · {pull}</text>")
    first, last = dates[0], dates[-1]
    svg = img(f"<svg viewBox='0 0 1000 {height}' font-family='Source Sans Pro, Segoe UI, Helvetica, Arial, "
              f"sans-serif'>" + "".join(body) + "</svg>", "wv",
              f"Each current and the swell from {first} to {last}")
    return ("<div class='card waves'>" + svg + "<div class='foot' style='margin-top:4px'>Above a lane's line pulls "
            "towards risk-taking, below pulls away. The swell is the Tide's score: each family's average, weighted "
            "(money and rates 30%, growth and credit 30%, safe havens 20%, rotation 20%); the grey band is slack. "
            "Dashed lines mark past releases: red Fed rate decisions, amber CPI inflation, purple jobs reports. Drawn from the readings, nothing added.</div></div>")


WAVES_TITLE = "<h4>〰️ The waves: each current's pull, and the swell they make together</h4>"


def card(c: dict) -> str:
    spec = td.SPEC[c["key"]]
    if c.get("status") != "ok":
        return (f"<div class='card cur mute' title='{esc(spec['measures'])}'><div class='nm'>{esc(spec['icon'])} "
                f"{esc(spec['name'])}</div><div class='meta'>No data right now.</div></div>")
    pull, cls, _tone = pull_of(c)
    meaning = spec[c["direction"]] if c["direction"] in ("rising", "falling") else "little change over 30 days"
    votes = "Votes in the Tide." if c["weight"] else "Shown on its own; does not vote in the Tide."
    tip = (f"{spec['measures']}. {c['direction'].capitalize()}: {meaning}. Today's level is {c['band']} for the past "
           f"5 years (score {c['score']:.0f}/100). {votes} Change: 7 days {fmt_change(c, 'change_7')}, 30 days "
           f"{fmt_change(c)}. As of {c['as_of']}.")
    return (f"<div class='card cur{'' if c['weight'] else ' mute'}' title='{esc(tip)}'>"
            f"<div class='top'><span class='nm'>{esc(spec['icon'])} {esc(spec['name'])}</span>"
            f"<span class='val'>{esc(fmt_value(c))}</span></div>"
            f"<span class='band'>{esc(c['band'])} · {c['score']:.0f}/100</span>"
            f"<div class='dir {cls}'>{ARROW[c['direction']]} {esc(c['direction'])} · {esc(pull)}</div>"
            f"<div class='meta'>30 days {esc(fmt_change(c))}{'' if c['weight'] else ' · not voting'}</div>"
            f"{spark(c.get('spark') or [], spec['sign'] > 0)}</div>")


def cards(snap: dict) -> str:
    cur = snap.get("currents") or {}
    out = ["<h4>🧭 The currents</h4>"]
    for fam in FAMILY_ORDER:
        name, weight, icon = td.FAMILIES[fam]
        members = [cur[k] for k in td.CURRENT_KEYS if td.SPEC[k]["family"] == fam and k in cur]
        score = ((snap.get("tide") or {}).get("families") or {}).get(fam)
        pull = "" if score is None else f" · pull {score:+.2f}"
        out.append(f"<div class='fam'><div class='fh'>{icon} {esc(name)} <span style='font-weight:400;opacity:.75'>"
                   f"(weight {weight:.0%}{pull})</span></div><div class='grid'>"
                   + "".join(card(c) for c in members) + "</div></div>")
    return "".join(out)


def side_readings(snap: dict) -> str:
    bits = []
    fng = snap.get("fear_greed")
    if fng is not None:
        mood = ("extreme fear" if fng < 25 else "fear" if fng < 45 else "neutral" if fng <= 55
                else "greed" if fng <= 75 else "extreme greed")
        bits.append(f"<div class='card cur' title='Alternative.me crypto Fear and Greed. Shown on its own: it already "
                    f"sits inside the crypto sentiment score, so it never votes in the Tide.'><div class='nm'>😱 Crypto "
                    f"Fear &amp; Greed</div><div class='val'>{fng:.0f}/100 · {esc(mood)}</div>"
                    f"<div class='meta'>not in the Tide</div></div>")
    dom = snap.get("btc_dominance")
    if dom is not None:
        bits.append(f"<div class='card cur' title=\"Bitcoin's share of the whole crypto market (CoinGecko). Rising often "
                    f"means money retreating to Bitcoin; falling, money moving out to altcoins. Our own daily history "
                    f"of it is still short, so it is shown, not scored.\"><div class='nm'>₿ Bitcoin share</div>"
                    f"<div class='val'>{dom:.1f}%</div><div class='meta'>crypto rotation, shown</div></div>")
    ex = snap.get("extras") or {}
    if ex.get("long_30y"):
        bits.append(f"<div class='card cur' title='30-year Treasury yield, shown beside long rates (the 10-year votes).'>"
                    f"<div class='nm'>📏 30-year yield</div><div class='val'>{ex['long_30y']['value']:.2f}%</div>"
                    f"<div class='meta'>30 days {ex['long_30y']['change_30']:+.2f} pts</div></div>")
    if ex.get("copper"):
        bits.append(f"<div class='card cur' title='Copper on its own (copper against gold votes).'>"
                    f"<div class='nm'>🔶 Copper</div><div class='val'>${ex['copper']['value']:.2f}/lb</div>"
                    f"<div class='meta'>30 days {ex['copper']['change_30']:+.1f}%</div></div>")
    for key, name, tip in (("cyclical_defensive", "🛍️ Cyclical vs defensive",
                            "Consumer discretionary against consumer staples (XLY vs XLP): rises when money favours "
                            "growth-sensitive sectors."),
                           ("small_large", "🐟 Small vs large", "Small companies against large (IWM vs SPY): rises "
                            "with broad risk appetite.")):
        r = ex.get(key)
        if r and r.get("change_30") is not None:
            bits.append(f"<div class='card cur' title='{esc(tip)}'><div class='nm'>{name}</div>"
                        f"<div class='val'>30 days {r['change_30']:+.1f}%</div>"
                        f"<div class='meta'>{esc(td.band(r.get('score')) or '')} for 5 years</div></div>")
    if not bits:
        return ""
    return "<h4>🔭 Also on the horizon (shown, not voting)</h4><div class='grid'>" + "".join(bits) + "</div>"


def top_part(snap: dict, now: datetime | None = None) -> str:
    """Header, note and storm warnings (then the app puts its range picker above the waves)."""
    now = now or datetime.now(timezone.utc)
    upcoming = mc.upcoming(now, days=35)
    return (CSS + "<div class='tides'>" + hero(snap, mc.storm_warning(now), now) + note(snap, upcoming, now)
            + strip(upcoming, now) + WAVES_TITLE + "</div>")


def hero_part(snap: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return CSS + "<div class='tides'>" + hero(snap, mc.storm_warning(now), now) + "</div>"


def note_part(snap: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return CSS + "<div class='tides'>" + note(snap, mc.upcoming(now, days=35), now) + "</div>"


def strip_part(snap: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return "<div class='tides'>" + strip(mc.upcoming(now, days=35), now) + WAVES_TITLE + "</div>"


def waves_part(snap: dict, range_key: str = "1Y") -> str:
    return "<div class='tides'>" + waves(snap, range_key) + "</div>"


def bottom_part(snap: dict) -> str:
    stamp = snap.get("computed_at", "")[:16].replace("T", " ")
    return "<div class='tides'>" + cards(snap) + side_readings(snap) + footer(stamp) + "</div>"


def footer(stamp: str) -> str:
    return (f"<div class='foot'>Preview for review. Readings from Yahoo Finance and FRED (St. Louis Fed), updated "
            f"{esc(stamp)} UTC. Each current is scored against its own last 5 years; its pull is its 30-day move "
            f"against the usual size of such a move. History before the daily record began is rebuilt from today's "
            f"data, and inflation uses revised figures, not first releases. Macro conditions frame risk; they do "
            f"not time trades, and a coin can rise on its own news while the tide goes out. Not advice.</div>")


def page(snap: dict, now: datetime | None = None, range_key: str = "1Y") -> str:
    now = now or datetime.now(timezone.utc)
    upcoming = mc.upcoming(now, days=35)
    warning = mc.storm_warning(now)
    stamp = snap.get("computed_at", "")[:16].replace("T", " ")
    foot = (f"<div class='foot'>Preview for review. Readings from Yahoo Finance and FRED (St. Louis Fed), updated "
            f"{esc(stamp)} UTC. Each current is scored against its own last 5 years; its pull is its 30-day move "
            f"against the usual size of such a move. History before the daily record began is rebuilt from today's "
            f"data, and inflation uses revised figures, not first releases. Macro conditions frame risk; they do "
            f"not time trades, and a coin can rise on its own news while the tide goes out. Not advice.</div>")
    return (CSS + "<div class='tides'>" + hero(snap, warning, now) + note(snap, upcoming, now)
            + strip(upcoming, now) + WAVES_TITLE + waves(snap, range_key) + cards(snap) + side_readings(snap)
            + foot + "</div>")


PASSAGE_TIP = ("📜 Today's AI Passage Plan (opens in its own window): the AI Navigator charts today's conditions, the "
               "week's events and the winds for your own assets, Sets and funnels, with things to watch. One plan a "
               "day, kept in your logbook. Descriptions, not buy or sell calls.")


def render_panel(st, snap: dict, saved_range: str | None, save_range, buttons) -> None:
    """The Tides panel in Streamlit (the app's 🌊 Tides section, and the training-video demo page): the hero, the
    note with the AI buttons beside it (buttons() draws them), the calendar, the range picker (saved_range, and
    save_range(picked) when it changes), the waves and the currents."""
    st.html(hero_part(snap))
    # The note and the two AI buttons share a row when there is room; on a narrow screen the buttons wrap to a
    # row of their own instead of squashing their labels.
    st.markdown(
        "<style>.st-key-tides_note_row [data-testid='stHorizontalBlock']{flex-wrap:wrap;row-gap:8px}"
        ".st-key-tides_note_row [data-testid='stColumn']:first-child{flex:1 1 420px !important;"
        "min-width:min(420px,100%) !important}"
        ".st-key-tides_note_row [data-testid='stColumn']:last-child{flex:0 1 auto !important;width:auto !important;"
        "min-width:0 !important}"
        ".st-key-tides_note_row [data-testid='stColumn']:last-child [data-testid='stElementContainer']"
        "{width:auto !important}</style>", unsafe_allow_html=True)
    row = st.container(key="tides_note_row")
    note_col, ai_col = row.columns([5, 1], vertical_alignment="center")
    with note_col:
        st.html(note_part(snap))
    with ai_col:
        buttons()
    st.html(strip_part(snap))
    ranges = list(RANGES)
    if st.session_state.get("tides_range") not in ranges:
        st.session_state["tides_range"] = saved_range if saved_range in ranges else "1Y"
    picked = st.segmented_control("Time range", ranges, key="tides_range", label_visibility="collapsed",
                                  help="How far back the waves go: 3 months, 6 months, 1 year or 2 years.")
    if picked and picked != saved_range:
        save_range(picked)
    st.html(waves_part(snap, picked or "1Y"))
    st.html(bottom_part(snap))
