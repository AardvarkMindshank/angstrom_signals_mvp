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


FILES = {"crypto": (DATA, GRID),
         "equity": (DATA.with_name("soundings_equity.json"), GRID.with_name("soundings_equity_grid.json.gz"))}


def load_grid(path: Path = GRID) -> dict | None:
    if str(path) not in _GRID:
        try:
            import gzip

            with gzip.open(path, "rt") as fh:
                _GRID[str(path)] = json.load(fh)
        except Exception:
            _GRID[str(path)] = None
    return _GRID[str(path)]


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
        for k, (t_icon, t_word) in TIDE_WORDS.items():
            x = split.get(k) or {}
            if not x.get("days"):
                continue
            lift = "–" if x.get("lift") is None else f"<b>{x['lift']:.1f}×</b>"
            parts.append(f"{t_icon} {t(t_word)} {lift} <span style='opacity:.7'>({t('{n} days', n=x['days'])})</span>")
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
    st.markdown(t("**🧭 Soundings** · *preview*: start from past rises and falls, and look back at what came "
                  "before them."))
    market = "crypto"
    if report is None:
        market = st.segmented_control(t("Market"), ["crypto", "equity"], default="crypto", key="snd_market",
                                      label_visibility="collapsed",
                                      format_func=lambda m: t("🪙 Crypto") if m == "crypto" else t("🏛️ Equities"),
                                      ) or "crypto"
        report = load(FILES[market][0])
    st.caption(t("Readings at the close before each move, compared with the same coin's usual chance of a move "
                 "that year. Anything found in the search years must also hold on later years the search never saw. "
                 "This describes the past: it is not a forecast or advice."))
    if not report:
        st.info(t("This Soundings run is still being checked. It will show here soon."))
        return
    s = report.get("settings") or {}
    with st.expander(t("How this run was done"), expanded=False):
        first = ""
        if s.get("universe") == "equity_sample":
            first = (t("- **Equities**: a fixed random sample of {n} companies from the S&P 500 as it stood at the "
                          "start of 2016, including companies that later left the index, so the results are not "
                          "flattered by looking only at today's winners.", n=len(s.get("coins") or [])))
        if s.get("universe") == "wide":
            first = (t("- **Coins**: the {n} most traded coins on Binance from 2018 to 2023, including coins that "
                          "later collapsed or stopped trading, so the results are not flattered by looking only at "
                          "survivors.", n=len(s.get("coins") or [])))
        rest = (t(
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
        lines = rest.split("\n")
        if first and len(lines) > 1:
            del lines[1]                  # "saved research coins": the first line already says what was used
        # one list, so the bullets are evenly spaced (two lists left a gap between them)
        st.markdown("\n".join([first, *lines]) if first else "\n".join(lines))
    st.markdown(CSS, unsafe_allow_html=True)
    chart, rises, falls = st.tabs([t("🗺️ Chart"), t("📈 Before rises"), t("📉 Before falls")])   # the picture first
    with chart:
        chart_tab(st, report, FILES[market][1] if market in FILES else GRID)
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
                for n, r in enumerate(sorted(group, key=lambda r: -((r.get("confirm") or {}).get("lift") or 0))[:12]):
                    st.markdown(card_html(r, target), unsafe_allow_html=True)
                    if v != "faded":
                        st.button(t("🧩 Open as Set"), key=f"snd_set_{target}_{v}_{n}", on_click=open_as_set,
                                  args=(st, r, target),
                                  help=t("Opens this condition in Signal Sets as a new Set (daily candles), to save, "
                                         "scan in Prism, put in a funnel or get alerts from."))


def open_as_set(st, r: dict, target: str) -> None:
    """Button callback: put the result's condition in the Set editor as a new, unsaved Set, and switch to it."""
    import lattice_sets as ls
    import soundings as so

    c = r.get("confirm") or {}
    move = t("rises") if target == "rise" else t("falls")
    name = t("Soundings: {cond} ({move})", cond=" + ".join(r["condition"]), move=move)
    purpose = t("Came before {move} {lift:.1f}× as often as usual in the search years and {later:.1f}× on the later "
                "years (Soundings, daily candles).", move=move, lift=r.get("lift") or 0, later=c.get("lift") or 0)
    model = so.set_model(r["condition"], name, purpose)
    if model is None:
        st.session_state["lattice_flash_set"] = ("warn", t("This condition can't be opened as a Set yet."))
    else:
        st.session_state["lattice_set_model"] = ls.clean_model(model, {})
        st.session_state["lattice_set_source"] = None
        st.session_state["lattice_set_loaded"] = "new"
        st.session_state["_lattice_set_start_next"] = "new"
        st.session_state["lattice_flash_set"] = ("ok", t("Opened from Soundings as a new Set. Check it, then save it."))
    st.session_state["_lattice_section_next"] = "sets"


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
    import lw_chart

    paper = lw_chart.card_colour(dark)                  # the account's card colour (Settings › UI colours)
    return (paper, "#e5e7eb", "#3f4654") if dark else (paper, "#374151", "#e5e7eb")


def _short(text: str, n: int = 40) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def chart_rows(report: dict, target: str, faded: bool) -> list[dict]:
    results = ((report.get("targets") or {}).get(target) or {}).get("results") or []
    keep = [r for r in results if faded or r.get("verdict") not in ("faded", "not_confirmed")]
    keep.sort(key=lambda r: (ORDER.index(r.get("verdict")) if r.get("verdict") in ORDER else 9,
                             -((r.get("confirm") or {}).get("lift") or 0)))
    return keep[:MAX_ROWS]


_NAMES: dict = {}


def asset_label(symbol: str) -> str:
    """'BTC · Bitcoin', 'AAPL · Apple' (data/asset_names.json); the ticker alone when the name isn't known."""
    if not _NAMES:
        try:
            _NAMES.update(json.loads((DATA.parent / "asset_names.json").read_text()))
        except Exception:
            _NAMES["_"] = ""
    short = symbol.replace("-USD", "")
    name = _NAMES.get(symbol)
    return f"{short} · {name}" if name else short


def coin_days(coin: dict):
    """The day of each close: every calendar day for crypto, the listed trading days for equities."""
    import pandas as pd

    if coin.get("offsets"):
        return pd.Timestamp(coin["start"]) + pd.to_timedelta(coin["offsets"], unit="D")
    return pd.date_range(coin["start"], periods=coin["days"], freq="D")


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

    days = coin_days(coin)
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
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0), dragmode="pan")
    fig.update_yaxes(automargin=True)
    long_view = (pd.Timestamp(end) - pd.Timestamp(start)).days > 400      # log scale only over several years
    fig.update_yaxes(type="log" if long_view else "linear", row=1, col=1, gridcolor=grid, tickformat="~s",
                     fixedrange=True)          # the wheel zooms time only
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(names)), row=2, col=1, gridcolor=grid,
                     fixedrange=True,
                     tickfont=dict(size=10))
    fig.update_xaxes(gridcolor=grid)
    usual = [m for m in move if m in "01"]
    base = (sum(m == "1" for m in usual) / len(usual)) if usual else None
    return fig, summary, base


def chart_payload(coin: dict, rows: list[dict], target: str, start: str, end: str, dark: bool,
                  key: str = "") -> tuple[dict, list, float | None]:
    """The TradingView chart's data (soundings_chart.js): times, closes, the move's days, and one row per result
    (the Tide first), each a list of [day index, colour, hover text]."""
    import pandas as pd

    import lw_chart

    days = coin_days(coin)
    idx = [i for i, d in enumerate(days) if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    times = [int(days[i].timestamp()) for i in idx]
    flags = "".join(coin[target][i] for i in idx)
    word = t("a rise followed") if target == "rise" else t("a fall followed")
    nothing = t("no rise followed") if target == "rise" else t("no fall followed")
    tide_words = {"in": t("Tide coming in"), "slack": t("Slack tide"), "out": t("Tide going out")}
    tide_points = []
    for k, i in enumerate(idx):
        for state, colour in TIDE_COLOUR.items():
            code = coin["rows"].get(f"Tide: {state}") or ""
            if i < len(code) and code[i] == "1":
                tide_points.append([k, colour, "🌊 " + tide_words[state]])
                break
    out_rows = [{"name": t("🌊 Tide"), "full": t("🌊 Tide"), "points": tide_points}]
    summary = []
    for r in rows:
        code = fired(coin, r["condition"])
        if code is None:
            continue
        full = " + ".join(r["condition"])
        points, hit, total = [], 0, 0
        for k, i in enumerate(idx):
            if code[i] != "1":
                continue
            followed = coin[target][i]
            if followed == ".":
                continue
            total += 1
            hit += followed == "1"
            points.append([k, MOVE_COLOUR[target] if followed == "1" else MISS,
                           f"{full}: {word if followed == '1' else nothing}"])
        icon = VERDICT.get(r.get("verdict"), ("",))[0]
        out_rows.append({"name": f"{icon} {_short(full, 46)}", "full": f"{icon} {full}", "points": points})
        summary.append((r, hit, total))
    known = [f for f in flags if f in "01"]
    base = (known.count("1") / len(known)) if known else None
    ink = "#e5e7eb" if dark else "#374151"
    theme = {**lw_chart.theme(dark), "ink": ink,
             "label_bg": "rgba(38,39,48,0.78)" if dark else "rgba(255,255,255,0.82)"}
    payload = {
        "lib": lw_chart.LIBRARY_PATH, "key": key, "theme": theme, "target": target,
        "times": times, "close": [coin["close"][i] for i in idx], "move_flags": flags,
        "moves": [k for k, f in enumerate(flags) if f == "1"], "move_colour": MOVE_COLOUR[target],
        "rows": out_rows, "price_px": 300, "log_scale": (pd.Timestamp(end) - pd.Timestamp(start)).days > 400,
        "words": {"followed": word, "not_followed": nothing, "reset": t("Back to the chosen range"),
                  "latest": t("Scroll to the newest candle"),
                  "failed": t("The TradingView chart could not load. You can switch to the Plotly chart in Settings.")},
    }
    return payload, summary, base


_COMPONENT: dict = {}


def _tv_component(st):
    if "c" not in _COMPONENT:
        js = (Path(__file__).resolve().parent / "soundings_chart.js").read_text(encoding="utf-8")
        _COMPONENT["c"] = st.components.v2.component("soundings_chart", js=js, isolate_styles=False)
    return _COMPONENT["c"]


def chart_tab(st, report: dict, grid_path: Path = GRID) -> None:
    grid = load_grid(grid_path)
    if not grid or not grid.get("coins"):
        st.info(t("The chart's data is not available yet."))
        return
    st.caption(t("Price on top; below, one row per result: a square on each close where its condition held, coloured "
                 "when the move followed and grey when it didn't. The top row shows the Tide. Research coins, to "
                 "{cut}: the protected test period is never shown here.", cut=grid.get("cut", "")))
    # Only coins still trading: those that stopped are kept in the testing (so the results are not flattered by
    # survivors only) but there is nothing to trade, so they are not offered here.
    coins = sorted(c for c, v in grid["coins"].items() if not v.get("stopped"))
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
    first = "BTC-USD" if "BTC-USD" in coins else ("AAPL" if "AAPL" in coins else None)
    sym = c1.selectbox(t("Asset"), coins, index=coins.index(first) if first else 0,
                       format_func=asset_label, key=f"snd_chart_coin_{grid.get('market', 'c')}")
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
    if st.session_state.get("price_chart", "TradingView") == "TradingView":     # follows Settings › price chart
        try:
            dark = st.context.theme.type == "dark"
        except Exception:
            dark = False
        payload, summary, base = chart_payload(coin, rows, target, start, end, dark,
                                               key=f"{sym}|{target}|{start}|{end}|{faded}")
        _tv_component(st)(key="snd_tv_chart", data=payload)
        st.caption(t("Zoom: scroll the wheel over the chart (or pinch), drag to move along, double-click the time "
                     "axis to see it all. Hover a day for its details."))
    else:
        fig, summary, base = build_figure(st, coin, rows, target, start, end)
        st.plotly_chart(fig, width="stretch", config={"scrollZoom": True, "displaylogo": False, "displayModeBar": True,
                                                      "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d",
                                                                                 "toImage"]})
        st.caption(t("Zoom: scroll the wheel over the chart (or pinch), drag to move along, double-click to see it all."))
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
