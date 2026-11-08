"""
🗂️ Lattice · Set editor, admin preview (docs/design/lattice_prism.md §4.2, §7; build stage 4, part 2).

Drag saved Groups and single signals into a Set and write its decision: an ALL box of lines, with optional ANY boxes.
Checks, the description and saving come from Python and the engine's validator. A saved Set with a decision appears
in 🔎 Prism straight away, for Run now and Scheduled scans.
"""

from __future__ import annotations

import copy
import json
import time

import lattice_component
import lattice_panel
import lattice_editor as le
import lattice_sets as ls

START_NEW = "new"


def _provided_starts(choices: list) -> dict:
    """Provided Sets the editor can open as your copy: key -> (label, model). One whose parts the editor can't
    rebuild (for example a Group made only for that Set) is left out."""
    import perspectives
    import table_columns

    out = {}
    for key, doc in table_columns.provided_sets().items():
        try:
            model, _why = ls.from_document(copy.deepcopy(doc), choices)
        except Exception:
            model = None
        if model is not None:
            out[key] = (f"{doc['name']} {perspectives.icons(doc)} (provided)", model)
    return out


def render(st, supabase, user_id: str = "") -> None:
    st.caption("Combine saved Groups and single signals, then say when the Set answers Yes. A Group goes in exactly "
               "as saved; save a Group with labels in Signal Groups "
               "first to test its label here.")
    import signal_groups_inspector as gi

    cached = st.session_state.get("siggroups_saved")
    if not cached or time.time() - cached[0] > 60:
        cached = (time.time(), *gi.saved_configs(supabase))
        st.session_state["siggroups_saved"] = cached
    _, saved, problem = cached
    import lattice_view

    st.session_state["_lattice_user"] = user_id
    lattice_view.undo_bar(st, supabase, "set")
    choices = ls.group_choices(saved, user_id)
    mine = [c for c in saved if c.get("kind") == "set" and c.get("owner_id") == user_id and c["versions"]]
    starts = {START_NEW: "➕ New Set"}
    # Provided Sets are run in Prism; most can't open here yet (they use labelled copies of the starter Groups that
    # the editor can't match), so only those that rebuild cleanly are offered.
    provided = _provided_starts(choices) if lattice_panel.provided_shown(st) else {}
    starts.update({k: label for k, (label, _) in provided.items()})
    starts.update({f"saved:{c['id']}": f"🗂️ {c['name']} (yours, v{c['versions'][-1]['version']})" for c in mine})
    if st.session_state.get("lattice_set_start") not in starts:
        st.session_state.pop("lattice_set_start", None)
    start = st.selectbox("Start from", list(starts), format_func=starts.get, key="lattice_set_start")
    if st.session_state.get("lattice_set_loaded") != start:
        st.session_state["lattice_set_loaded"] = start
        st.session_state["lattice_set_model"], st.session_state["lattice_set_source"] = ls.empty_model(), None
        if start in provided:                             # a provided Set opens as your own copy
            model = provided[start][1]
            model["name"] = f"{model.get('name') or 'Set'} (my copy)"
            st.session_state["lattice_set_model"] = model
        elif start != START_NEW:
            cfg = next(c for c in mine if f"saved:{c['id']}" == start)
            model, why = ls.from_document(cfg["versions"][-1]["body"], choices)
            if model is None:
                st.warning(f"{why} Starting a new Set instead.")
            else:
                st.session_state["lattice_set_model"], st.session_state["lattice_set_source"] = model, cfg
    model = ls.clean_model(st.session_state.get("lattice_set_model") or ls.empty_model(), choices)

    early = lattice_panel.pending(st, "lattice_set_editor", "model")
    if early and early != st.session_state.get("lattice_set_seen"):
        st.session_state["lattice_set_seen"] = early                 # picked up now: no second redraw below
        try:
            st.session_state["lattice_set_model"] = ls.clean_model(json.loads(early), choices)
        except ValueError:
            pass
        model = st.session_state["lattice_set_model"]
    screen = ls.state_for_screen(model, choices)
    screen["show_provided"] = lattice_panel.provided_shown(st)   # the library's "Provided" section
    try:
        result = lattice_component.set_component()(
            key="lattice_set_editor", data={**screen, "catalogue": le.catalogue()}, on_model_change=lambda: None)
    except Exception as exc:
        st.info(f"The editor could not load here ({str(exc)[:120]}).")
        result = None
    raw = getattr(result, "model", None)
    if raw and raw != st.session_state.get("lattice_set_seen"):
        st.session_state["lattice_set_seen"] = raw
        try:
            st.session_state["lattice_set_model"] = ls.clean_model(json.loads(raw), choices)
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
        st.markdown("**What this Set returns**")
        st.markdown("- **Answer**: Yes, No, or Unknown when a needed reading is missing.\n"
                    "- **Lines**: each line's reading, and the deciding reason.\n"
                    "- **Data available**: Complete or Partial, separate from how sure the answer is.\n"
                    "- No combined Set score.")
        st.markdown("**Description** · written automatically")
        st.caption(screen["description"])

    doc = ls.to_document(model, choices)
    source = st.session_state.get("lattice_set_source")
    cols = st.columns(2)
    if cols[0].button("💾 Save as a new Set", disabled=not screen["can_save"], key="lattice_set_save_new", type="primary",
                      help="Saves version 1. It is private until you publish it."):
        try:
            supabase.rpc("analysis_create_config", {"kind": "set", "body": doc}).execute()
            st.success("Saved as a new Set (version 1)."
                       + (" It now appears in 🔎 Prism." if screen["scannable"] else ""))
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {gi._rpc_error(exc)}")
    if source and source.get("owner_id") == user_id:
        lattice_view._delete(st, supabase, "set", source)
    if source and cols[1].button(f"💾 Save as version {source['current_version'] + 1} of {source['name']}",
                                 disabled=not screen["can_save"], key="lattice_set_save_next"):
        try:
            v = supabase.rpc("analysis_save_version", {"cfg": source["id"], "expected_version": source["current_version"],
                                                       "body": doc}).execute().data
            st.success(f"Saved version {v}.")
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {gi._rpc_error(exc)}")
    if problem:
        st.caption(f"Saved Groups and Sets could not be read: {problem}")
