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


def _sources(saved: list[dict], user_id: str, current: str | None = None, provided: bool = True) -> tuple[dict, dict]:
    """"Start from": a new Group, then the provided starters (opened as your copy), then your own Groups."""
    import perspectives

    labels = {START_NEW: "➕ New Group"}
    docs: dict = {}
    for alias in sg.STARTERS:
        doc = sg.starter(alias)
        docs[f"starter:{alias}"] = (doc, None)
        if provided or current == f"starter:{alias}":     # asked for by name (Open in Lattice): shown even if hidden
            labels[f"starter:{alias}"] = f"{doc['name']} {perspectives.icons(doc)} (provided)"
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
    st.session_state["_lattice_user"] = user_id
    undo_bar(st, supabase, "group")
    if "_lattice_start_next" in st.session_state:          # a starter picked under "Copy a provided starter"
        st.session_state["lattice_start"] = st.session_state.pop("_lattice_start_next")
    labels, docs = _sources(saved, user_id, st.session_state.get("lattice_start"), lattice_panel.provided_shown(st))
    if st.session_state.get("lattice_start") not in labels:
        st.session_state.pop("lattice_start", None)
    if lattice_panel.provided_shown(st):
        _provided_starters(st)
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


def starters_html() -> str:
    """Each starter Group: name, what it looks at, evidence status, one line and "more…" (perspectives.py)."""
    import html

    import perspectives

    esc = lambda t: html.escape(str(t), quote=True)
    rows = []
    for alias in sg.STARTERS:
        doc, more = sg.starter(alias), perspectives.explain(alias)
        icons = "".join(f"<span title='{esc(c['hover'])}' aria-label='{esc(c['hover'])}' style='cursor:help'>{c['icon']}"
                        "</span>" for c in perspectives.chips(doc))
        ev_icon, ev_words = perspectives.EVIDENCE["untested"]
        body = ""
        if more:
            body = (f"<div style='font-size:13px;opacity:.85'>{esc(more['line'])}</div>"
                    "<details class='more' style='font-size:13px'><summary style='cursor:pointer;opacity:.75;"
                    "list-style:none'><span class='m'>more…</span><span class='l'>less…</span></summary>"
                    f"<p style='margin:4px 0'><b>What it measures:</b> {esc(more['measures'])}</p>"
                    f"<p style='margin:4px 0'><b>Why traders watch it:</b> {esc(more['why'])}</p>"
                    f"<p style='margin:4px 0'><b>What it doesn't prove:</b> {esc(more['not_proven'])}</p></details>")
        rows.append(f"<div style='padding:6px 0;border-bottom:1px solid rgba(127,127,127,.2)'>"
                    f"<div><b>{esc(doc['name'])}</b> <span style='margin-left:4px'>{icons}</span>"
                    f"<span title='{esc(ev_words)}' aria-label='{esc(ev_words)}' style='margin-left:6px;opacity:.75;"
                    f"cursor:help'>{ev_icon}</span></div>{body}</div>")
    style = ("<style>details.more[open] .m,details.more:not([open]) .l{display:none}"
             "details.more summary::-webkit-details-marker{display:none}</style>")
    return style + "<div>" + "".join(rows) + "</div>"


def _provided_starters(st) -> None:
    """The starter Groups, in their own folded section: copy one to start from it."""
    with st.expander(lattice_panel.PROVIDED_TITLE + " · starter Groups", icon=":material/inventory_2:"):
        st.caption("The dashboard's own readings, as Groups. Pick one in **Start from** below to open your own copy; "
                   "the original stays as it is. Hide these in ⚙️ Settings → Show provided starters and examples.")
        st.html(starters_html())


def _delete(st, supabase, kind: str, source: dict) -> None:
    """🗑 Delete your own Group or Set: refused while something is built on it; a table column showing it is
    removed; Undo brings it back (lattice_delete.py)."""
    import lattice_delete as ld
    import signal_groups_inspector as gi

    saved = (st.session_state.get("siggroups_saved") or (0, []))[1]
    user_id = st.session_state.get("_lattice_user")
    if kind == "group":
        users = ld.sets_using(source["id"], saved, user_id)
    else:
        try:
            scans = (supabase.table("prism_scans").select("name, set_source").execute().data or [])
        except Exception:
            scans = []
        users = ld.scans_using(source["id"], scans)
    word = "Group" if kind == "group" else "Set"
    with _popover(st, f"Delete this {word}", icon=":material/delete:",
                  help=f"Remove {source['name']} from your {word}s. You can undo it straight after."):
        if users:
            st.warning(ld.blocked_message(kind, users))
            return
        st.markdown(f"Delete **{source['name']}**? It disappears from your lists; if it is a column in your tables, "
                    "that column is removed too. You can undo this straight after.")
        if st.button(f"Delete {source['name']}", type="primary", key=f"lattice_delete_{kind}_{source['id']}"):
            try:
                supabase.rpc("analysis_archive_config", {"cfg": source["id"]}).execute()
            except Exception as exc:
                st.error(f"Refused: {gi._rpc_error(exc)}")
                return
            st.session_state["_drop_column"] = f"saved:{source['id']}"
            st.session_state["_lattice_undo"] = {"id": source["id"], "name": source["name"], "kind": kind}
            st.session_state.pop("siggroups_saved", None)
            st.session_state.pop("lattice_start" if kind == "group" else "lattice_set_start", None)
            st.session_state.pop("lattice_loaded" if kind == "group" else "lattice_set_loaded", None)
            lattice_panel.rerun_page(st)


def _popover(st, label: str, **kw):
    try:
        return st.popover(label, width="stretch", **kw)
    except TypeError:                      # an older Streamlit without width
        return st.popover(label, **kw)


def undo_bar(st, supabase, kind: str) -> None:
    """Straight after a delete: Undo brings the Group or Set back."""
    import signal_groups_inspector as gi

    undo = st.session_state.get("_lattice_undo")
    if not undo or undo["kind"] != kind:
        return
    cols = st.columns([4, 1], vertical_alignment="center")
    cols[0].info(f"Deleted **{undo['name']}**.", icon=":material/delete:")
    if cols[1].button("Undo", icon=":material/undo:", key=f"lattice_undo_{kind}", width="stretch"):
        try:
            supabase.rpc("analysis_restore_config", {"cfg": undo["id"]}).execute()
        except Exception as exc:
            st.error(f"Could not undo: {gi._rpc_error(exc)}. If it says the function is missing, run "
                     "sql/2026-11-13_restore_config.sql once.")
            return
        st.session_state.pop("_lattice_undo", None)
        st.session_state.pop("siggroups_saved", None)
        lattice_panel.rerun(st)


def action_row(st, n: int):
    """One row for the save and delete buttons: side by side on a wide screen, one under another on a phone
    (Streamlit stacks columns on narrow screens)."""
    return st.columns(n, vertical_alignment="center")


def _save(st, supabase, model: dict, can_save: bool) -> None:
    import signal_groups_inspector as gi

    doc = le.to_document(model)
    source = st.session_state.get("lattice_source")
    mine = bool(source and source.get("owner_id") == st.session_state.get("_lattice_user"))
    cols = action_row(st, 1 + bool(source) + mine)
    new = cols[0].button("💾 Save as a new Group", disabled=not can_save, key="lattice_save_new", type="primary",
                         width="stretch", help="Saves version 1 of a new Group. It is private until you publish it.")
    nxt = bool(source) and cols[1].button(f"💾 Save as version {source['current_version'] + 1} of {source['name']}",
                                          disabled=not can_save, key="lattice_save_next", width="stretch",
                                          help="Saves a new version. Earlier versions stay as they were.")
    if mine:
        with cols[-1]:
            _delete(st, supabase, "group", source)
    if new:
        try:
            new_id = supabase.rpc("analysis_create_config", {"kind": "group", "body": doc}).execute().data
            st.success("Saved as a new Group (version 1). It is private until you publish it.")
            st.session_state.pop("siggroups_saved", None)
            st.session_state["lattice_saved_id"] = new_id
        except Exception as exc:
            st.error(f"Refused: {gi._rpc_error(exc)}")
    if nxt:
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
