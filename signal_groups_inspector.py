"""
Admin-only development view for Signal Groups and Sets (inside the 🧪 Signal Library panel).

- Evaluate: a starter Group, the example Set, or any saved Group/Set version you can read, on any watchlist asset,
  with live data. Runs only when the button is pressed.
- Storage testing: save, version, copy, publish and archive through the database functions, with the documents as
  JSON. This is admin test tooling, not the user-facing editor (its workflow is still to be agreed).

Nothing here changes Trend, Stretch, Flow, alerts or any user setting.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import time

import pandas as pd

import signal_groups as sg
import signal_library as sl
from signal_library import loaders

STATUS_ICON = {"ok": "✅", "vetoed": "⛔", "veto_unknown": "❔", "insufficient": "⏳", "invalid": "⚠️",
               "unsupported": "➖"}
STATE_ICON = {"met": "✅", "not_met": "▫️", "unknown": "❔", "active": "⛔", "clear": "▫️"}
SETUP_HINT = ("The Groups & Sets tables are not installed. Run sql/2026-11-04_signal_groups.sql and then "
              "sql/2026-11-04_signal_groups_starters.sql in the Supabase SQL editor.")


def example_set() -> dict:
    """The design's example Set, rebuilt from the code starters (so it always embeds the current starters)."""
    doc = json.loads((sg.STARTERS_DIR.parent.parent / "docs" / "design" / "examples" / "set_multi_timeframe.json")
                     .read_text(encoding="utf-8"))
    for g in doc["groups"]:
        body = sg.starter(g["provenance"]["source_config"])
        g["snapshot"] = body
        g["provenance"]["content_sha256"] = sg.content_sha256(body)
    return doc


def saved_configs(supabase) -> tuple[list[dict], str | None]:
    """Configs and readable versions (row-level security decides what comes back)."""
    try:
        configs = (supabase.table("analysis_configs")
                   .select("id, kind, name, owner_id, starter_alias, current_version, archived, copied_from_config")
                   .order("updated_at", desc=True).limit(100).execute().data or [])
        versions = (supabase.table("analysis_config_versions")
                    .select("config_id, version, body, capture_ceiling, created_at, change_note")
                    .order("created_at", desc=True).limit(300).execute().data or [])
    except Exception as exc:
        return [], f"{SETUP_HINT} ({str(exc)[:120]})"
    by_cfg: dict = {}
    for v in versions:
        by_cfg.setdefault(v["config_id"], []).append(v)
    for c in configs:
        c["versions"] = sorted(by_cfg.get(c["id"], []), key=lambda v: v["version"])
    return [c for c in configs if c["versions"]], None


def _rpc_error(exc) -> str:
    text = str(getattr(exc, "message", "") or exc)
    for code in ("beyond_capture_ceiling", "beyond_source_audience", "not_authorised_to_capture", "not_authorised_to_copy",
                 "snapshot_mismatch", "unknown_source", "conflict", "not_owner", "not_in_community", "archived",
                 "too_large", "wrong_schema", "missing_lineage_version", "no_communities"):
        if code in text:
            return code
    return text[:200]


# ---------------------------------------------------------------------------------------------- rendering results

def _group_card(st, result: dict, title: str) -> None:
    status = result.get("status")
    score = result.get("score") or {}
    head = f"{STATUS_ICON.get(status, '')} **{title}** · status `{status}`"
    if result.get("score") is not None:
        v = score.get("value")
        head += (f" · score **{v * 100:+.0f}**" if v is not None else f" · score withheld (`{score.get('withheld')}`)")
        head += f" · observed coverage {score.get('observed_coverage', 0):.0%}"
    st.markdown(head)
    if result.get("errors"):
        for e in result["errors"]:
            st.caption(f"⚠️ {e}")
        return
    if result.get("reason"):
        st.caption(result["reason"])
        return
    if score.get("meaning"):
        st.caption(score["meaning"])
    st.dataframe([{"": STATE_ICON.get(c["state"], ""), "Condition": c.get("label") or c["key"], "Kind": c["kind"],
                   "State": c["state"], "Sources": ", ".join(c.get("sources") or [])} for c in result["conditions"]],
                 hide_index=True, width="stretch")
    rows = []
    for m in result["members"]:
        sig = m["signal"]
        value = sig.get("value")
        shown = value if isinstance(value, (str, int, float)) or value is None else json.dumps(value)[:90]
        rows.append({"Member": m.get("label") or m["key"], "Role": m["role"], "TF": sig["ref"].get("timeframe"),
                     "Signal status": sig["status"], "Value": shown, "State": m.get("state", ""),
                     "Contribution": m.get("contribution"), "Weight": m.get("weight"),
                     "Sources": ", ".join(m["lineage"]), "Available": (sig.get("available_at") or "")[:16].replace("T", " ")})
    st.dataframe(rows, hide_index=True, width="stretch")
    diag = result.get("diagnostics") or {}
    notes = []
    if diag.get("source_separation"):
        notes.append(diag["source_separation"]["note"])
    notes += diag.get("known_redundancy") or []
    if diag.get("duplicates"):
        notes.append(f"Same signal used twice: {diag['duplicates']}")
    if diag.get("category_conflicts"):
        notes.append(f"Members in these categories point opposite ways: {', '.join(diag['category_conflicts'])}")
    for n in notes:
        st.caption(f"ℹ️ {n}")


def _set_card(st, result: dict, title: str) -> None:
    st.markdown(f"{STATUS_ICON.get(result.get('status'), '')} **{title}** · Set · status `{result.get('status')}` · no Set score")
    if result.get("errors") or result.get("reason"):
        for e in result.get("errors") or [result.get("reason")]:
            st.caption(f"⚠️ {e}")
        return
    for g in result["groups"]:
        with st.container(border=True):
            prov = g.get("provenance") or {}
            _group_card(st, g["result"], f"{g['result'].get('name')} (from {prov.get('source_config')} v{prov.get('source_version')})")
    items = [{"Item": s.get("label") or s["key"], "Role": s["role"], "Status": s["signal"]["status"],
              "Value": json.dumps(s["signal"].get("value"))[:110]} for s in result["standalone"]]
    for mc in result["market_context"]:
        sig = mc.get("signal") or {}
        items.append({"Item": mc.get("label") or mc["key"], "Role": f"market ({mc['subject']})",
                      "Status": sig.get("status") or mc.get("skipped"), "Value": json.dumps(sig.get("value"))[:110]})
    if items:
        st.dataframe(items, hide_index=True, width="stretch")
    st.caption(f"ℹ️ {result['diagnostics']['note']}")
    shared = result["diagnostics"].get("shared_signals") or []
    if shared:
        st.caption(f"Signals used in more than one part: {len(shared)}")


# ---------------------------------------------------------------------------------------------- main

def render(st, supabase, assets, my_communities, user_id: str) -> None:
    st.caption(
        "Evaluate Signal Groups and Sets on live data. Admin only; nothing here changes readings, alerts or settings. "
        "Signals run only when you press Evaluate. Tick \"Reconstruct at a past time\" to see what a Group or Set "
        "said at one date and time (an as-of reconstruction: today's rules on data cut at that time)."
    )
    cached = st.session_state.get("siggroups_saved")
    if st.button("↻", key="siggroups_refresh", help="Reload saved Groups and Sets") or not cached \
            or time.time() - cached[0] > 60:
        cached = (time.time(), *saved_configs(supabase))  # at most once a minute per session, or on request
        st.session_state["siggroups_saved"] = cached
    _, saved, problem = cached
    choices = {f"starter-file:{a}": f"⭐ {sg.starter(a)['name']} (starter, from code)" for a in sg.STARTERS}
    choices["example-set"] = "⭐ Multi-Timeframe Analysis (example Set, from code)"
    docs = {f"starter-file:{a}": ("group", sg.starter(a)) for a in sg.STARTERS}
    docs["example-set"] = ("set", example_set())
    for c in saved:
        for v in c["versions"]:
            key = f"saved:{c['id']}:{v['version']}"
            owner = "mine" if c.get("owner_id") == user_id else ("starter" if c.get("starter_alias") else "shared")
            choices[key] = f"{'📁' if c['kind'] == 'group' else '🗂️'} {c['name']} v{v['version']} ({c['kind']}, {owner})"
            docs[key] = (c["kind"], v["body"])
    if problem:
        st.caption(problem)
    names = {f"{kind}:{key}": name for kind, key, name in assets}
    with st.form("siggroups_form", border=False):
        cols = st.columns([3, 3, 1])
        pick = cols[0].selectbox("Group or Set", list(choices), format_func=lambda k: choices[k], key="siggroups_pick")
        asset = cols[1].selectbox("Asset", list(names), format_func=lambda k: names[k], key="siggroups_asset")
        go = cols[2].form_submit_button("Evaluate", width="stretch")
        past = st.checkbox("Reconstruct at a past time (one date, UTC)", key="siggroups_past",
                           help="Evaluates the Group or Set as of one past moment, using only data available then. "
                                "One date per request; this is not a history view.")
        when = st.columns(2)
        day = when[0].date_input("Date (UTC)", key="siggroups_day", value=(pd.Timestamp.now(tz="UTC")
                                                                         - pd.Timedelta(days=30)).date())
        clock = when[1].time_input("Time (UTC)", key="siggroups_time", value=dt.time(0, 0))
    if go:
        kind, body = docs[pick]
        akind, aid = asset.split(":", 1)
        if past:
            st.session_state["siggroups_result"] = reconstruct(supabase, kind, body, akind, aid,
                                                               pd.Timestamp(dt.datetime.combine(day, clock), tz="UTC"),
                                                               choices[pick])
        else:
            ctx = sl.DataContext(akind, aid, derivatives_loader=loaders.derivatives_loader(supabase))
            if kind == "group":
                result = sg.evaluate_group(body, ctx)
            else:
                result = sg.evaluate_set(body, ctx, market_context=lambda scope: sl.DataContext(
                    "market", scope.split(":", 1)[1], flows_loader=loaders.flows_loader(supabase)))
            st.session_state["siggroups_result"] = (choices[pick], kind, result)
    stored = st.session_state.get("siggroups_result")
    if stored:
        title, kind, result = stored[:3]
        if result.get("data_mode") == "point_in_time" or len(stored) > 3:
            _reconstruction_card(st, stored)
        else:
            (_group_card if kind == "group" else _set_card)(st, result, title)
            st.download_button("Download result (JSON)", json.dumps(result, indent=1, default=str),
                               file_name="group_result.json", mime="application/json", key="siggroups_download")

    with st.expander("Storage testing (admin): save, version, copy, publish, archive"):
        _storage(st, supabase, saved, docs, choices, my_communities, user_id, problem)


# ---------------------------------------------------------------------------------------------- reconstruction

COMPLETENESS_ICON = {"complete": "🟢", "limited": "🟡", "partial": "🟠", "partial and limited": "🟠"}


def reconstruct(supabase, kind: str, body: dict, asset_kind: str, asset_id: str, as_of, title: str) -> tuple:
    """One as-of reconstruction (display mode: descriptive, not saved, not for statistics).
    Returns (title, kind, result or None, record or None, error or None)."""
    from signal_library.replay import ReplayRefused
    from signal_library.replay_display import display_run

    now = pd.Timestamp.now(tz="UTC")
    if as_of >= now:
        return title, kind, {"data_mode": "point_in_time"}, None, "Choose a time in the past."
    try:
        run = display_run(supabase, max_steps=1)
        ctx = run.context(asset_kind, asset_id, as_of)
        if kind == "group":
            result = sg.evaluate_group(body, ctx, data_mode="point_in_time", as_of=as_of)
        else:
            result = sg.evaluate_set(body, ctx, data_mode="point_in_time",
                                     market_context=lambda scope: run.context("market", scope.split(":", 1)[1], as_of))
        return title, kind, result, run.record(), None
    except ReplayRefused as exc:
        return title, kind, {"data_mode": "point_in_time"}, None, str(exc)


def _completeness_block(st, completeness: dict, kind: str) -> None:
    label = completeness.get("label", "?")
    st.markdown(f"{COMPLETENESS_ICON.get(label, '')} **Reconstruction: {label}**")
    if completeness.get("qualified"):
        st.warning("Read this result with its qualifications: it is not a complete reconstruction of this time.",
                   icon=":material/warning:")
    for note in completeness.get("notes") or []:
        st.caption(f"• {note}")
    if kind == "set":
        if completeness.get("groups"):
            st.caption("Groups: " + ", ".join(f"{k}: {v}" for k, v in completeness["groups"].items()))
        for item in completeness.get("missing_items") or []:
            st.caption(f"• {item['item']} ({item['section']}): {item['reason']}")
        for text in completeness.get("limitations") or []:
            st.caption(f"• {text}")
    missing = completeness.get("missing") or []
    if missing:
        st.dataframe([{"Member": m["member"], "Why": m["reason"], "Critical": "yes" if m["critical"] else "",
                       "Score coverage": "affected" if m["affects_score_coverage"] else "",
                       "Confirmations unknown": ", ".join(m["confirmations_unknown"]),
                       "Vetoes unknown": ", ".join(m["vetoes_unknown"])} for m in missing],
                     hide_index=True, width="stretch")


def _reconstruction_card(st, stored: tuple) -> None:
    title, kind, result, record, error = (list(stored) + [None, None])[:5]
    if error:
        st.warning(error, icon=":material/error:")
        return
    st.info(f"As-of reconstruction at **{result.get('as_of', '?').replace('T', ' ')[:16]} UTC**: today's rules on data "
            "cut at that time. Descriptive only: it is not saved and not used for statistics.",
            icon=":material/history:")
    if result.get("status") in ("unsupported", "invalid"):
        (_group_card if kind == "group" else _set_card)(st, result, title)
        return
    if kind == "group":
        _completeness_block(st, result.get("completeness") or {}, "group")
        _group_card(st, result, title)
    else:
        _completeness_block(st, result.get("completeness") or {}, "set")
        for g in result.get("groups") or []:
            c = g["result"].get("completeness") or {}
            st.caption(f"{COMPLETENESS_ICON.get(c.get('label'), '')} {g['key']}: {c.get('label')}")
        _set_card(st, result, title)
    if record:
        with st.expander("Reconstruction record (what produced this result)"):
            st.json({k: record[k] for k in ("mode", "kind", "cutoffs", "administrative", "code", "environment",
                                            "hold_out")}, expanded=False)
            st.dataframe([{"Input": i.get("timeframe") or f"{i.get('source')}/{i.get('series')}",
                           "Subject": i["subject"], "Rows": i.get("candles", i.get("rows")),
                           "Quality": (i.get("source") or {}).get("quality") if isinstance(i.get("source"), dict)
                           else i.get("quality"), "SHA-256": i["sha256"][:16]} for i in record.get("inputs") or []],
                         hide_index=True, width="stretch")
            st.dataframe([{"Signal": s["key"], "TF": s["timeframe"], "Certification": s["certification"]["algorithm"],
                           "Slice shortcut": "yes" if s["certification"].get("slice_equivalent") else "no"}
                          for s in record.get("signals") or []], hide_index=True, width="stretch")


def _storage(st, supabase, saved, docs, choices, my_communities, user_id, problem) -> None:
    if problem:
        st.caption(problem)
        return
    st.caption("Test tooling with raw JSON, not the planned editor. Every action goes through the database functions, "
               "which enforce ownership, strict capture ceilings and community membership; refusals show their reason.")
    start = st.selectbox("Start from", list(choices), format_func=lambda k: choices[k], key="siggroups_store_from")
    kind, body = docs[start]
    text = st.text_area("Document (JSON)", json.dumps(body, indent=1), height=220, key=f"siggroups_json_{start}")
    try:
        doc = json.loads(text)
    except ValueError as exc:
        st.caption(f"⚠️ Not valid JSON: {exc}")
        return
    kind = "set" if doc.get("schema") == sg.validate.SET_SCHEMA else "group"
    errors = sg.validate_set(doc) if kind == "set" else sg.validate_group(doc)
    for e in errors[:8]:
        st.caption(f"⚠️ {e}")
    mine = [c for c in saved if c.get("owner_id") == user_id]
    c1, c2 = st.columns(2)
    if c1.button(f"Save as a new {kind}", disabled=bool(errors), key="siggroups_create"):
        try:
            new_id = supabase.rpc("analysis_create_config", {"kind": kind, "body": doc}).execute().data
            st.success(f"Saved as version 1 ({new_id}). It is private until you publish it.")
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {_rpc_error(exc)}")
    target = c2.selectbox("…or as the next version of", [""] + [c["id"] for c in mine],
                          format_func=lambda i: "—" if not i else next(f"{c['name']} (now v{c['current_version']})"
                                                                       for c in mine if c["id"] == i),
                          key="siggroups_target")
    if target and c2.button("Save next version", disabled=bool(errors), key="siggroups_save"):
        current = next(c["current_version"] for c in mine if c["id"] == target)
        try:
            v = supabase.rpc("analysis_save_version", {"cfg": target, "expected_version": current, "body": doc}).execute().data
            st.success(f"Saved version {v}.")
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {_rpc_error(exc)}")

    st.markdown("**Build a Set from Groups** (embeds frozen snapshots; the server re-checks them)")
    group_versions = {k: v for k, v in choices.items() if docs[k][0] == "group" and k.startswith("saved:")}
    picked = st.multiselect("Groups to embed", list(group_versions), format_func=lambda k: group_versions[k],
                            key="siggroups_set_groups")
    if picked and st.button("Save as a new Set", key="siggroups_build_set"):
        groups = []
        for i, k in enumerate(picked):
            _, cfg, ver = k.split(":")
            src = next(c for c in saved if c["id"] == cfg)
            body = copy.deepcopy(docs[k][1])
            groups.append({"key": f"g{i + 1}", "snapshot": body,
                           "provenance": {"source_config": src.get("starter_alias") or cfg, "source_version": int(ver)}})
        set_doc = {"schema": sg.validate.SET_SCHEMA, "name": "Set built in the inspector", "lineage_version": 2,
                   "groups": groups, "standalone": [], "market_context": [], "score": None}
        problems = sg.validate_set(set_doc)
        if problems:
            st.error("; ".join(problems[:4]))
        else:
            try:
                new_id = supabase.rpc("analysis_create_config", {"kind": "set", "body": set_doc}).execute().data
                st.success(f"Saved Set {new_id} (version 1, private).")
                st.session_state.pop("siggroups_saved", None)
            except Exception as exc:
                st.error(f"Refused: {_rpc_error(exc)}")

    st.markdown("**Publish, copy or archive**")
    readable = [(c, v["version"]) for c in saved for v in c["versions"]]
    if not readable:
        return
    pick = st.selectbox("Version", range(len(readable)),
                        format_func=lambda i: f"{readable[i][0]['name']} v{readable[i][1]} "
                                              f"({'mine' if readable[i][0].get('owner_id') == user_id else 'not mine'})",
                        key="siggroups_pub_pick")
    cfg, ver = readable[pick]
    communities = my_communities() or []
    audience = st.radio("Audience", ["private", "communities", "public"], horizontal=True, key="siggroups_aud")
    chosen = st.multiselect("Communities", [c["id"] for c in communities],
                            format_func=lambda i: next(c["name"] for c in communities if c["id"] == i),
                            key="siggroups_aud_comm") if audience == "communities" else []
    b1, b2, b3 = st.columns(3)
    if b1.button("Publish", key="siggroups_publish"):
        try:
            supabase.rpc("analysis_publish_version", {"cfg": cfg["id"], "ver": ver, "audience": audience,
                                                      "communities": chosen}).execute()
            st.success(f"Published v{ver} to {audience}.")
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {_rpc_error(exc)}")
    if b2.button("Copy to my configs", key="siggroups_copy"):
        try:
            new_id = supabase.rpc("analysis_copy_config", {"src": cfg["id"], "src_version": ver}).execute().data
            st.success(f"Copied ({new_id}).")
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {_rpc_error(exc)}")
    if b3.button("Archive", key="siggroups_archive"):
        try:
            supabase.rpc("analysis_archive_config", {"cfg": cfg["id"]}).execute()
            st.success("Archived.")
            st.session_state.pop("siggroups_saved", None)
        except Exception as exc:
            st.error(f"Refused: {_rpc_error(exc)}")
