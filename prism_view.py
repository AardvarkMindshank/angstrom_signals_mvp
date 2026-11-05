"""
Prism · Run now, admin view (docs/design/lattice_prism.md §5.1, build stage 2).

A tab in the 🧩 Lattice · 🔎 Prism panel, for every signed-in account. Pick a Set that has a decision, pick assets
(default: the whole Watchlist), choose Now or a past moment, and press Run now. Runs nothing until the button is
pressed. Display only: results are not saved or exported, and past moments are reconstructions, not records.
"""

from __future__ import annotations

import datetime as dt
import time

import pandas as pd

import prism
import signal_groups as sg
import signal_library as sl
from signal_library import loaders

COOLDOWN_SECONDS = 20     # one Run now per account every 20 seconds: each run can read up to 40 assets
HELP = {
    "answer": "Yes: every necessary line holds. No: at least one necessary line fails (missing data could not change "
              "that). Unknown: nothing fails, but something needed could not be decided.",
    "how_sure": "Definite: the answer cannot change with the missing data. Undecided: it could.",
    "available": "How much of the input data existed. Separate from how sure the answer is.",
}


def scannable_sets(saved: list[dict], user_id: str) -> tuple[dict, dict]:
    """(labels, documents) for the demo Sets and every readable saved Set version that has a decision."""
    labels = {k: f"⭐ {d['name']}" for k, d in prism.demo_sets().items()}
    docs = dict(prism.demo_sets())
    for c in saved:
        if c.get("kind") != "set":
            continue
        for v in c["versions"]:
            if sg.scannable(v.get("body") or {}):
                key = f"saved:{c['id']}:{v['version']}"
                owner = "mine" if c.get("owner_id") == user_id else "shared"
                labels[key] = f"🗂️ {c['name']} v{v['version']} ({owner})"
                docs[key] = v["body"]
    return labels, docs


def render(st, supabase, assets: list[tuple[str, str, str]], user_id: str = "") -> None:
    st.caption("🔎 **Prism · Run now** (preview). Checks a Set on your Watchlist and answers Yes, No or Unknown "
               "for each asset, with the reason. Nothing is saved; past moments are reconstructions from today's data "
               "providers, not records.")
    if not assets:
        st.info("No assets in the watchlists.")
        return
    import signal_groups_inspector as gi

    cached = st.session_state.get("siggroups_saved")
    if not cached or time.time() - cached[0] > 60:
        cached = (time.time(), *gi.saved_configs(supabase))
        st.session_state["siggroups_saved"] = cached
    _, saved, problem = cached
    labels, docs = scannable_sets(saved, user_id)
    view = st.radio("Prism view", ["▶️ Run now", "⏰ Scheduled scans"], horizontal=True, key="prism_view",
                    label_visibility="collapsed")
    if view.endswith("Scheduled scans"):
        _scheduled(st, supabase, labels, docs, user_id)
        return
    names = {f"{kind}:{key}": name for kind, key, name in assets}

    with st.form("prism_form", border=False):
        top = st.columns([3, 1])
        pick = top[0].selectbox("Set", list(labels), format_func=lambda k: labels[k], key="prism_set",
                                help="Only Sets with a decision can be scanned. A Set without one is never treated as No.")
        go = top[1].form_submit_button("Run now", width="stretch", type="primary")
        chosen = st.multiselect("Assets", list(names), default=list(names)[:prism.MAX_ASSETS],
                                format_func=lambda k: names[k], key="prism_assets",
                                help=f"Your Watchlist, at most {prism.MAX_ASSETS} per run.")
        when = st.columns([2, 2, 2])
        mode = when[0].radio("When", ["Now", "A past moment"], horizontal=True, key="prism_when",
                             help="Now uses the latest finished candles. A past moment rebuilds what was known then, "
                                  "using only data available at that time.")
        day = when[1].date_input("Date (UTC)", key="prism_day",
                                 value=(pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)).date())
        clock = when[2].time_input("Time (UTC)", key="prism_time", value=dt.time(0, 5))

    doc = docs[pick]
    with st.expander("What this Set checks", expanded=False):
        st.markdown(f"**{doc['name']}**: {doc.get('purpose') or 'no description'}")
        st.markdown("\n".join(f"- {head}" for _, head in prism.columns(doc)))
        st.caption("All lines must hold (ALL). A failed line gives No even if other data is missing; Unknown is "
                   "never turned into Yes or No.")

    if go and time.time() - st.session_state.get("prism_last_run", 0.0) < COOLDOWN_SECONDS:
        st.info(f"Please wait a few seconds between runs (at most one every {COOLDOWN_SECONDS} seconds).")
        go = False
    if go:
        st.session_state["prism_last_run"] = time.time()
        picked = [(k.split(":", 1)[0], k.split(":", 1)[1], names[k]) for k in chosen]
        if not picked:
            st.warning("Choose at least one asset.")
            return
        bar = st.progress(0.0, text="Checking…")
        progress = lambda n, total: bar.progress(n / total, text=f"Checked {n} of {total}")
        try:
            if mode == "Now":
                rows = prism.run_now(
                    doc, picked,
                    live_context=lambda kind, aid: sl.DataContext(
                        kind, aid, derivatives_loader=loaders.derivatives_loader(supabase),
                        sentiment_loader=loaders.sentiment_loader(supabase)),
                    market_context=lambda scope: sl.DataContext(
                        "market", scope.split(":", 1)[1], flows_loader=loaders.flows_loader(supabase),
                        sentiment_loader=loaders.sentiment_loader(supabase)),
                    progress=progress)
            else:
                as_of = pd.Timestamp(dt.datetime.combine(day, clock), tz="UTC")
                if as_of >= pd.Timestamp.now(tz="UTC"):
                    st.warning("Choose a moment in the past.")
                    return
                from signal_library.replay_display import display_run

                run = display_run(supabase, max_steps=1, shortcut=True)   # one moment, every asset
                rows = prism.run_now(doc, picked, live_context=None, replay=(run, as_of), progress=progress)
        except ValueError as exc:
            st.error(str(exc))
            return
        finally:
            bar.empty()
        st.session_state["prism_result"] = (pick, labels[pick], rows)

    stored = st.session_state.get("prism_result")
    if stored and stored[0] in docs:
        _results(st, docs[stored[0]], stored[1], stored[2])
    if problem:
        st.caption(f"Saved Sets could not be read: {problem}")


def _results(st, doc: dict, title: str, rows: list[dict]) -> None:
    counts = {a: sum(r["answer"] == a for r in rows) for a in ("yes", "no", "unknown")}
    path = rows[0]["path"] if rows else ""
    st.markdown(f"**{title}** · {path} · {prism.ANSWER_ICON['yes']} {counts['yes']} Yes · "
                f"{prism.ANSWER_ICON['no']} {counts['no']} No · {prism.ANSWER_ICON['unknown']} {counts['unknown']} Unknown")
    if path.startswith("Reconstruction"):
        st.info("Reconstruction: today's rules on data cut at that moment, from today's providers. Not a record of what "
                "was shown then, and not for statistics.")
    order = {"yes": 0, "unknown": 1, "no": 2}
    frame = prism.table(doc, sorted(rows, key=lambda r: (order[r["answer"]], r["asset"])))
    st.dataframe(frame, hide_index=True, width="stretch", column_config={
        "Answer": st.column_config.TextColumn("Answer", help=HELP["answer"]),
        "How sure": st.column_config.TextColumn("How sure", help=HELP["how_sure"]),
        "Data available": st.column_config.TextColumn("Data available", help=HELP["available"]),
    })


# ----------------------------------------------------------------------------------------------- scheduled scans

SCHEDULES = {"4H": "Each 4-hour close", "1D": "Each daily close", "1W": "Each weekly close", "times": "Set times"}
DAYS = {"all": "Every day", "weekdays": "Weekdays only"}
ZONES = ["Asia/Bangkok", "UTC", "Europe/London", "Europe/Berlin", "America/New_York", "America/Los_Angeles",
         "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney"]
SQL_HINT = ("Scheduled scans need their tables. Run sql/2026-11-06_prism_scans.sql in the Supabase SQL editor.")
RPC_ERRORS = {
    "prism_preview_admins_only": "Saving scans is not switched on for every account yet (the database update is "
                                 "pending).",
    "too_many_active_scans": "You already have 5 active scans. Pause or delete one first.",
    "set_not_scannable": "This Set has no decision, so it cannot be scanned.",
    "bad_schedule": "The schedule is not valid.",
    "not_owner": "This scan is not yours.",
    "too_large": "This Set is too large.",
}


def _rpc_message(exc) -> str:
    text = str(getattr(exc, "message", "") or exc)
    for code, words in RPC_ERRORS.items():
        if code in text:
            return words
    return text[:200]


def _schedule_from(choice: str, times: str, days: str, tz: str) -> dict:
    if choice != "times":
        return {"kind": "close", "timeframe": choice}
    return {"kind": "times", "times": [t.strip() for t in times.split(",") if t.strip()], "days": days, "tz": tz}


def _scheduled(st, supabase, labels: dict, docs: dict, user_id: str) -> None:
    import prism_scans as ps

    st.caption("A scan runs a Set on your Watchlist on a schedule and alerts you when an asset **turns Yes**: once, "
               "until a confirmed No resets it. Unknown never alerts. Alerts appear in the app and follow your email "
               "settings (instant, or the daily summary). Each run uses only finished candles at its time.")
    try:
        scans = supabase.table("prism_scans").select("*").order("created_at").execute().data or []
    except Exception:
        st.info(SQL_HINT)
        return
    if scans:
        st.dataframe(pd.DataFrame([{
            "Scan": s["name"], "Runs": ps.describe_schedule(s["schedule"]),
            "Alerts": "when an asset turns Yes" if s["alert_mode"] == "change" else "every run while Yes",
            "State": "⏸️ paused" if s["paused"] else "▶️ active",
            "Last run": str(s.get("last_run_at") or "not yet")[:16].replace("T", " "),
        } for s in scans]), hide_index=True, width="stretch")
    options = ["new"] + [s["id"] for s in scans]
    by_id = {s["id"]: s for s in scans}
    chosen = st.selectbox("Scan", options, key="prism_scan_pick",
                          format_func=lambda k: "➕ New scan" if k == "new" else by_id[k]["name"])
    scan = by_id.get(chosen)
    _scan_form(st, supabase, labels, docs, scan)
    if scan:
        _scan_actions(st, supabase, scan)
        _scan_results(st, supabase, scan)


def _scan_form(st, supabase, labels, docs, scan) -> None:
    import prism_scans as ps

    sched = (scan or {}).get("schedule") or {"kind": "close", "timeframe": "1D"}
    current = sched.get("timeframe") if sched.get("kind") == "close" else "times"
    set_keys = list(labels)
    source_key = ((scan or {}).get("set_source") or {}).get("key")
    with st.form(f"prism_scan_form_{(scan or {}).get('id', 'new')}", border=True):
        name = st.text_input("Name", value=(scan or {}).get("name") or "", max_chars=80)
        pick = st.selectbox("Set", set_keys + (["pinned"] if scan else []),
                            index=(set_keys.index(source_key) if source_key in set_keys else
                                   (len(set_keys) if scan else 0)),
                            format_func=lambda k: f"📌 keep the pinned copy: {scan['set_body'].get('name')}"
                            if k == "pinned" else labels[k],
                            help="The scan keeps its own copy of the Set, so later edits to the Set do not change "
                                 "it until you pin it again here.")
        c1, c2 = st.columns(2)
        choice = c1.selectbox("Run", list(SCHEDULES), index=list(SCHEDULES).index(current),
                              format_func=SCHEDULES.get)
        mode = c2.radio("Alert me", ["change", "every"], horizontal=True,
                        index=0 if (scan or {}).get("alert_mode", "change") == "change" else 1,
                        format_func=lambda m: "when an asset turns Yes" if m == "change" else "every run while Yes")
        c3, c4, c5 = st.columns(3)
        times = c3.text_input("Times (for Set times)", value=", ".join(sched.get("times") or ["08:00"]),
                              help="Up to 4, like 08:00, 20:00")
        days = c4.selectbox("Days", list(DAYS), format_func=DAYS.get,
                            index=list(DAYS).index(sched.get("days")) if sched.get("days") in DAYS else 0)
        tz_now = sched.get("tz") or "Asia/Bangkok"
        zones = ZONES if tz_now in ZONES else [tz_now] + ZONES
        tz = c5.selectbox("Time zone", zones, index=zones.index(tz_now))
        email = st.checkbox("Also email me (instant or in the daily summary, as in your alert settings)",
                            value=((scan or {}).get("notify") or {}).get("email", True))
        saved = st.form_submit_button("💾 Save scan", type="primary")
    if not saved:
        return
    body = scan["set_body"] if pick == "pinned" else docs[pick]
    schedule = _schedule_from(choice, times, days, tz)
    problems = ps.validate_schedule(schedule) + (sg.validate_set(body) if sg.scannable(body) else
                                                 ["This Set has no decision, so it cannot be scanned."])
    if not name.strip():
        problems.append("Give the scan a name.")
    if problems:
        st.error(" ".join(problems[:3]))
        return
    warning = ps.schedule_warning(schedule, body)
    try:
        supabase.rpc("prism_save_scan", {
            "p_id": (scan or {}).get("id"), "p_name": name.strip(), "p_set": body,
            "p_source": (scan or {}).get("set_source") if pick == "pinned" else {"key": pick, "name": labels[pick]},
            "p_schedule": schedule, "p_alert_mode": mode, "p_notify": {"in_app": True, "email": bool(email)},
            "p_paused": bool((scan or {}).get("paused", False)),
        }).execute()
    except Exception as exc:
        st.error(_rpc_message(exc))
        return
    st.success("Scan saved. It runs at its next scheduled time." + (f" Note: {warning}" if warning else ""))


def _scan_actions(st, supabase, scan) -> None:
    cols = st.columns(3)
    paused = scan["paused"]
    if cols[0].button("▶️ Resume" if paused else "⏸️ Pause", key=f"prism_pause_{scan['id']}"):
        try:
            supabase.rpc("prism_save_scan", {
                "p_id": scan["id"], "p_name": scan["name"], "p_set": scan["set_body"], "p_source": scan["set_source"],
                "p_schedule": scan["schedule"], "p_alert_mode": scan["alert_mode"], "p_notify": scan["notify"],
                "p_paused": not paused}).execute()
            st.success("Resumed." if paused else "Paused.")
        except Exception as exc:
            st.error(_rpc_message(exc))
    if cols[1].button("🔁 Reset alerts", key=f"prism_reset_{scan['id']}",
                      help="Forget which assets already alerted, so each current Yes alerts once more."):
        try:
            supabase.rpc("prism_reset_latches", {"p_id": scan["id"]}).execute()
            st.success("Alerts reset.")
        except Exception as exc:
            st.error(_rpc_message(exc))
    if cols[2].button("🗑️ Delete", key=f"prism_delete_{scan['id']}"):
        try:
            supabase.rpc("prism_delete_scan", {"p_id": scan["id"]}).execute()
            st.success("Deleted.")
        except Exception as exc:
            st.error(_rpc_message(exc))


def _scan_results(st, supabase, scan) -> None:
    import prism_scans as ps

    try:
        runs = ps.latest_runs(supabase, scan["id"])
    except Exception:
        return
    if not runs:
        st.caption("No runs yet. The first run happens at the next scheduled time.")
        return
    for run in runs:
        market = "Crypto" if run["market"] == "crypto" else "Shares"
        late = run.get("late_seconds") or 0
        st.markdown(f"**{market}** · run for {str(run['cutoff'])[:16].replace('T', ' ')} UTC"
                    + (f" · ran {late // 60} min late" if late >= 300 else "")
                    + (" · ❌ failed" if run["status"] == "failed" else ""))
        if run["status"] == "failed":
            st.caption(str(run.get("error") or "")[:300])
    grouped = ps.group_results(runs)
    for key, title, icon in (("new_yes", "New Yes · alert sent", "🔔"), ("still_yes", "Still Yes · no new alert", "✅"),
                             ("unknown", "Couldn't decide · never alerts", "❔")):
        items = grouped[key]
        if items:
            st.markdown(f"{icon} **{title}** ({len(items)})")
            st.markdown("\n".join(f"- **{r['asset']}**: {r['reason']}" for r in items))
    if grouped["no"]:
        with st.expander(f"⛔ No ({len(grouped['no'])})"):
            st.markdown("\n".join(f"- **{r['asset']}**: {r['reason']}" for r in grouped["no"]))
    st.caption("This is the stored record of what each run said. A later reconstruction can differ if a data provider "
               "revised its history.")

