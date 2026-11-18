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
            rise=s.get("rise", ""), n=len(s.get("coins") or []), search=s.get("search", ""),
            confirm=s.get("confirm", ""), lift=s.get("min_lift", ""), days=s.get("min_days", ""),
            coins=s.get("min_coins", ""), fdr=f"{100 * float(s.get('fdr', 0.1)):.0f}%"))
    st.markdown(CSS, unsafe_allow_html=True)
    rises, falls = st.tabs([t("📈 Before rises"), t("📉 Before falls")])
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
