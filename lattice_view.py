"""
🧩 Lattice · Group editor, admin preview (docs/design/lattice_prism.md §7, build stage 4).

Start from a new Group, a starter, or one of your saved Groups; drag signals in (or tap +); choose roles and
timeframes; write ordered label rules. Checks, the auto-written description and saving come from Python and the
engine's validator. Saving creates a version through the existing storage functions, so a saved Group can be
embedded in a Set and, with a decision, scanned in Prism.
"""

from __future__ import annotations

import json
import time

import lattice_component
import lattice_panel
import lattice_editor as le
import signal_groups as sg
import signal_library as sl
from signal_library import loaders

START_NEW = "new"


def _sources(saved: list[dict], user_id: str, show_provided: bool = True) -> tuple[dict, dict]:
    labels = {START_NEW: "➕ New Group"}
    docs: dict = {}
    for alias in sg.STARTERS if show_provided else ():
        doc = sg.starter(alias)
        labels[f"starter:{alias}"] = f"{lattice_panel.PROVIDED} {doc['name']} (copy of a starter)"
        docs[f"starter:{alias}"] = (doc, None)
    for c in saved:
        if c.get("kind") != "group" or c.get("owner_id") != user_id or not c["versions"]:
            continue
        v = c["versions"][-1]
        labels[f"saved:{c['id']}"] = f"📁 {c['name']} (yours, v{v['version']})"
        docs[f"saved:{c['id']}"] = (v["body"], c)
    return labels, docs


def render(st, supabase, assets: list[tuple[str, str, str]], user_id: str = "") -> None:
    st.caption("Drag signals in, or tap + on a tablet. Rules give the Group labels such as Bullish; the checks "
               "below say what blocks saving and what is only a warning.")
    import signal_groups_inspector as gi

    cached = st.session_state.get("siggroups_saved")
    if not cached or time.time() - cached[0] > 60:
        cached = (time.time(), *gi.saved_configs(supabase))
        st.session_state["siggroups_saved"] = cached
    _, saved, problem = cached
    shown = lattice_panel.provided_shown(st)
    labels, docs = _sources(saved, user_id, shown)
    if st.session_state.get("lattice_start") not in labels:
        st.session_state.pop("lattice_start", None)         # a starter that is now hidden
    lattice_panel.provided_switch(st, 0 if shown else len(sg.STARTERS), "provided_groups")
    start = st.selectbox("Start from", list(labels), format_func=labels.get, key="lattice_start")
    if st.session_state.get("lattice_loaded") != start:
        st.session_state["lattice_loaded"] = start
        if start == START_NEW:
            st.session_state["lattice_model"], st.session_state["lattice_source"] = le.empty_model(), None
        else:
            doc, cfg = docs[start]
            model, why = le.from_document(doc)
            if model is None:
                st.session_state["lattice_model"], st.session_state["lattice_source"] = le.empty_model(), None
                st.warning(f"{why} Starting a new Group instead; the raw inspector (Groups & Sets tab) can still open it.")
            else:
                if cfg is None:
                    model["name"] = f"{model['name']} (my copy)"
                st.session_state["lattice_model"], st.session_state["lattice_source"] = model, cfg
    model = st.session_state.get("lattice_model") or le.empty_model()

    early = lattice_panel.pending(st, "lattice_group_editor", "model")
    if early and early != st.session_state.get("lattice_seen"):
        st.session_state["lattice_seen"] = early                 # picked up now: no second redraw below
        try:
            st.session_state["lattice_model"] = le.clean_model(json.loads(early))
        except ValueError:
            pass
        model = st.session_state["lattice_model"]
    screen = le.state_for_screen(model)
    try:
        result = lattice_component.component()(
            key="lattice_group_editor",
            data={**screen, "catalogue": le.catalogue(), "role_hints": le.ROLE_HINT,
                  "suggested_labels": le.SUGGESTED_LABELS},
            on_model_change=lambda: None,
        )
    except Exception as exc:          # the page still works; only the editor is missing
        st.info(f"The editor could not load here ({str(exc)[:120]}).")
        result = None
    raw = getattr(result, "model", None)
    if raw and raw != st.session_state.get("lattice_seen"):
        st.session_state["lattice_seen"] = raw
        try:
            st.session_state["lattice_model"] = le.clean_model(json.loads(raw))
        except ValueError:
            pass
        lattice_panel.rerun(st)

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Checks**")
        for b in screen["checks"]["blocks"]:
            st.error(f"⛔ Can't save: {b}")
        for w in screen["checks"]["warnings"]:
            st.warning(f"⚠️ {w}")
        if not screen["checks"]["blocks"] and not screen["checks"]["warnings"]:
            st.success("✅ No problems found.")
    with right:
        st.markdown("**What this Group returns**")
        st.markdown(
            ("- **Score**: an average from −100 to +100 (a number).\n" if screen["returns"]["score"] else
             "- **Score**: none (no Score members).\n")
            + "- **Label**: " + (", ".join(screen["returns"]["labels"][:-1]) + " or " if len(screen["returns"]["labels"]) > 1
                                 else "") + f"{screen['returns']['labels'][-1]}, or Unknown if a rule can't be checked.\n"
            + "- **Completeness**: Complete, Partial or Limited, listing anything missing.")
        st.markdown("**Description** · written automatically")
        st.caption(screen["description"])

    _save(st, supabase, model, screen["can_save"])
    _try(st, supabase, model, assets, screen["can_save"])
    if problem:
        st.caption(f"Saved Groups could not be read: {problem}")


def _save(st, supabase, model: dict, can_save: bool) -> None:
    import signal_groups_inspector as gi

    doc = le.to_document(model)
    source = st.session_state.get("lattice_source")
    cols = st.columns(2)
    if cols[0].button("💾 Save as a new Group", disabled=not can_save, key="lattice_save_new", type="primary",
                      help="Saves version 1 of a new Group. It is private until you publish it."):
        try:
            new_id = supabase.rpc("analysis_create_config", {"kind": "group", "body": doc}).execute().data
            st.success("Saved as a new Group (version 1). It is private until you publish it.")
            st.session_state.pop("siggroups_saved", None)
            st.session_state["lattice_saved_id"] = new_id
        except Exception as exc:
            st.error(f"Refused: {gi._rpc_error(exc)}")
    if source:
        if cols[1].button(f"💾 Save as version {source['current_version'] + 1} of {source['name']}", disabled=not can_save,
                          key="lattice_save_next", help="Saves a new version. Earlier versions stay as they were."):
            try:
                v = supabase.rpc("analysis_save_version", {"cfg": source["id"], "expected_version": source["current_version"],
                                                           "body": doc}).execute().data
                st.success(f"Saved version {v}.")
                st.session_state.pop("siggroups_saved", None)
            except Exception as exc:
                st.error(f"Refused: {gi._rpc_error(exc)}")


def _try(st, supabase, model: dict, assets, can_save: bool) -> None:
    if not assets or not can_save:
        return
    with st.expander("▶️ Try it on one asset (live)"):
        names = {f"{k}:{i}": n for k, i, n in assets}
        pick = st.selectbox("Asset", list(names), format_func=names.get, key="lattice_try_asset")
        if st.button("Try it", key="lattice_try"):
            kind, aid = pick.split(":", 1)
            ctx = sl.DataContext(kind, aid, sentiment_loader=loaders.sentiment_loader(supabase))
            result = sg.evaluate_group(le.to_document(model), ctx)
            score = (result.get("score") or {}).get("value")
            outcome = (result.get("outcome") or {})
            st.markdown(f"**{names[pick]}**: score "
                        + ("—" if score is None else f"{score * 100:+.0f}")
                        + (f" · label **{outcome.get('label')}**" + (" (qualified)" if outcome.get("qualified") else "")
                           if outcome else "")
                        + f" · status {result.get('status')}")
