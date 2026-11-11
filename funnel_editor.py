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

# The stages themselves are drawn by funnel_stages_component.py (the Set list as in Prism, the funnel beside it).


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
        problem = st.session_state.pop("funnel_stages_flash", None)
        if problem:
            st.warning(problem, icon=":material/info:")
        _stages_board(st, f, pick, configs, user_id, library, saved_sets)

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



# ----------------------------------------------------------------------------------------------- the stages board

MIN_STAGES, MAX_STAGES = 3, 5


def board_choices(configs: list[dict], user_id: str) -> dict:
    """The Sets a stage can use, exactly as Prism lists them: key -> {name, meta, doc, config, version, provided}."""
    import prism_board as pb

    return pb.set_choices(configs, user_id)


def _from_choice(key: str, choices: dict) -> tuple[dict, dict] | None:
    c = choices.get(key)
    if c is None:
        return None
    if c.get("provided"):
        return copy.deepcopy(c["doc"]), {"provided": key}
    return copy.deepcopy(c["doc"]), {"config_id": c["config"], "version": c["version"]}


def apply_action(f: dict, action: dict, choices: dict, library: dict, saved_sets: dict) -> str | None:
    """Apply one press on the stages board to the working copy f. Returns an error to show, or None."""
    op, stages = action.get("op"), f["stages"]
    i = action.get("stage")
    if op in ("set", "move", "remove", "tf", "label", "upgrade") and not (isinstance(i, int) and 0 <= i < len(stages)):
        return "That stage no longer exists."
    if op in ("set", "add"):
        got = _from_choice(str(action.get("set")), choices)
        if got is None:
            return "That Set is no longer available."
        if op == "set":
            stages[i]["set_body"], stages[i]["set_source"] = got
            return None
        if len(stages) >= MAX_STAGES:
            return f"A funnel has at most {MAX_STAGES} stages: select a stage to replace its Set instead."
        stages.append({"label": f"Stage {len(stages) + 1}", "timeframe": stages[-1]["timeframe"],
                       "set_body": got[0], "set_source": got[1]})
        return None
    if op == "move":
        j = i + (1 if action.get("dir") == 1 else -1)
        if 0 <= j < len(stages):
            stages[i], stages[j] = stages[j], stages[i]
        return None
    if op == "remove":
        if len(stages) <= MIN_STAGES:
            return f"A funnel needs at least {MIN_STAGES} stages."
        stages.pop(i)
        return None
    if op == "tf":
        if action.get("tf") not in fs.TIMEFRAMES:
            return "That timeframe isn't available."
        stages[i]["timeframe"] = action["tf"]
        return None
    if op == "label":
        stages[i]["label"] = str(action.get("label") or "").strip()[:40]
        return None
    if op == "upgrade":
        up = upgrade_for(stages[i], library, saved_sets)
        if up:
            stages[i]["set_body"], stages[i]["set_source"] = up[1], up[2]
        return None
    return None


def board_data(f: dict, choices: dict, library: dict, saved_sets: dict, show_provided: bool, scope: str) -> dict:
    import perspectives
    import prism_board as pb

    stages = []
    for i, stage in enumerate(f["stages"]):
        doc = stage.get("set_body") or {}
        up = upgrade_for(stage, library, saved_sets)
        stages.append({"label": stage.get("label") or "", "timeframe": stage["timeframe"],
                       "icon": fn.STAGE_ICONS[min(i, len(fn.STAGE_ICONS) - 1)],
                       "set_name": doc.get("name") or "This stage's Set", "set_line": str(doc.get("purpose") or ""),
                       "icons": perspectives.chips(doc), "upgrade": up[0] if up else None})
    return {"library": {"sets": [pb._set_entry(k, c) for k, c in choices.items()],
                        "perspectives": [{"key": k, "icon": i, "hover": h} for k, i, h in perspectives.ICONS]},
            "show_provided": show_provided, "stages": stages, "scope": scope,
            "timeframes": [[tf, TF_LABELS[tf]] for tf in fs.TIMEFRAMES],
            "min_stages": MIN_STAGES, "max_stages": MAX_STAGES,
            "intro": "Widest at the top: each stage checks only what passed the ones above it."}


def _stages_board(st, f: dict, pick: str, configs: list[dict], user_id: str, library: dict, saved_sets: dict) -> None:
    import json

    import funnel_stages_component
    import lattice_panel

    choices = board_choices(configs, user_id)
    data = board_data(f, choices, library, saved_sets, lattice_panel.provided_shown(st), str(pick))
    try:
        result = funnel_stages_component.component()(key=f"funnel_stages_{pick}", data=data,
                                                     on_action_change=lambda: None)
    except Exception as exc:
        st.info(f"The stages board could not load here ({str(exc)[:120]}).")
        return
    raw = getattr(result, "action", None)
    if not raw or raw == st.session_state.get("funnel_stages_seen"):
        return
    st.session_state["funnel_stages_seen"] = raw
    try:
        action = json.loads(raw)
    except ValueError:
        return
    if action.get("op") == "open_set":
        c = choices.get(action.get("set"))
        if c is not None:
            st.session_state["_lattice_section_next"] = "sets"
            st.session_state["_lattice_set_start_next"] = action["set"] if c.get("provided") else f"saved:{c['config']}"
            st.session_state.pop("lattice_set_loaded", None)
            st.session_state["lattice_flash_set"] = ("ok", (
                f"Opened a copy of “{c['name']}”: change it and save it as your own." if c.get("provided")
                else f"Opened “{c['name']}”."))
        lattice_panel.rerun(st)
        return
    problem = apply_action(f, action, choices, library, saved_sets)
    if problem:
        st.session_state["funnel_stages_flash"] = problem
    lattice_panel.rerun(st)


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
