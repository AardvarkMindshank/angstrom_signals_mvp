"""🌊 The Tides page for the new app: the classic Tides panel (tides_view.py), as data. The sky-and-sea drawing and the
waves chart are the classic SVGs (passed as image sources); everything else is words and numbers for the page to lay
out in the new style. Read from the snapshot the worker saves every 6 hours (tides.latest)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import i18n


def _src(img_html: str) -> str:
    m = re.search(r"src='(data:image/svg\+xml;base64,[^']+)'", img_html or "")
    return m.group(1) if m else ""


def build(db, lang: str, range_key: str = "1Y") -> dict:
    import macro_calendar as mc
    import tides as td
    import tides_view as tv

    with i18n.using(lang):
        t = i18n.t
        snap = td.latest(db)
        tide = (snap or {}).get("tide") or {}
        if not snap or tide.get("status") != "ok":
            return {"ready": False}
        now = datetime.now(timezone.utc)
        upcoming = mc.upcoming(now, days=35)
        warning = mc.storm_warning(now)
        sea = snap.get("sea") or {}
        state = sea.get("state") or "moderate"
        name, plain, _ = td.TIDE_WORDS[tide["label"]]
        hero = {"src": _src(tv.hero(snap, warning, now)), "dark": state in ("rough", "storm"), "label": tide["label"],
                "name": t(name), "plain": t(plain), "held": t("for {n} trading days", n=tide["held_days"]),
                "pending": (t("turning: readings point to {td_tide_words_t_raw_labe}, confirmed after 5 closes",
                              td_tide_words_t_raw_labe=t(td.TIDE_WORDS[tide["raw_label"]][0]).lower())
                            if tide.get("pending") else ""),
                "score": t("score {s:+.2f}", s=tide["score"]),
                "sea": (t("Sea {state}", state=t(sea["state"])), t(sea["plain"])) if sea.get("status") == "ok" else None,
                "winds": [], "warning": None}
        for w in (snap.get("winds") or {}).values():
            word = {"headwind": t("headwind (risk against)"), "tailwind": t("tailwind (risk with)"), "neither": t("no clear wind")}[w["wind"]]
            why = ", ".join(t(td.SPEC[k]["name"]) for k in w["drivers"]) or t("no single current")
            tip = t("{name}: {word}. Led by {why}.", name=t(w["name"]), word=word, why=why)
            if w.get("against"):
                tip += t(" Pushing the other way: {join_td_spec_k_name_for_}.",
                         join_td_spec_k_name_for_=", ".join(t(td.SPEC[k]["name"]) for k in w["against"]))
            hero["winds"].append({"wind": w["wind"], "icon": tv.WIND_ICON[w["wind"]], "name": t(w["name"]),
                                  "word": t(w["wind"]) if w["wind"] != "neither" else t("no clear wind"), "tip": tip})
        if warning:
            hero["warning"] = {"flags": mc.pennants(warning["tier"]), "short": t(warning["short"]),
                               "when": mc.when_words(warning["at"], now),
                               "tip": t("{warning_name} ({warning_reference}): {warning_why} A scheduled event, not a forecast.",
                                        warning_name=t(warning["name"]), warning_reference=warning["reference"],
                                        warning_why=t(warning["why"]))}
        events = []
        for e in upcoming[:10]:
            delta = (e["at"] - now).total_seconds()
            local = e["at"].astimezone(mc.NEW_YORK)
            events.append({"state": "past" if delta < 0 else "now" if delta < 24 * 3600 else "",
                           "flags": mc.pennants(e["tier"]), "icon": e["icon"], "name": t(e["short"]), "ref": e["reference"],
                           "day": f"{local:%a %d %b}", "when": mc.when_words(e["at"], now),
                           "tip": t("{name} ({ref}) at {time} New York.", name=t(e["name"]), ref=e["reference"], time=f"{local:%H:%M}")
                                  + f" {t(e['why'])}" + (f" ({e['note']})" if e["note"] else "") + " " + t("A scheduled event, not a forecast.")})
        cur = snap.get("currents") or {}
        families = []
        for fam in tv.FAMILY_ORDER:
            fname, weight, icon = td.FAMILIES[fam]
            score = (tide.get("families") or {}).get(fam)
            cards = []
            for k in td.CURRENT_KEYS:
                spec = td.SPEC[k]
                if spec["family"] != fam or k not in cur:
                    continue
                c = cur[k]
                if c.get("status") != "ok":
                    cards.append({"icon": spec["icon"], "name": t(spec["name"]), "none": True, "tip": t(spec["measures"])})
                    continue
                pull, cls, _ = tv.pull_of(c)
                meaning = t(spec[c["direction"]]) if c["direction"] in ("rising", "falling") else t("little change over 30 days")
                votes = t("Votes in the Tide.") if c["weight"] else t("Shown on its own; does not vote in the Tide.")
                tip = (t(spec["measures"]) + ". " + t("{direction}: {meaning}. Today's level is {band} for the past 5 years (score {score:.0f}/100).",
                                                       direction=t(c["direction"]).capitalize(), meaning=meaning, band=t(c["band"]), score=c["score"])
                       + " " + votes + " " + t("Change: 7 days {c7}, 30 days {c30}. As of {when}.", c7=tv.fmt_change(c, "change_7"),
                                               c30=tv.fmt_change(c), when=c["as_of"]))
                cards.append({"icon": spec["icon"], "name": t(spec["name"]), "value": tv.fmt_value(c),
                              "band": f"{t(c['band'])} · {c['score']:.0f}/100", "arrow": tv.ARROW[c["direction"]],
                              "dir": f"{t(c['direction'])} · {t(pull)}", "tone": {"pos": "good", "neg": "bad"}.get(cls, ""),
                              "change": t("30 days {change}", change=tv.fmt_change(c)), "voting": bool(c["weight"]),
                              "spark": [v for v in c.get("spark") or [] if v is not None], "positive_good": spec["sign"] > 0,
                              "tip": tip})
            families.append({"icon": icon, "name": t(fname), "meta": t("weight {w:.0%}", w=weight) + ("" if score is None else t(" · pull {score:+.2f}", score=score)),
                             "cards": cards})
        side = []
        fng = snap.get("fear_greed")
        if fng is not None:
            mood = ("extreme fear" if fng < 25 else "fear" if fng < 45 else "neutral" if fng <= 55 else "greed" if fng <= 75 else "extreme greed")
            side.append({"name": "😱 " + t("Crypto Fear & Greed"), "val": f"{fng:.0f}/100 · {t(mood)}", "meta": t("not in the Tide"),
                         "tip": t("Alternative.me crypto Fear and Greed. Shown on its own: it already sits inside the crypto sentiment score, so it never votes in the Tide.")})
        dom = snap.get("btc_dominance")
        if dom is not None:
            side.append({"name": "₿ " + t("Bitcoin share"), "val": f"{dom:.1f}%", "meta": t("crypto rotation, shown"),
                         "tip": t("Bitcoin's share of the whole crypto market (CoinGecko). Rising often means money retreating to Bitcoin; falling, money moving out to altcoins.")})
        ex = snap.get("extras") or {}
        if ex.get("long_30y"):
            side.append({"name": "📏 " + t("30-year yield"), "val": f"{ex['long_30y']['value']:.2f}%",
                         "meta": t("30 days {change}", change=f"{ex['long_30y']['change_30']:+.2f} pts"),
                         "tip": t("30-year Treasury yield, shown beside long rates (the 10-year votes).")})
        if ex.get("copper"):
            side.append({"name": "🔶 " + t("Copper"), "val": f"${ex['copper']['value']:.2f}/lb",
                         "meta": t("30 days {change}", change=f"{ex['copper']['change_30']:+.1f}%"),
                         "tip": t("Copper on its own (copper against gold votes).")})
        for key, nm, tip in (("cyclical_defensive", t("🛍️ Cyclical vs defensive"), t("Consumer discretionary against consumer staples (XLY vs XLP): rises when money favours growth-sensitive sectors.")),
                             ("small_large", t("🐟 Small vs large"), t("Small companies against large (IWM vs SPY): rises with broad risk appetite."))):
            r = ex.get(key)
            if r and r.get("change_30") is not None:
                side.append({"name": nm, "val": t("30 days {change}", change=f"{r['change_30']:+.1f}%"),
                             "meta": t("{band} for 5 years", band=t(td.band(r.get("score")) or "")), "tip": tip})
        return {"ready": True, "hero": hero, "note": td.summary(snap, upcoming, now), "events": events,
                "waves": _src(tv.waves(snap, range_key if range_key in tv.RANGES else "1Y")), "ranges": list(tv.RANGES),
                "range": range_key if range_key in tv.RANGES else "1Y", "families": families, "side": side,
                "since": td.since(snap), "tide_score": None if tide.get("score") is None else round(float(tide["score"]) * 100),
                "tide_words": " ".join(td.TIDE_WORDS.get(tide.get("label"), ("", "", ""))[:2]),
                "stamp": (snap.get("computed_at") or "")[:16].replace("T", " ")}
