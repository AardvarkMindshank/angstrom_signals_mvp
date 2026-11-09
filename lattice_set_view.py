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


def fixed_asset_matches(raw: str, search_crypto=None, search_stock=None) -> dict | None:
    """A fixed-asset search from the Set editor ({slot, kind, q, nonce}) answered with market matches, as the
    Watchlist editor finds them: coins from CoinGecko (fixed by their CoinGecko id), equities from Yahoo (by ticker)."""
    import data_fetchers

    try:
        ask = json.loads(raw)
    except (TypeError, ValueError):
        return None
    kind, q = ask.get("kind"), str(ask.get("q") or "").strip()[:60]
    if kind not in ("crypto", "equity") or not q:
        return None
    try:
        if kind == "crypto":
            found = (search_crypto or data_fetchers.search_crypto_matches)(q)
            results = [{"id": m["id"], "label": f"{m.get('name') or m['id']} ({m.get('symbol') or ''})".replace(" ()", "")}
                       for m in found if m.get("id")]
        else:
            found = (search_stock or data_fetchers.search_stock_matches)(q)
            results = [{"id": m["symbol"], "label": " · ".join(x for x in (m["symbol"], m.get("name"), m.get("exchange"))
                                                               if x)} for m in found if m.get("symbol")]
    except Exception:
        results = []
    return {"slot": ask.get("slot"), "kind": kind, "q": q, "nonce": ask.get("nonce"), "results": results[:8]}


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
    asked = st.session_state.get("_lattice_set_start_next")
    provided = _provided_starts(choices) if lattice_panel.provided_shown(st) or str(asked).startswith("demo:") else {}
    starts.update({k: label for k, (label, _) in provided.items()})
    starts.update({f"saved:{c['id']}": f"🗂️ {c['name']} (yours, v{c['versions'][-1]['version']})" for c in mine})
    if "_lattice_set_start_next" in st.session_state:      # the Set just saved
        st.session_state["lattice_set_start"] = st.session_state.pop("_lattice_set_start_next")
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
                model["name"] = cfg["name"]               # its current name (it may have been renamed since saving)
                st.session_state["lattice_set_model"], st.session_state["lattice_set_source"] = model, cfg
    model = ls.clean_model(st.session_state.get("lattice_set_model") or ls.empty_model(), choices)
    lattice_view.show_flash(st, "lattice_flash_set")            # "Saved …", "Opened a copy of …"

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
    screen["search"] = st.session_state.get("lattice_set_search")      # market matches for a fixed asset
    try:
        result = lattice_component.set_component()(
            key="lattice_set_editor", data={**screen, "catalogue": le.catalogue()}, on_model_change=lambda: None,
            on_search_change=lambda: None)
    except Exception as exc:
        st.info(f"The editor could not load here ({str(exc)[:120]}).")
        result = None
    asked = getattr(result, "search", None)
    if asked and asked != st.session_state.get("lattice_set_search_seen"):
        st.session_state["lattice_set_search_seen"] = asked
        st.session_state["lattice_set_search"] = fixed_asset_matches(asked)
        lattice_panel.rerun(st)
    raw = getattr(result, "model", None)
    if raw and raw != st.session_state.get("lattice_set_seen"):
        st.session_state["lattice_set_seen"] = raw
        try:
            st.session_state["lattice_set_model"] = ls.clean_model(json.loads(raw), choices)
        except ValueError:
            pass
        lattice_panel.rerun(st)

    # Lined up with the editor's divider above: Checks under the left panel, what it returns under the right one
    # (the widths follow the divider as it is dragged; lattice_component.SPLITTER_JS).
    left, right = st.container(key="lat_checks_set").columns([3, 2])
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
    mine = bool(source and source.get("owner_id") == user_id)
    cols = lattice_view.action_row(st, 1 + bool(source) + 2 * mine)
    new = cols[0].button("💾 Save as a new Set", disabled=not screen["can_save"], key="lattice_set_save_new",
                         type="primary", width="stretch", help="Saves version 1. It is private until you publish it.")
    nxt = bool(source) and cols[1].button(f"💾 Save as version {source['current_version'] + 1} of {source['name']}",
                                          disabled=not screen["can_save"], key="lattice_set_save_next",
                                          width="stretch")
    if mine:
        with cols[-2]:
            lattice_view._rename(st, supabase, "set", source)
        with cols[-1]:
            lattice_view._delete(st, supabase, "set", source)
    if new and lattice_view.name_taken(saved, user_id, "set", doc.get("name")):
        st.warning(lattice_view.taken_message("Set", doc.get("name") or "", source))
        new = False
    if new:
        try:
            new_id = supabase.rpc("analysis_create_config", {"kind": "set", "body": doc}).execute().data
            st.session_state.pop("siggroups_saved", None)
            # Open the Set just saved, so the next save offers "Save as version 2" instead of another new Set.
            st.session_state["_lattice_set_start_next"] = f"saved:{new_id}"
            st.session_state.pop("lattice_set_loaded", None)
            st.session_state["lattice_flash_set"] = ("ok", "Saved as a new Set (version 1)."
                                                     + (" It now appears in 🔎 Prism." if screen["scannable"] else ""))
            lattice_panel.rerun(st)
        except Exception as exc:
            if "Rerun" in type(exc).__name__:
                raise
            st.error(f"Refused: {gi._rpc_error(exc)}")
    if nxt:
        try:
            v = supabase.rpc("analysis_save_version", {"cfg": source["id"], "expected_version": source["current_version"],
                                                       "body": doc}).execute().data
            st.session_state.pop("siggroups_saved", None)
            # Open the saved version, so everything below (such as Study this Set) is about version {v}.
            st.session_state["_lattice_set_start_next"] = f"saved:{source['id']}"
            st.session_state.pop("lattice_set_loaded", None)
            st.session_state["lattice_flash_set"] = ("ok", f"Saved version {v}.")
            lattice_panel.rerun(st)
        except Exception as exc:
            if "Rerun" in type(exc).__name__:
                raise
            st.error(f"Refused: {gi._rpc_error(exc)}")
    if source and source.get("owner_id") == user_id and source.get("versions"):
        study_block(st, supabase, source)
    if problem:
        st.caption(f"Saved Groups and Sets could not be read: {problem}")


STUDY_WAIT = "Studies run in the background, usually within an hour; you can leave this page."


def study_block(st, supabase, source: dict) -> None:
    """🔬 "What followed" for your saved Set: the study if there is one, its progress, or a button to start it.
    It studies the saved version (what the Set checks, not its name)."""
    import perspectives
    import what_followed as wf

    version = source["versions"][-1]
    doc = version["body"]
    st.markdown("**What followed** · what happened after this Set turned Yes in the past")
    card = perspectives.followed_card(doc)
    if card:
        icon, _ = perspectives.evidence(doc)
        with st.expander(f"{icon} What followed: {card['verdict'] or 'not studied on its own'}"):
            st.caption(card["title"].replace("What followed · ", ""))
            for line in card["lines"]:
                st.markdown(f"- {line}")
            st.caption(card["note"])
        return
    ok, why = wf.studyable(doc)
    if not ok:
        st.caption(f"🔬 Can't be studied: {why}")
        return
    h = wf.logic_hash(doc)
    try:
        row = (supabase.table("set_studies").select("status, error, requested_at").eq("set_hash", h)
               .limit(1).execute().data or [None])[0]
    except Exception:
        row = None
    status = (row or {}).get("status")
    if status in ("queued", "running"):
        word = "is being worked out" if status == "running" else "is waiting its turn"
        st.info(f"⏳ The study of version {version['version']} {word}. {STUDY_WAIT}")
        return
    if status == "done":                         # finished since this page last looked
        perspectives.load_studies(supabase, force=True)
        st.caption("✅ The study is ready: reopen this Set to see it.")
        return
    if status in ("refused", "failed") and row.get("error"):
        st.caption(f"Last try: {row['error']}")
    if status == "refused":
        return
    if st.button(f"🔬 Study this Set (version {version['version']})", key=f"lattice_study_{h}",
                 help="Checks what happened after this Set turned Yes on 25 major coins and 61 large US shares, "
                      "Sep 2014 to Oct 2024, against comparable days. " + STUDY_WAIT):
        try:
            got = supabase.rpc("request_set_study", {"set_hash": h, "body": doc,
                                                     "name": source.get("name") or ""}).execute().data
            st.success("⏳ Queued. " + STUDY_WAIT if got in ("queued", "running") else f"Status: {got}.")
        except Exception as exc:
            import signal_groups_inspector as gi

            msg = gi._rpc_error(exc)
            st.error("You already have 5 studies waiting; try again when one finishes." if "too_many_waiting" in msg
                     else f"Could not queue the study: {msg}")
