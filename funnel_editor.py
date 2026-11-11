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

# A quiet funnel drawn behind the stages: wide at the top, narrowing down the page to a spout. Flat, low-contrast,
# stretched to the stages' size (so it scales with the window), and behind the content (clicks pass through).
_FUNNEL_SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' preserveAspectRatio='none'>"
               "<polygon points='0,0 100,0 60,84 60,100 40,100 40,84' fill='%23818cf8' fill-opacity='0.09'/>"
               "<polygon points='6,3 94,3 58,82 42,82' fill='none' stroke='%23818cf8' stroke-opacity='0.12' "
               "stroke-width='0.4' vector-effect='non-scaling-stroke'/></svg>")
FUNNEL_CSS = ("<style>.st-key-funnel_stages_art{position:relative;}"
              ".st-key-funnel_stages_art::before{content:'';position:absolute;inset:0;pointer-events:none;z-index:0;"
              f"background:url(\"data:image/svg+xml;utf8,{_FUNNEL_SVG}\") center/100% 100% no-repeat;}}"
              ".st-key-funnel_stages_art>div{position:relative;z-index:1;}</style>")


# ----------------------------------------------------------------------------------------------- pure helpers

def template(market: str, direction: str) -> dict:
    t = ft.trend_funnel(direction, market)
    return {"id": None, "name": t["name"], "direction": direction, "market": market, "stages": t["stages"],
            "flicker": True, "alerts": {"in_app": True, "email": False}, "pool": {}, "paused": False}


def provenance(f: dict, library: dict) -> str:
    """For your own funnels: 'Your copy of a provided funnel' (unchanged), 'Customised' (started from one, changed) or
    'My funnel'. (A provided original itself is shown read-only, as provided Groups and Sets are.)"""
    made = ft.trend_funnel(f["direction"], f.get("market") or "crypto")
    if [s["set_body"] for s in f["stages"]] == [s["set_body"] for s in made["stages"]] and \
            [s["timeframe"] for s in f["stages"]] == [s["timeframe"] for s in made["stages"]]:
        return "Your copy of a provided funnel"
    keys = [provided_key(s.get("set_source")) for s in f["stages"]]
    if all(k and k in library and library[k] == s.get("set_body") for k, s in zip(keys, f["stages"])) and \
            [s["timeframe"] for s in f["stages"]] == [s["timeframe"] for s in made["stages"]]:
        return "Your copy of an earlier version of a provided funnel"
    if any(str(k or "").startswith("demo:") for k in keys):
        return "Customised"
    return "My funnel"


def provided_key(src: dict | None) -> str | None:
    """The library key of a provided stage Set. The first funnels (10 Nov) recorded "funnel:trend:<tf>:<direction>"
    and "funnel:entry:<direction>"; those name the same Sets as today's keys."""
    key = (src or {}).get("provided")
    if not key:
        return None
    parts = str(key).split(":")
    if parts[0] == "funnel" and len(parts) == 4 and parts[1] == "trend":
        return ft.library_key(parts[2], parts[3])
    if parts[0] == "funnel" and len(parts) == 3 and parts[1] == "entry":
        return ft.library_key(None, parts[2])
    return key


def upgrade_for(stage: dict, library: dict, saved_sets: dict) -> tuple[str, dict, dict] | None:
    """(button text, newer Set body, its source) when the stage's Set has a newer version, else None."""
    src = stage.get("set_source") or {}
    key = provided_key(src)
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
    key = provided_key(src)
    if key and f"provided:{key}" in choices:
        return f"provided:{key}"
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
        names[f"new:{m}:{d}"] = (f"{'🪙' if m == 'crypto' else '🏛️'} {template(m, d)['name']} (provided)")
    pick = st.selectbox("Funnel", keys, format_func=names.get, key="funnel_edit",
                        help="Your own funnels first, then the provided ones (marked provided). As with provided "
                             "Groups and Sets, a provided funnel can't be changed or deleted: make your own copy to "
                             "use it. At most 6 of your own.")
    if pick.startswith("new:"):
        _provided_view(st, supabase, pick, funnels, library)
        return

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
                + ("" if badge.startswith("Your copy") else " · not reviewed or tested by Angstrom"))
    if badge.startswith("Your copy of an earlier version"):
        latest = template(market, f["direction"])
        if st.button("⬆ Update to the latest provided version", key=f"fe_latest_{pick}",
                     help="Angstrom's provided funnel has changed since you made your copy (its daily stage now reads "
                          "WaveTrend turning back from an extreme). This takes its stages; your name, pool and alerts "
                          "stay. Then Save and activate: every asset starts again from the pool, quietly."):
            f["stages"] = copy.deepcopy(latest["stages"])
            lattice_panel.rerun(st)

    # ------------------------------------------------------------------ basics
    c1, c2 = st.columns(2)
    f["name"] = c1.text_input("Name", value=f["name"], max_chars=80, key=f"fe_name_{pick}")
    f["direction"] = c2.radio("Direction", ["long", "short"], index=0 if f["direction"] == "long" else 1,
                              horizontal=True, key=f"fe_dir_{pick}",
                              format_func=lambda d: "▲ Long" if d == "long" else "▼ Short",
                              help="Long and short are separate funnels; a ready-made one has its own Sets for each.")
    c3, c4 = st.columns(2)
    flick = c3.radio(f"{'A coin' if market == 'crypto' else 'An equity'} leaves a stage", ["two", "one"], index=0 if f.get("flicker", True) else 1,
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
    paused = bool(f.get("paused"))
    if st.button("", icon=":material/play_arrow:" if paused else ":material/pause:", key=f"fe_pause_{pick}",
                 help=("Paused: not checked; it keeps its places. Press to resume." if paused else
                       "Pause: stop checking this funnel; it keeps its places until resumed.")):
        f["paused"] = not paused
        if saved:                                   # as in Prism: pausing applies at once, nothing else changes
            live = {**copy.deepcopy(saved), "paused": f["paused"]}
            try:
                supabase.rpc("funnel_save", save_args(live)).execute()
                saved["paused"] = f["paused"]
                _refresh(st)
                st.toast("Paused." if f["paused"] else "Resumed.")
            except Exception as exc:
                st.error(f"That didn't work: {str(exc)[:160]}")
        lattice_panel.rerun(st)
    if paused:
        st.caption("⏸ Paused: not checked until resumed.")

    # ------------------------------------------------------------------ pool
    pool = dict(f.get("pool") or {})
    whole = "the top 500 coins" if market == "crypto" else "the S&P 500"
    box = st.container(border=True)
    box.markdown("**Pool** · which assets the funnel starts from", help=(
        f"All eligible = {whole} that pass Angstrom's data checks. Narrow it by size, by how much trades a day "
        "(on the coin's venue: Binance, or across exchanges for Yahoo coins; equities in New York), or to your own "
        "watchlist. Changing the pool starts every asset again from the pool."))
    p1, p2, p3 = box.columns([2, 2, 1.4], vertical_alignment="bottom")
    sizes = [0, 50, 100, 200, 500]
    top = p1.selectbox("Size", sizes, index=sizes.index(int(pool.get("top") or 0)), key=f"fe_top_{pick}",
                       format_func=lambda n: "All eligible" if n == 0 else f"Top {n} by market cap")
    floors = [0, 250_000, 1_000_000, 5_000_000, 20_000_000, 100_000_000]
    current = int(pool.get("min_volume") or 0)
    if current not in floors:
        floors = sorted(floors + [current])
    vol = p2.selectbox("Traded a day, at least", floors, index=floors.index(current), key=f"fe_vol_{pick}",
                       format_func=lambda v: "No extra minimum" if v == 0 else
                       (f"${v / 1e6:g}M" if v >= 1e6 else f"${v / 1e3:g}k"))
    only = p3.toggle("Only my watchlist", value=bool(pool.get("watchlist_only")), key=f"fe_watch_{pick}",
                     help="The funnel checks only your own watchlist's eligible "
                          f"{'coins' if market == 'crypto' else 'equities'}, not the market.")
    f["pool"] = {k: v for k, v in (("top", top or None), ("min_volume", vol or None), ("watchlist_only", only or None))
                 if v}

    # ------------------------------------------------------------------ stages
    # A fixed title: Streamlit treats a folding section with a new title as a new one and folds it, so naming the
    # stages in the title closed it whenever a stage was added, removed, moved or renamed.
    st.caption("Stages: " + " → ".join(s.get("label") or s["timeframe"] for s in f["stages"]))
    with st.expander("Stages (advanced)", icon=":material/stacks:"):
        st.caption("Each stage checks one Set, only for the assets that hold every stage before it. The timeframe is "
                   "**when the stage is checked**; the Set's readings keep their own timeframes. To change a threshold, "
                   "edit a copy of the Set in Signal Sets, then pick it here.")
        keys_ = list(choices)
        st.markdown(FUNNEL_CSS, unsafe_allow_html=True)
        stages_box = st.container(key="funnel_stages_art")
        for i, stage in enumerate(list(f["stages"])):
            box = stages_box.container(border=True)
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


def _provided_view(st, supabase, pick: str, funnels: list[dict], library: dict) -> None:
    """A provided funnel, read-only (as a provided Group or Set): what it does, and Make my own copy."""
    _, market, direction = pick.split(":")
    t = template(market, direction)
    st.markdown(f"**{MARKET_WORDS[market]}** · {fn.DIRECTION_ICONS[direction]} "
                f"{'Long' if direction == 'long' else 'Short'} · *Provided by Angstrom* · can't be changed or deleted")
    pool = "the top 500 coins that pass Angstrom's data checks" if market == "crypto" else "the S&P 500"
    st.caption(f"Starts from {pool}. {'A coin' if market == 'crypto' else 'An equity'} leaves a stage after two No "
               "closes in a row. Alerts on new Candidates.")
    for i, stage in enumerate(t["stages"], 1):
        doc = stage["set_body"]
        st.markdown(f"**{i}. {stage['label']}** · checked at each {fs.WORDS[stage['timeframe']]} close  \n"
                    f"{doc['name']}: {doc.get('purpose') or ''}")
    st.caption(NOTE)
    mine = [f for f in funnels if f.get("market") == market and f.get("direction") == direction
            and provenance(f, library) == "Your copy of a provided funnel"]
    if mine:
        st.caption(f"You already have an unchanged copy: **{mine[0]['name']}**.")
    if st.button("Make my own copy", type="primary", icon=":material/content_copy:", key=f"fe_copy_{pick}",
                 disabled=len(funnels) >= 6,
                 help="Your copy runs for your account, with its own places and alerts. You can then change it, "
                      "pause it or delete it; this provided one stays as it is."):
        _save(st, supabase, t, None, {})


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
