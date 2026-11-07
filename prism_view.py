"""
🔎 Prism Scan page (build stage 7; earlier stages 2 and 3).

Saved Prism Scans on a board (prism_component.py): each scan is a Set plus its assets, schedule and alerts, saved
through prism_put_scan (sql/2026-11-08_prism_scan_objects.sql). ▶ runs a scan now on the latest finished candles,
⏪ rebuilds a past moment; those results are shown, not saved. Scheduled runs happen in the background worker
(prism_scans.py) and are stored there. Nothing runs until a button is pressed.
"""

from __future__ import annotations

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
    labels = {k: f"🔰 {d['name']}" for k, d in prism.demo_sets().items()}
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
    """The Prism Scans board (build stage 7)."""
    import json

    import lattice_panel
    import prism_board as pb
    import prism_component
    import signal_groups_inspector as gi

    _SUPABASE[0] = supabase
    if not assets:
        st.info("No assets in the watchlists.")
        return
    cached = st.session_state.get("siggroups_saved")
    if not cached or time.time() - cached[0] > 60:
        cached = (time.time(), *gi.saved_configs(supabase))
        st.session_state["siggroups_saved"] = cached
    _, saved, problem = cached
    choices = pb.set_choices(saved, user_id)
    builtins: list = []

    def load():
        rows = supabase.table("prism_scans").select("*").order("created_at").execute().data or []
        builtins[:] = [r for r in rows if r.get("builtin")]    # the built-in alerts: shown below, not on the board
        return [r for r in rows if not r.get("builtin")]

    try:
        scans = load()
    except Exception:
        st.info(SQL_HINT)
        return
    by_id = {s["id"]: s for s in scans}
    now = pd.Timestamp.now(tz="UTC")
    early = lattice_panel.pending(st, "prism_board", "action")
    if early and early != st.session_state.get("prism_action_seen"):
        # a press from the board, handled before drawing: the board then shows the result in this same redraw
        st.session_state["prism_action_seen"] = early
        try:
            action = json.loads(early)
        except ValueError:
            action = {}
        st.session_state["prism_flash"] = handle(st, supabase, action, by_id, choices, assets, now)
        scans = load()
        by_id = {s["id"]: s for s in scans}
    runs, latches = _history(supabase, list(by_id))
    results = st.session_state.setdefault("prism_results", {})
    flash = st.session_state.pop("prism_flash", None)
    if flash:
        (st.success if flash[0] == "ok" else st.error)(flash[1])
    library = pb.library(choices, assets)
    shown = lattice_panel.provided_shown(st)
    hidden = 0
    if not shown:                                    # example Sets and the built-in alerts are hidden
        keep = [s for s in library["sets"] if not s["meta"].startswith("🔰")]
        hidden = len(library["sets"]) - len(keep) + (1 if builtins else 0)
        library["sets"] = keep
    lattice_panel.provided_switch(st, hidden, "provided_prism")
    data = {
        "library": library, "zones": pb.ZONES,
        "scheduled": pb.scheduled_count(scans), "max_scheduled": pb.MAX_SCHEDULED,
        "open_new": st.session_state.pop("prism_open_new", None),
        "scans": [pb.view(s, runs.get(s["id"], []), latches.get(s["id"], []), choices, assets, now,
                          results.get(s["id"])) for s in scans],
    }
    try:
        result = prism_component.component()(key="prism_board", data=data, on_action_change=lambda: None)
    except Exception as exc:
        st.info(f"The Prism board could not load here ({str(exc)[:120]}).")
        result = None
    raw = getattr(result, "action", None)
    if raw and raw != st.session_state.get("prism_action_seen"):
        st.session_state["prism_action_seen"] = raw
        try:
            action = json.loads(raw)
        except ValueError:
            action = {}
        st.session_state["prism_flash"] = handle(st, supabase, action, by_id, choices, assets, now)
        lattice_panel.rerun(st)
    if shown:
        _builtin_section(st, supabase, builtins)
    st.caption("Answers are descriptive readings, not forecasts or advice. ▶ uses the latest finished candles; ⏪ "
               "rebuilds a past moment from today's data providers (a reconstruction, not a record).")
    if problem:
        st.caption(f"Saved Sets could not be read: {problem}")


CHANNEL_WORDS = {"account": "as your alert settings", "instant": "instantly (app and email)", "digest": "daily summary",
                 "app": "app only", "off": "off"}


def _builtin_section(st, supabase, builtins: list) -> None:
    """The six built-in alerts (Trend, Stretch and Flow, up and down): what each checks, where its alerts go, and
    which assets are past the line now. Their lines and on/off are set in Notifications → Configure Alert Rules."""
    if not builtins:
        return
    import builtin_alerts as ba

    order = {k: n for n, k in enumerate(ba.BUILTINS)}
    builtins = sorted(builtins, key=lambda r: order.get(r.get("builtin"), 99))
    _, latches = _history(supabase, [b["id"] for b in builtins])
    on = sum((b.get("notify") or {}).get("channel") != "off" for b in builtins)
    with st.expander(f"🔰 Built-in alerts · {on} of {len(builtins)} on", icon=":material/notifications_active:"):
        st.caption("Trend, Stretch and Flow alerts, checked at each daily close (crypto 00:10 UTC, shares 10 minutes "
                   "after the New York close) on the same readings as the dashboard. Change the lines and switch "
                   "them on or off in Notifications → Configure Alert Rules. They don't count towards your "
                   f"{MAX_SCANS_TEXT} scheduled scans.")
        rows = []
        for b in builtins:
            reading, direction, _ = ba.BUILTINS[b["builtin"]]
            line = float((b.get("set_source") or {}).get("line") or 0)
            channel = (b.get("notify") or {}).get("channel") or "account"
            past = latches.get(b["id"], [])
            rows.append({"Alert": ("🔔 " if channel != "off" else "🔕 ") + b["name"],
                         "Says Yes at": f"{direction * line:+.0f}",
                         "Alerts again after": f"{direction * ba.rearm_level(line):+.0f}",
                         "Alerts go": CHANNEL_WORDS.get(channel, channel),
                         "Past the line now": len(past) if channel != "off" else "—"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


MAX_SCANS_TEXT = "5"


def _history(supabase, ids: list) -> tuple[dict, dict]:
    """The last runs (newest first) and the open latches, per scan."""
    runs, latches = {}, {}
    if not ids:
        return runs, latches
    try:
        rows = (supabase.table("prism_scan_runs").select("scan_id, market, cutoff, status, results")
                .in_("scan_id", ids).order("cutoff", desc=True).limit(12 * len(ids)).execute().data or [])
        for r in rows:
            runs.setdefault(r["scan_id"], []).append(r)
        for r in (supabase.table("prism_scan_latches").select("scan_id, asset_key").in_("scan_id", ids)
                  .execute().data or []):
            latches.setdefault(r["scan_id"], []).append(r["asset_key"])
    except Exception:
        pass
    return runs, latches


def _put(supabase, scan_id, obj) -> str:
    import prism_board as pb

    out = supabase.rpc("prism_put_scan", {"p_id": scan_id, "p_scan": pb.for_database(obj)}).execute()
    return getattr(out, "data", None) or scan_id


def handle(st, supabase, action: dict, by_id: dict, choices: dict, assets, now) -> tuple[str, str]:
    """Carry out one board action. Returns ("ok" | "error", message)."""
    import prism_board as pb

    op = action.get("op")
    scan = by_id.get(action.get("scan"))
    try:
        if op == "create":
            if action.get("set") not in choices:
                return "error", "That Set is no longer available."
            new_id = _put(supabase, None, pb.new_scan(action["set"], choices))
            st.session_state["prism_open_new"] = new_id
            return "ok", "Scan added. Press ▶ to run it, or open it to choose its assets, schedule and alerts."
        if scan is None:
            return "error", "That scan no longer exists."
        obj = pb.tidy_snoozes(pb.scan_object(scan), now)
        if op in ("run", "run_past"):
            return _run(st, scan, obj, op, action, assets)
        if op == "delete":
            supabase.rpc("prism_delete_scan", {"p_id": scan["id"]}).execute()
            st.session_state.get("prism_results", {}).pop(scan["id"], None)
            return "ok", f"Deleted “{scan['name']}”."
        if op == "duplicate":
            new_id = _put(supabase, None, pb.duplicate(obj))
            st.session_state["prism_open_new"] = new_id
            return "ok", "Copied. The copy runs only when you press ▶ until you give it a schedule."
        if op in ("pause", "resume"):
            _put(supabase, scan["id"], {**obj, "paused": op == "pause"})
            return "ok", ("Paused: no runs and no alerts until you resume." if op == "pause" else
                          "Resumed. The first run records answers without alerting, so resuming never sends a burst.")
        if op == "add_asset":
            obj, problem = pb.add_asset(obj, action.get("item") or {})
        elif op == "remove_asset":
            obj, problem = pb.remove_asset(obj, int(action.get("index", -1)))
        elif op == "schedule":
            schedule, problem = pb.schedule_from(action)
            if schedule:
                obj = {**obj, "schedule": schedule}
        elif op == "alerts":
            obj, problem = {**obj, "notify": pb.notify_from(action)}, None
        elif op == "snooze":
            obj, problem = pb.snooze(obj, str(action.get("key")), int(action.get("days") or 0), now), None
        elif op == "unsnooze":
            obj, problem = pb.unsnooze(obj, str(action.get("key"))), None
        elif op == "update_set":
            if action.get("key") not in choices:
                return "error", "That version is no longer available."
            obj, problem = pb.switch_set(obj, action["key"], choices), None
        else:
            return "error", "Unknown action."
        if problem:
            return "error", problem
        _put(supabase, scan["id"], obj)
        return "ok", "Saved."
    except Exception as exc:
        return "error", _rpc_message(exc)


def _run(st, scan, obj, op, action, assets) -> tuple[str, str]:
    import prism_board as pb

    if time.time() - st.session_state.get("prism_last_run", 0.0) < COOLDOWN_SECONDS:
        return "error", f"Please wait a few seconds between runs (at most one every {COOLDOWN_SECONDS} seconds)."
    markets = pb.scan_markets(obj, assets)
    picked = [(k if k == "crypto" else "equity", i, n) for m in ("crypto", "equity") for k, i, n in markets[m]]
    if not picked:
        return "error", "This scan has no assets on your Watchlist right now."
    if len(picked) > prism.MAX_ASSETS:
        return "error", (f"This scan covers {len(picked)} assets; ▶ checks up to {prism.MAX_ASSETS} at a time. "
                         "Narrow its assets (for example All crypto), or let its schedule run them all.")
    st.session_state["prism_last_run"] = time.time()
    if op == "run":
        rows = prism.run_now(
            obj["set"], picked,
            live_context=lambda kind, aid: sl.DataContext(
                kind, aid, derivatives_loader=_loader("derivatives"), sentiment_loader=_loader("sentiment")),
            market_context=lambda scope: sl.DataContext(
                "market", scope.split(":", 1)[1], flows_loader=_loader("flows"), sentiment_loader=_loader("sentiment")))
        title = f"Run now at {pd.Timestamp.now(tz='UTC'):%d %b %H:%M} UTC"
    else:
        try:
            as_of = pd.Timestamp(f"{action.get('date')} {action.get('time') or '00:05'}", tz="UTC")
        except (ValueError, TypeError):
            return "error", "Choose a date and time."
        if as_of >= pd.Timestamp.now(tz="UTC"):
            return "error", "Choose a moment in the past."
        from signal_library.replay_display import display_run

        run = display_run(_SUPABASE[0], max_steps=1, shortcut=True)
        rows = prism.run_now(obj["set"], picked, live_context=None, replay=(run, as_of))
        title = f"Reconstruction at {as_of:%d %b %Y %H:%M} UTC: today's data providers, not a record of what was shown"
    counts = {a: sum(r["answer"] == a for r in rows) for a in ("yes", "no", "unknown")}
    st.session_state.setdefault("prism_results", {})[scan["id"]] = {
        "title": f"{title} · Yes {counts['yes']} · No {counts['no']} · ? {counts['unknown']}",
        "rows": [{"asset": r["asset"], "answer": r["answer"], "reason": r["reason"]} for r in rows]}
    return "ok", f"“{scan['name']}”: Yes {counts['yes']} · No {counts['no']} · Unknown {counts['unknown']}."


_SUPABASE = [None]


def _loader(which):
    db = _SUPABASE[0]
    return {"derivatives": loaders.derivatives_loader, "sentiment": loaders.sentiment_loader,
            "flows": loaders.flows_loader}[which](db)


# ----------------------------------------------------------------------------------------------- messages

SQL_HINT = ("Prism Scans need their tables. Run sql/2026-11-06_prism_scans.sql and "
            "sql/2026-11-08_prism_scan_objects.sql in the Supabase SQL editor.")
RPC_ERRORS = {
    "too_many_active_scans": "You already have 5 scheduled scans. Pause one, or set it to run only when you press Play.",
    "set_not_scannable": "This Set has no decision, so it cannot be scanned.",
    "bad_schedule": "The schedule is not valid.",
    "bad_assets": "A scan needs 1 to 60 assets or Watchlist groups.",
    "bad_alerts": "The alert setting is not valid.",
    "bad_name": "A scan needs a name of 1 to 80 characters.",
    "not_owner": "This scan is not yours.",
    "too_large": "This Set is too large.",
    "prism_put_scan": "Prism Scans need a database update: run sql/2026-11-08_prism_scan_objects.sql.",
}


def _rpc_message(exc) -> str:
    text = str(getattr(exc, "message", "") or exc)
    for code, words in RPC_ERRORS.items():
        if code in text:
            return words
    return text[:200]
