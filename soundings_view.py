"""
🧭 Soundings in Angstrom Lattice (preview, 18 Nov 2026): what came before past rises and falls (soundings.py).

Shows the last checked run (data/soundings.json, copied from the reports branch after checking): the conditions that
came before moves more often than usual in the search years, and what happened to each on the later years it never
saw. Faded ones are shown too: knowing what looked good and then failed is half the value.
"""

from __future__ import annotations

import json
from pathlib import Path

from i18n import mark, t

DATA = Path(__file__).resolve().parent / "data" / "soundings.json"
GRID = Path(__file__).resolve().parent / "data" / "soundings_grid.json.gz"

VERDICT = {
    "survivor": ("✅", mark("Held up"), mark("Still came before more moves than usual on the later years, on most coins.")),
    "either_way": ("↕️", mark("A bigger move, either way"), mark("Came before more rises AND more falls on the later years: a big move coming, direction unknown.")),
    "fragile": ("⚠️", mark("Held up, on a few coins"), mark("Still worked on the later years, but only on some coins.")),
    "not_confirmed": ("➖", mark("Weaker later"), mark("Pointed the same way on the later years, but not clearly enough.")),
    "faded": ("✖️", mark("Faded"), mark("On the later years it came before no more moves than usual.")),
}
ORDER = ["survivor", "either_way", "fragile", "not_confirmed", "faded"]
TIDE_WORDS = {"in": ("🌊⬆", mark("Tide coming in")), "slack": ("🌊↔", mark("Slack tide")),
              "out": ("🌊⬇", mark("Tide going out"))}
TIDE_HINT = mark("How often a move followed this condition, against the usual, split by the Tide on the day. Few Tide "
                 "spells, so this describes the past; it is not a tested result.")


def load(path: Path = DATA) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


_GRID: dict = {}


def load_grid(path: Path = GRID) -> dict | None:
    if "data" not in _GRID:
        try:
            import gzip

            with gzip.open(path, "rt") as fh:
                _GRID["data"] = json.load(fh)
        except Exception:
            _GRID["data"] = None
    return _GRID["data"]


def _pct(x) -> str:
    return f"{100 * float(x):.0f}%" if x is not None else "–"


def card_html(r: dict, target: str) -> str:
    import html

    icon, word, why = VERDICT.get(r.get("verdict"), ("", "", ""))
    c = r.get("confirm") or {}
    cond = " <b>and</b> ".join(html.escape(x) for x in r["condition"])
    move = t("a rise") if target == "rise" else t("a fall")
    first = t("{move} followed {rate} of the time, against {usual} usually: <b>{lift:.1f}×</b> · {days} days, {coins} coins",
              move=move, rate=_pct(r.get("rate")), usual=_pct(r.get("usual")), lift=r.get("lift") or 0,
              days=r.get("days", 0), coins=r.get("coins", 0))
    later = t("Later years: <b>{lift:.1f}×</b> · {days} days · more moves than usual on {up} of {read} coins",
              lift=c.get("lift") or 0, days=c.get("days", 0), up=c.get("coins_up", 0), read=c.get("coins_read", 0))
    o = r.get("opposite") or {}
    other = t("falls") if target == "rise" else t("rises")
    later += " · " + t("{other}: {lift:.1f}×", other=other, lift=o.get("lift") or 0)
    split = r.get("tide_split") or {}
    tides = ""
    if any((split.get(k) or {}).get("days") for k in TIDE_WORDS):
        parts = []
        for k, (icon, word) in TIDE_WORDS.items():
            x = split.get(k) or {}
            if not x.get("days"):
                continue
            lift = "–" if x.get("lift") is None else f"<b>{x['lift']:.1f}×</b>"
            parts.append(f"{icon} {t(word)} {lift} <span style='opacity:.7'>({t('{n} days', n=x['days'])})</span>")
        tides = (f"<div class='snd-line' title='{html.escape(t(TIDE_HINT))}'>{t('By the Tide, all years')}: "
                 + " · ".join(parts) + "</div>")
    theme = ""
    if r.get("theme_size"):
        theme = ("<div class='snd-line' title='" + html.escape("\n".join(r.get("theme") or [])) + "'>"
                 + t("+ {n} similar pairs found in the search (hover to see them)", n=r["theme_size"]) + "</div>")
    return (f"<div class='snd-card'><div class='snd-top'><span class='snd-v' title='{html.escape(t(why))}'>{icon} "
            f"{html.escape(t(word))}</span></div><div class='snd-cond'>{cond}</div>"
            f"<div class='snd-line'>{t('Search years')}: {first}</div><div class='snd-line'>{later}</div>{tides}{theme}</div>")


CSS = """
<style>
.snd-card{border:1px solid rgba(127,127,127,.3);border-radius:10px;padding:10px 12px;margin:8px 0}
.snd-top{font-size:.85rem;font-weight:700;margin-bottom:2px}
.snd-cond{font-size:1rem;margin:2px 0 6px}
.snd-line{font-size:.85rem;opacity:.85}
</style>
"""


def render(st, report: dict | None = None) -> None:
    report = report if report is not None else load()
    st.markdown(t("**🧭 Soundings** · *preview*: start from past rises and falls, and look back at what came "
                  "before them."))
    st.caption(t("Readings at the close before each move, compared with the same coin's usual chance of a move "
                 "that year. Anything found in the search years must also hold on later years the search never saw. "
                 "This describes the past: it is not a forecast or advice."))
    if not report:
        st.info(t("The first Soundings run is still being checked. It will show here soon."))
        return
    s = report.get("settings") or {}
    with st.expander(t("How this run was done"), expanded=False):
        st.markdown(t(
            "- **A rise**: {rise}. A fall is the mirror image.\n"
            "- **Coins**: {n} saved research coins, daily candles.\n"
            "- **Search years**: to {search}. **Later years** (confirmation): {confirm}. The protected test period "
            "from 30 Oct 2024 is never read.\n"
            "- **Kept from the search**: at least {lift}× the usual rate, on {days}+ days and {coins}+ coins, after "
            "allowing for how many conditions and pairs were tried (false finds kept to {fdr}).\n"
            "- **Tides** are read too (the Tide, the sea state, the wind for crypto, a major release coming, and the "
            "dollar, long rates, credit and fear), as they stood at each close; every result is also split by the Tide.",
            rise=s.get("rise", ""), n=len(s.get("coins") or []), search=str(s.get("search", "")).removeprefix("to "),
            confirm=s.get("confirm", ""), lift=s.get("min_lift", ""), days=s.get("min_days", ""),
            coins=s.get("min_coins", ""), fdr=f"{100 * float(s.get('fdr', 0.1)):.0f}%"))
    st.markdown(CSS, unsafe_allow_html=True)
    chart, rises, falls = st.tabs([t("🗺️ Chart"), t("📈 Before rises"), t("📉 Before falls")])   # the picture first
    with chart:
        chart_tab(st, report)
    for tab, target in ((rises, "rise"), (falls, "fall")):
        with tab:
            part = (report.get("targets") or {}).get(target) or {}
            results = part.get("results") or []
            st.caption(t("Usually {usual} of closes were followed by {move}. Looked at {looked} conditions and pairs; "
                         "{kept} passed the search, in {themes} themes; the strongest of each theme was checked on the "
                         "later years.", usual=_pct(part.get("base_rate_search")),
                         move=t("a rise") if target == "rise" else t("a fall"), looked=part.get("looked_at", 0),
                         kept=part.get("search_survivors", 0), themes=part.get("themes", 0)))
            if not results:
                st.markdown(t("Nothing passed the search: no condition came before {moves} clearly more often than "
                              "usual.", moves=t("rises") if target == "rise" else t("falls")))
                continue
            for v in ORDER:
                group = [r for r in results if r.get("verdict") == v]
                if not group:
                    continue
                icon, word, why = VERDICT[v]
                st.markdown(f"**{icon} {t(word)}** ({len(group)}) · <span style='opacity:.7'>{t(why)}</span>",
                            unsafe_allow_html=True)
                for r in sorted(group, key=lambda r: -((r.get("confirm") or {}).get("lift") or 0))[:12]:
                    st.markdown(card_html(r, target), unsafe_allow_html=True)


# ------------------------------------------------------------------------------------------------ the chart

MOVE_COLOUR = {"rise": "#16a34a", "fall": "#dc2626"}
TIDE_COLOUR = {"in": "#2563eb", "slack": "#9ca3af", "out": "#f97316"}
MISS = "#9ca3af"
MAX_ROWS = 12


def _theme(st) -> tuple[str, str, str]:
    try:
        dark = st.context.theme.type == "dark"
    except Exception:
        dark = False
    return ("#262730", "#e5e7eb", "#3f4654") if dark else ("#ffffff", "#374151", "#e5e7eb")


def _short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def chart_rows(report: dict, target: str, faded: bool) -> list[dict]:
    results = ((report.get("targets") or {}).get(target) or {}).get("results") or []
    keep = [r for r in results if faded or r.get("verdict") not in ("faded", "not_confirmed")]
    keep.sort(key=lambda r: (ORDER.index(r.get("verdict")) if r.get("verdict") in ORDER else 9,
                             -((r.get("confirm") or {}).get("lift") or 0)))
    return keep[:MAX_ROWS]


def fired(coin: dict, condition: list[str]) -> list[str] | None:
    """One character per day: 1 when every part of the condition held, 0 when not, . when a reading was missing."""
    parts = [coin["rows"].get(c) for c in condition]
    if any(p is None for p in parts):
        return None
    out = []
    for chars in zip(*parts):
        out.append("." if "." in chars else ("1" if all(c == "1" for c in chars) else "0"))
    return out


def build_figure(st, coin: dict, rows: list[dict], target: str, start: str, end: str):
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    days = pd.date_range(coin["start"], periods=coin["days"], freq="D")
    keep = (days >= pd.Timestamp(start)) & (days <= pd.Timestamp(end))
    idx = [i for i, k in enumerate(keep) if k]
    x = [days[i] for i in idx]
    close = [coin["close"][i] for i in idx]
    move = [coin[target][i] for i in idx]
    names = [t("🌊 Tide")] + [f"{VERDICT.get(r.get('verdict'), ('',))[0]} {_short(' + '.join(r['condition']))}" for r in rows]
    n = len(names)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.42, 0.58] if n > 4 else [0.6, 0.4])
    fig.add_trace(go.Scatter(x=x, y=close, mode="lines", line=dict(width=1.4, color="#64748b"), name=t("Price"),
                             hovertemplate="%{x|%d %b %Y}: %{y:,.4g}<extra></extra>"), row=1, col=1)
    word = t("a rise followed") if target == "rise" else t("a fall followed")
    mx = [xx for xx, m in zip(x, move) if m == "1"]
    my = [c for c, m in zip(close, move) if m == "1"]
    fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", name=word,
                             marker=dict(size=5, color=MOVE_COLOUR[target],
                                         symbol="triangle-up" if target == "rise" else "triangle-down"),
                             hovertemplate="%{x|%d %b %Y}: " + word + "<extra></extra>"), row=1, col=1)
    # Tide row: coloured by state
    for state, colour in TIDE_COLOUR.items():
        code = coin["rows"].get(f"Tide: {state}") or ""
        xs = [days[i] for i in idx if i < len(code) and code[i] == "1"]
        label = {"in": t("Tide coming in"), "slack": t("Slack tide"), "out": t("Tide going out")}[state]
        fig.add_trace(go.Scatter(x=xs, y=[names[0]] * len(xs), mode="markers", name=label, showlegend=True,
                                 marker=dict(symbol="square", size=7, color=colour),
                                 hovertemplate="%{x|%d %b %Y}: " + label + "<extra></extra>"), row=2, col=1)
    summary = []
    for name, r in zip(names[1:], rows):
        code = fired(coin, r["condition"])
        if code is None:
            continue
        hit = [days[i] for i in idx if code[i] == "1" and coin[target][i] == "1"]
        miss = [days[i] for i in idx if code[i] == "1" and coin[target][i] == "0"]
        full = " + ".join(r["condition"])
        fig.add_trace(go.Scatter(x=hit, y=[name] * len(hit), mode="markers", showlegend=False,
                                 marker=dict(symbol="square", size=7, color=MOVE_COLOUR[target]),
                                 hovertemplate="%{x|%d %b %Y}<br>" + full.replace("%", "%%") + "<br>" + word
                                 + "<extra></extra>"), row=2, col=1)
        nothing = t("no rise followed") if target == "rise" else t("no fall followed")
        fig.add_trace(go.Scatter(x=miss, y=[name] * len(miss), mode="markers", showlegend=False,
                                 marker=dict(symbol="square", size=7, color=MISS, opacity=0.45),
                                 hovertemplate="%{x|%d %b %Y}<br>" + full.replace("%", "%%") + "<br>" + nothing
                                 + "<extra></extra>"), row=2, col=1)
        summary.append((r, len(hit), len(hit) + len(miss)))
    paper, ink, grid = _theme(st)
    fig.update_layout(height=320 + 24 * n, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor=paper,
                      plot_bgcolor=paper, font=dict(color=ink, size=11), hovermode="closest",
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
    fig.update_yaxes(automargin=True)
    long_view = (pd.Timestamp(end) - pd.Timestamp(start)).days > 400      # log scale only over several years
    fig.update_yaxes(type="log" if long_view else "linear", row=1, col=1, gridcolor=grid, tickformat="~s")
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(names)), row=2, col=1, gridcolor=grid,
                     tickfont=dict(size=10))
    fig.update_xaxes(gridcolor=grid)
    usual = [m for m in move if m in "01"]
    base = (sum(m == "1" for m in usual) / len(usual)) if usual else None
    return fig, summary, base


def chart_tab(st, report: dict) -> None:
    grid = load_grid()
    if not grid or not grid.get("coins"):
        st.info(t("The chart's data is not available yet."))
        return
    st.caption(t("Price on top; below, one row per result: a square on each close where its condition held, coloured "
                 "when the move followed and grey when it didn't. The top row shows the Tide. Research coins, to "
                 "{cut}: the protected test period is never shown here.", cut=grid.get("cut", "")))
    coins = sorted(grid["coins"])
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    sym = c1.selectbox(t("Coin"), coins, index=coins.index("BTC-USD") if "BTC-USD" in coins else 0,
                       format_func=lambda s: s.replace("-USD", ""), key="snd_chart_coin")
    coin = grid["coins"][sym]
    first_year = int(coin["start"][:4])
    years = [str(y) for y in range(int(grid["cut"][:4]), first_year - 1, -1)]
    period = c2.selectbox(t("Period"), [t("Last 12 months")] + years + [t("All years")], key="snd_chart_period")
    target = c3.radio(t("Move"), ["rise", "fall"], horizontal=True, key="snd_chart_move",
                      format_func=lambda v: t("📈 Rises") if v == "rise" else t("📉 Falls"))
    faded = c4.toggle(t("Show faded too"), value=False, key="snd_chart_faded")
    import pandas as pd

    end = grid["cut"]
    if period == t("All years"):
        start = coin["start"]
    elif period == t("Last 12 months"):
        start = (pd.Timestamp(end) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    else:
        start, end = f"{period}-01-01", min(f"{period}-12-31", end)
    rows = chart_rows(report, target, faded)
    if not rows:
        st.markdown(t("No results to show for this move."))
        return
    fig, summary, base = build_figure(st, coin, rows, target, start, end)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    if base is not None:
        lines = []
        for r, hit, total in summary:
            rate = f"{100 * hit / total:.0f}%" if total else "–"
            lift = f"{(hit / total) / base:.1f}×" if total and base else "–"
            lines.append(t("- {icon} {cond}: held on {n} closes; {move} after {rate} of them, against {usual} usually "
                           "(**{lift}**)",
                           icon=VERDICT.get(r.get("verdict"), ("",))[0], cond=" + ".join(r["condition"]), n=total,
                           move=t("a rise") if target == "rise" else t("a fall"), rate=rate,
                           usual=f"{100 * base:.0f}%", lift=lift))
        st.markdown(t("**{coin}, this period:** {move} followed {usual} of all closes.",
                      coin=sym.replace("-USD", ""), move=t("a rise") if target == "rise" else t("a fall"),
                      usual=f"{100 * base:.0f}%") + "\n" + "\n".join(lines))
