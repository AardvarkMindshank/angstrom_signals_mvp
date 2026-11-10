"""
🔻 Funnels in Angstrom Lattice (the approved decision in docs/research/funnel_editor_brief_2026-11-10.md; contracts in
docs/design/funnels_v2_spec.md).

Start from a ready-made funnel or one of your own → change it → save and activate. Beginners change the direction,
the pool and the leave rule; "Stages (advanced)" opens the stages themselves: any provided or saved Set, the close it
is checked at, add, remove and reorder, and ⬆ Upgrade when a stage's Set has a newer version. Changes are kept as a
working copy until they are saved, so the live funnel is never reset by accident; what a save will reset is shown
first.
"""

from __future__ import annotations

import copy

import funnel as fn
import funnel_spec as fs
import funnel_templates as ft
import funnel_view as fv

TEMPLATES = [("crypto", "long"), ("crypto", "short"), ("equity", "long"), ("equity", "short")]
MARKET_WORDS = {"crypto": "Crypto", "equity": "Equities"}
TF_LABELS = {"15m": "15 minutes", "30m": "30 minutes", "1h": "1 hour", "4h": "4 hours", "12h": "12 hours",
             "1D": "1 day", "1W": "1 week"}
NOTE = "Candidate means an asset matches your selected conditions. It is not a recommendation to trade."


# ----------------------------------------------------------------------------------------------- pure helpers

def template(market: str, direction: str) -> dict:
    t = ft.trend_funnel(direction, market)
    return {"id": None, "name": t["name"], "direction": direction, "market": market, "stages": t["stages"],
            "flicker": True, "alerts": {"in_app": True, "email": False}, "pool": {}, "paused": False}


def provenance(f: dict, library: dict) -> str:
    """'Provided by Angstrom' (a ready-made funnel, unchanged), 'Customised' (started from one, changed) or 'My funnel'."""
    made = ft.trend_funnel(f["direction"], f.get("market") or "crypto")
    if [s["set_body"] for s in f["stages"]] == [s["set_body"] for s in made["stages"]] and \
            [s["timeframe"] for s in f["stages"]] == [s["timeframe"] for s in made["stages"]]:
        return "Provided by Angstrom"
    if any(str((s.get("set_source") or {}).get("provided") or "").startswith("demo:") for s in f["stages"]):
        return "Customised"
    return "My funnel"


def upgrade_for(stage: dict, library: dict, saved_sets: dict) -> tuple[str, dict, dict] | None:
    """(button text, newer Set body, its source) when the stage's Set has a newer version, else None."""
    src = stage.get("set_source") or {}
    key = src.get("provided")
    if key and key in library and library[key] != stage.get("set_body"):
        return "⬆ Upgrade to the latest provided version", copy.deepcopy(library[key]), {"provided": key}
    cid = src.get("config_id")
    if cid and cid in saved_sets:
        latest = saved_sets[cid]["versions"][-1]
        if int(latest["version"]) > int(src.get("version") or 0):
            return (f"⬆ Upgrade to version {latest['version']}", copy.deepcopy(latest["body"]),
                    {"config_id": cid, "version": latest["version"]})
    return None


def changes(old: dict | None, new: dict) -> tuple[list[str], bool]:
    """(what changed, in words; does saving start every asset again from the pool?)"""
    if not old:
        return ["A new funnel: it starts quietly, without alerts for what already qualifies."], False
    out, reset = [], False
    if [s["set_body"] for s in old["stages"]] != [s["set_body"] for s in new["stages"]] or \
            [s["timeframe"] for s in old["stages"]] != [s["timeframe"] for s in new["stages"]]:
        out.append("The stages changed (a Set, a check timeframe, a stage added, removed or moved).")
        reset = True
    if (old.get("pool") or {}) != (new.get("pool") or {}):
        out.append("The pool changed.")
        reset = True
    if old.get("direction") != new.get("direction"):
        out.append("The direction changed.")
    if bool(old.get("flicker", True)) != bool(new.get("flicker", True)):
        out.append("The leave rule changed.")
    if (old.get("alerts") or {}) != (new.get("alerts") or {}):
        out.append("The alerts changed.")
    if old.get("name") != new.get("name") or [s.get("label") for s in old["stages"]] != [s.get("label") for s in
                                                                                          new["stages"]]:
        out.append("Names changed.")
    if bool(old.get("paused")) != bool(new.get("paused")):
        out.append("Paused." if new.get("paused") else "Resumed.")
    return out, reset


def save_args(f: dict) -> dict:
    args = {"p_id": f.get("id"), "p_name": f["name"].strip() or "My funnel", "p_direction": f["direction"],
            "p_stages": f["stages"], "p_flicker": bool(f.get("flicker", True)),
            "p_alerts": f.get("alerts") or {"in_app": True, "email": False}, "p_paused": bool(f.get("paused"))}
    if (f.get("market") or "crypto") != "crypto" or f.get("pool"):
        args["p_market"] = f.get("market") or "crypto"
    if f.get("pool"):
        args["p_pool"] = f["pool"]
    return args


# ----------------------------------------------------------------------------------------------- the section

def _set_choices(library: dict, saved_sets: dict) -> dict:
    """key -> (label, body, source) for every Set a stage can use: the provided ones, then your own (latest)."""
    import perspectives

    out = {}
    for key, doc in library.items():
        if doc.get("decision"):
            out[f"provided:{key}"] = (f"{doc['name']} {perspectives.icons(doc)} (provided)", doc, {"provided": key})
    for cid, c in saved_sets.items():
        latest = c["versions"][-1]
        if (latest.get("body") or {}).get("decision"):
            out[f"saved:{cid}"] = (f"{c['name']} v{latest['version']} (yours)", latest["body"],
                                   {"config_id": cid, "version": latest["version"]})
    return out


def _choice_of(stage: dict, choices: dict) -> str | None:
    src = stage.get("set_source") or {}
    if src.get("provided") and f"provided:{src['provided']}" in choices:
        return f"provided:{src['provided']}"
    if src.get("config_id") and f"saved:{src['config_id']}" in choices:
        return f"saved:{src['config_id']}"
    return None


def render(st, supabase, user_id: str) -> None:
    import time

    import lattice_panel
    import prism
    import signal_groups_inspector as gi

    st.caption("🔻 A funnel narrows the top coins or equities down in stages, from the longest timeframe to the hour, and "
               "keeps the list up to date by itself. It shows as **Dynamic funnel** above the crypto and equity "
               "tables. " + NOTE)
    funnels = fv.load_funnels(supabase, user_id)
    library = prism.demo_sets()
    memo = st.session_state.setdefault("_memo", {})
    hit = memo.get("funnel_sets")
    if hit and time.time() - hit[0] < 60:
        configs = hit[1]
    else:
        configs, _err = gi.saved_configs(supabase)
        memo["funnel_sets"] = (time.time(), configs)
    saved_sets = {c["id"]: c for c in configs if c.get("kind") == "set" and str(c.get("owner_id")) == str(user_id)}

    nxt = st.session_state.pop("_funnel_edit_next", None)
    keys = [f["id"] for f in funnels] + [f"new:{m}:{d}" for m, d in TEMPLATES]
    if nxt in keys:
        st.session_state["funnel_edit"] = nxt
    if st.session_state.get("funnel_edit") not in keys:
        st.session_state["funnel_edit"] = keys[0]
    names = {f["id"]: f"{'🪙' if (f.get('market') or 'crypto') == 'crypto' else '🏛️'} {f['name']}"
             + (" (paused)" if f.get("paused") else "") for f in funnels}
    for m, d in TEMPLATES:
        names[f"new:{m}:{d}"] = f"➕ Start from: {template(m, d)['name']} ({MARKET_WORDS[m].lower()})"
    pick = st.selectbox("Funnel", keys, format_func=names.get, key="funnel_edit",
                        help="Your funnels, then the ready-made ones to start a new funnel from. At most 6.")

    saved = next((f for f in funnels if f["id"] == pick), None)
    drafts = st.session_state.setdefault("_funnel_drafts", {})
    if pick not in drafts:
        base = copy.deepcopy(saved) if saved else template(*pick.split(":")[1:3])
        base.setdefault("pool", {})
        drafts[pick] = base
    f = drafts[pick]
    market = f.get("market") or "crypto"
    choices = _set_choices(library, saved_sets)

    badge = provenance(f, library)
    st.markdown(f"**{MARKET_WORDS[market]}** · {fn.DIRECTION_ICONS[f['direction']]} "
                f"{'Long' if f['direction'] == 'long' else 'Short'} · *{badge}*"
                + ("" if badge == "Provided by Angstrom" else " · not reviewed or tested by Angstrom"))

    # ------------------------------------------------------------------ basics
    c1, c2 = st.columns(2)
    f["name"] = c1.text_input("Name", value=f["name"], max_chars=80, key=f"fe_name_{pick}")
    f["direction"] = c2.radio("Direction", ["long", "short"], index=0 if f["direction"] == "long" else 1,
                              horizontal=True, key=f"fe_dir_{pick}",
                              format_func=lambda d: "▲ Long" if d == "long" else "▼ Short",
                              help="Long and short are separate funnels; a ready-made one has its own Sets for each.")
    c3, c4 = st.columns(2)
    flick = c3.radio("A coin leaves a stage", ["two", "one"], index=0 if f.get("flicker", True) else 1,
                     horizontal=True, key=f"fe_flick_{pick}",
                     format_func=lambda x: "after 2 No closes in a row" if x == "two" else "on the first No",
                     help="Two in a row stops coins flickering in and out near a threshold (recommended).")
    f["flicker"] = flick == "two"
    alerts = dict(f.get("alerts") or {"in_app": True, "email": False})
    alerts["in_app"] = c4.toggle("Alert me on new Candidates", value=bool(alerts.get("in_app", True)),
                                 key=f"fe_alert_{pick}", help="One message per hourly run, only for new Candidates.")
    alerts["first_matches"] = c4.toggle("…including the first run", value=bool(alerts.get("first_matches")),
                                        key=f"fe_first_{pick}",
                                        help="Off (recommended): a new or changed funnel starts quietly, without "
                                             "alerts for everything that already qualifies.")
    if not alerts["first_matches"]:
        alerts.pop("first_matches")
    f["alerts"] = alerts
    f["paused"] = st.toggle("Paused", value=bool(f.get("paused")), key=f"fe_pause_{pick}",
                            help="A paused funnel isn't checked; it keeps its places until resumed.")

    # ------------------------------------------------------------------ pool
    with st.expander("Pool: which assets the funnel starts from", icon=":material/filter_list:"):
        pool = dict(f.get("pool") or {})
        whole = "the top 500 coins (eligible on Binance or Yahoo)" if market == "crypto" else "the S&P 500"
        sizes = [0, 50, 100, 200, 500]
        top = st.selectbox("Size", sizes, index=sizes.index(int(pool.get("top") or 0)), key=f"fe_top_{pick}",
                           format_func=lambda n: f"All eligible: {whole}" if n == 0 else f"Top {n} by market cap")
        vol = st.number_input("Minimum traded a day (US$, 0 = no extra minimum)", min_value=0, max_value=10_000_000_000,
                              value=int(pool.get("min_volume") or 0), step=250_000, key=f"fe_vol_{pick}",
                              help="On the coin's venue (Binance) or across exchanges (Yahoo coins); equities: in New York.")
        only = st.toggle("Only my watchlist", value=bool(pool.get("watchlist_only")), key=f"fe_watch_{pick}",
                         help="The funnel checks only your own watchlist's eligible "
                              f"{'coins' if market == 'crypto' else 'equities'}, not the market.")
        pool = {k: v for k, v in (("top", top or None), ("min_volume", vol or None), ("watchlist_only", only or None))
                if v}
        f["pool"] = pool

    # ------------------------------------------------------------------ stages
    with st.expander(f"Stages (advanced): {' → '.join(s.get('label') or s['timeframe'] for s in f['stages'])}",
                     icon=":material/stacks:"):
        st.caption("Each stage checks one Set, only for the assets that hold every stage before it. The timeframe is "
                   "**when the stage is checked**; the Set's readings keep their own timeframes. To change a threshold, "
                   "edit a copy of the Set in Signal Sets, then pick it here.")
        keys_ = list(choices)
        for i, stage in enumerate(list(f["stages"])):
            box = st.container(border=True)
            a, b = box.columns([2, 1])
            stage["label"] = a.text_input(f"Stage {i + 1}", value=stage.get("label") or "", max_chars=40,
                                          key=f"fe_lab_{pick}_{i}")
            tfs = list(fs.TIMEFRAMES)
            stage["timeframe"] = b.selectbox("Checked at each … close", tfs, index=tfs.index(stage["timeframe"]),
                                             format_func=TF_LABELS.get, key=f"fe_tf_{pick}_{i}")
            current = _choice_of(stage, choices)
            options = keys_ if current else ["(kept as it is)"] + keys_
            chosen = box.selectbox("Set", options, index=options.index(current) if current else 0,
                                   format_func=lambda k: choices[k][0] if k in choices else
                                   f"{stage['set_body'].get('name', 'This stage’s Set')} (kept as it is)",
                                   key=f"fe_set_{pick}_{i}")
            if chosen in choices and chosen != current:
                stage["set_body"], stage["set_source"] = copy.deepcopy(choices[chosen][1]), choices[chosen][2]
            up = upgrade_for(stage, library, saved_sets)
            row = box.container(horizontal=True, gap="small")
            if up and row.button(up[0], key=f"fe_up_{pick}_{i}",
                                 help="Use the newer version of this Set. Saving then starts every asset again."):
                stage["set_body"], stage["set_source"] = up[1], up[2]
                lattice_panel.rerun(st)
            if i > 0 and row.button("↑", key=f"fe_upmove_{pick}_{i}", help="Move this stage up"):
                f["stages"][i - 1], f["stages"][i] = f["stages"][i], f["stages"][i - 1]
                lattice_panel.rerun(st)
            if i < len(f["stages"]) - 1 and row.button("↓", key=f"fe_down_{pick}_{i}", help="Move this stage down"):
                f["stages"][i + 1], f["stages"][i] = f["stages"][i], f["stages"][i + 1]
                lattice_panel.rerun(st)
            if len(f["stages"]) > 3 and row.button("Remove", icon=":material/delete:", key=f"fe_rm_{pick}_{i}"):
                f["stages"].pop(i)
                lattice_panel.rerun(st)
        if len(f["stages"]) < 5 and st.button("Add a stage", icon=":material/add:", key=f"fe_add_{pick}"):
            last = copy.deepcopy(f["stages"][-1])
            last["label"] = f"Stage {len(f['stages']) + 1}"
            f["stages"].append(last)
            lattice_panel.rerun(st)

    # ------------------------------------------------------------------ check, summary, save
    blocks, warns = fs.validate(f)
    for b in blocks:
        st.error(b, icon=":material/block:")
    for w in warns:
        st.warning(w, icon=":material/info:")
    what, reset = changes(saved, f)
    if saved and not what:
        st.caption("No changes.")
    else:
        st.caption("**If you save:** " + " ".join(what)
                   + (" Every asset starts again from the pool, quietly (no alerts for what already qualifies)."
                      if reset else ""))
    bar = st.container(horizontal=True, gap="small")
    if bar.button("Save and activate" if saved else "Create this funnel", type="primary", icon=":material/save:",
                  disabled=bool(blocks) or (saved is not None and not what), key=f"fe_save_{pick}"):
        _save(st, supabase, f, pick, drafts)
    if saved and bar.button("Discard changes", icon=":material/undo:", key=f"fe_discard_{pick}", disabled=not what):
        drafts.pop(pick, None)
        for k in [k for k in st.session_state.keys() if str(k).startswith("fe_") and str(k).endswith(pick)]:
            st.session_state.pop(k, None)
        lattice_panel.rerun(st)
    if saved and bar.button("Duplicate", icon=":material/content_copy:", key=f"fe_dup_{pick}",
                            disabled=len(funnels) >= 6, help="A copy to experiment with; this one keeps running."):
        copy_ = copy.deepcopy(saved)
        copy_["id"], copy_["name"] = None, f"{saved['name']} (copy)"[:80]
        _save(st, supabase, copy_, None, drafts)
    if saved:
        with bar.popover("Delete", icon=":material/delete:"):
            st.caption("The funnel and its places are deleted for good.")
            if st.button(f"Delete “{saved['name']}”", type="primary", key=f"fe_del_{pick}"):
                try:
                    supabase.rpc("funnel_delete", {"p_id": saved["id"]}).execute()
                    drafts.pop(pick, None)
                    st.session_state.pop("funnel_edit", None)
                    _refresh(st)
                    st.toast("Funnel deleted.")
                    lattice_panel.rerun_page(st)
                except Exception as exc:
                    st.error(f"That didn't work: {str(exc)[:160]}")


def _refresh(st) -> None:
    for market in ("crypto", "equity"):
        st.session_state[f"_funnels_reread_{market}"] = True


def _save(st, supabase, f: dict, pick: str | None, drafts: dict) -> None:
    import lattice_panel

    args = save_args(f)
    try:
        res = supabase.rpc("funnel_save", args).execute()
    except Exception as exc:
        text = str(exc)
        if "too_many_funnels" in text:
            st.error("You already have 6 funnels: delete one first.")
        elif "p_pool" in text or ("funnel_save" in text and "function" in text.lower()):
            st.error("The database update for funnel pools hasn't been run yet (sql/2026-11-20_funnel_pools.sql).")
        else:
            st.error(f"Could not save it: {text[:200]}")
        return
    new_id = getattr(res, "data", None)
    if pick in drafts:
        drafts.pop(pick, None)
    if isinstance(new_id, str):
        st.session_state["_funnel_edit_next"] = new_id
    _refresh(st)
    st.toast("Saved. The funnel fills in at the next hourly check.")
    lattice_panel.rerun_page(st)
