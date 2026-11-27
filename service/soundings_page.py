"""🧭 Soundings for the new app: the classic Soundings view (soundings_view.py) as data. The last checked run, its
results as cards (what came before past rises and falls, and how each held up on the later years), and the chart's
data for the classic chart script (soundings_chart.js), which the new app hosts unchanged. Read-only research; the
protected test period is never shown."""
from __future__ import annotations

import i18n


def _verdict(v: str) -> dict:
    import soundings_view as sv

    icon, word, why = sv.VERDICT.get(v, ("", "", ""))
    return {"key": v, "icon": icon, "word": i18n.t(word), "why": i18n.t(why)}


def _card(r: dict, target: str) -> dict:
    """One result, its lines in words (the classic card's own texts; <b> marks the figures)."""
    import soundings_view as sv

    t = i18n.t
    c = r.get("confirm") or {}
    move = t("a rise") if target == "rise" else t("a fall")
    first = t("{move} followed {rate} of the time, against {usual} usually: <b>{lift:.1f}×</b> · {days} days, {coins} coins",
              move=move, rate=sv._pct(r.get("rate")), usual=sv._pct(r.get("usual")), lift=r.get("lift") or 0,
              days=r.get("days", 0), coins=r.get("coins", 0))
    later = t("Later years: <b>{lift:.1f}×</b> · {days} days · more moves than usual on {up} of {read} coins",
              lift=c.get("lift") or 0, days=c.get("days", 0), up=c.get("coins_up", 0), read=c.get("coins_read", 0))
    o = r.get("opposite") or {}
    later += " · " + t("{other}: {lift:.1f}×", other=t("falls") if target == "rise" else t("rises"), lift=o.get("lift") or 0)
    tides = []
    split = r.get("tide_split") or {}
    for k, (_icon, word) in sv.TIDE_WORDS.items():
        x = split.get(k) or {}
        if x.get("days"):
            tides.append({"tide": k, "word": t(word), "lift": None if x.get("lift") is None else round(x["lift"], 1),
                          "days": t("{n} days", n=x["days"])})
    return {"condition": r["condition"], "verdict": r.get("verdict"), "search": t("Search years") + ": " + first,
            "later": later, "tides": tides, "tides_label": t("By the Tide, all years"), "tides_hint": t(sv.TIDE_HINT),
            "theme": (t("+ {n} similar pairs found in the search (hover to see them)", n=r["theme_size"]) if r.get("theme_size") else ""),
            "theme_list": r.get("theme") or [], "lift": (c.get("lift") or 0), "search_lift": r.get("lift") or 0}


def report(market: str, lang: str) -> dict:
    import soundings_view as sv

    market = "equity" if market == "equity" else "crypto"
    with i18n.using(lang):
        t = i18n.t
        rep = sv.load(sv.FILES[market][0])
        if not rep:
            return {"ready": False, "message": t("This Soundings run is still being checked. It will show here soon.")}
        s = rep.get("settings") or {}
        first = ""
        if s.get("universe") == "equity_sample":
            first = t("- **Equities**: a fixed random sample of {n} companies from the S&P 500 as it stood at the start of 2016, including companies that later left the index, so the results are not flattered by looking only at today's winners.", n=len(s.get("coins") or []))
        if s.get("universe") == "wide":
            first = t("- **Coins**: the {n} most traded coins on Binance from 2018 to 2023, including coins that later collapsed or stopped trading, so the results are not flattered by looking only at survivors.", n=len(s.get("coins") or []))
        rest = t(
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
            coins=s.get("min_coins", ""), fdr=f"{100 * float(s.get('fdr', 0.1)):.0f}%")
        lines = rest.split("\n")
        if first and len(lines) > 1:
            del lines[1]
        how = "\n".join([first, *lines]) if first else "\n".join(lines)
        targets = {}
        for target in ("rise", "fall"):
            part = (rep.get("targets") or {}).get(target) or {}
            results = part.get("results") or []
            groups = []
            for v in sv.ORDER:
                group = [r for r in results if r.get("verdict") == v]
                if group:
                    cards = [_card(r, target) for r in sorted(group, key=lambda r: -((r.get("confirm") or {}).get("lift") or 0))[:12]]
                    groups.append({**_verdict(v), "count": len(group), "cards": cards})
            targets[target] = {
                "caption": t("Usually {usual} of closes were followed by {move}. Looked at {looked} conditions and pairs; "
                             "{kept} passed the search, in {themes} themes; the strongest of each theme was checked on the "
                             "later years.", usual=sv._pct(part.get("base_rate_search")),
                             move=t("a rise") if target == "rise" else t("a fall"), looked=part.get("looked_at", 0),
                             kept=part.get("search_survivors", 0), themes=part.get("themes", 0)),
                "empty": "" if results else t("Nothing passed the search: no condition came before {moves} clearly more often than usual.",
                                              moves=t("rises") if target == "rise" else t("falls")),
                "groups": groups}
        grid = sv.load_grid(sv.FILES[market][1])
        coins = []
        if grid and grid.get("coins"):
            coins = [[c, sv.asset_label(c)] for c in sorted(c for c, v in grid["coins"].items() if not v.get("stopped"))]
        return {"ready": True, "market": market, "how": how, "targets": targets, "coins": coins,
                "cut": (grid or {}).get("cut", ""), "first_coin": "BTC-USD" if any(c[0] == "BTC-USD" for c in coins) else ("AAPL" if any(c[0] == "AAPL" for c in coins) else (coins[0][0] if coins else ""))}


def chart(market: str, coin: str, period: str, target: str, faded: bool, dark: bool, lang: str) -> dict:
    """The chart script's data for one asset, period and move, and the per-result lines under it."""
    import pandas as pd
    import soundings_view as sv

    market = "equity" if market == "equity" else "crypto"
    target = "fall" if target == "fall" else "rise"
    with i18n.using(lang):
        t = i18n.t
        rep = sv.load(sv.FILES[market][0])
        grid = sv.load_grid(sv.FILES[market][1])
        if not rep or not grid or coin not in (grid.get("coins") or {}):
            return {"ready": False, "message": t("The chart's data is not available yet.")}
        c = grid["coins"][coin]
        years = [str(y) for y in range(int(grid["cut"][:4]), int(c["start"][:4]) - 1, -1)]
        end = grid["cut"]
        if period == "all":
            start = c["start"]
        elif period in years:
            start, end = f"{period}-01-01", min(f"{period}-12-31", end)
        else:
            period = "12m"
            start = (pd.Timestamp(end) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
        rows = sv.chart_rows(rep, target, faded)
        if not rows:
            return {"ready": True, "years": years, "payload": None, "message": t("No results to show for this move.")}
        payload, summary, base = sv.chart_payload(c, rows, target, start, end, dark, key=f"{coin}|{target}|{start}|{end}|{faded}")
        payload["lib"] = ""                                  # the new app provides the library itself
        lines = []
        if base is not None:
            move = t("a rise") if target == "rise" else t("a fall")
            head = t("**{coin}, this period:** {move} followed {usual} of all closes.", coin=coin.replace("-USD", ""), move=move, usual=f"{100 * base:.0f}%")
            for r, hit, total in summary:
                rate = f"{100 * hit / total:.0f}%" if total else "–"
                lift = f"{(hit / total) / base:.1f}×" if total and base else "–"
                lines.append(t("- {icon} {cond}: held on {n} closes; {move} after {rate} of them, against {usual} usually (**{lift}**)",
                               icon=sv.VERDICT.get(r.get("verdict"), ("",))[0], cond=" + ".join(r["condition"]), n=total,
                               move=move, rate=rate, usual=f"{100 * base:.0f}%", lift=lift))
            lines.insert(0, head)
        return {"ready": True, "years": years, "period": period, "payload": payload, "summary": "\n".join(lines),
                "caption": t("Price on top; below, one row per result: a square on each close where its condition held, coloured when the move followed and grey when it didn't. The top row shows the Tide. Research coins, to {cut}: the protected test period is never shown here.", cut=grid.get("cut", "")),
                "zoom": t("Zoom: scroll the wheel over the chart (or pinch), drag to move along, double-click the time axis to see it all. Hover a day for its details.")}


def as_set(condition: list[str], target: str, rise_lift: float, later_lift: float, lang: str) -> dict:
    """🧩 Open as Set: the result's condition as a new, unsaved Set (daily candles)."""
    import lattice_sets as ls
    import soundings as so

    with i18n.using(lang):
        t = i18n.t
        move = t("rises") if target == "rise" else t("falls")
        name = t("Soundings: {cond} ({move})", cond=" + ".join(condition), move=move)
        purpose = t("Came before {move} {lift:.1f}× as often as usual in the search years and {later:.1f}× on the later years (Soundings, daily candles).",
                    move=move, lift=rise_lift or 0, later=later_lift or 0)
        model = so.set_model([str(x) for x in condition][:6], name, purpose)
        if model is None:
            return {"ok": False, "message": t("This condition can't be opened as a Set yet.")}
        return {"ok": True, "model": ls.clean_model(model, {}), "message": t("Opened from Soundings as a new Set. Check it, then save it.")}
