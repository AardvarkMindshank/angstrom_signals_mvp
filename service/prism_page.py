"""🔎 Prism Scan for the new app: the classic board (prism_component.py, hosted unchanged in the browser) with its
Python side (prism_view.py) as data. The board's data comes from board(); each press on it comes to action(), which
does exactly what the classic page does (prism_board.py, prism.py, the prism_put_scan / prism_delete_scan database
functions) and says what to show. A ▶ / ⏪ result is returned to the browser, which keeps it for the board (the
classic app kept it in the page's session); nothing about a member is logged.
"""
from __future__ import annotations

import time

import i18n

COOLDOWN_SECONDS = 20            # as the classic page: one Run now per member every 20 seconds
_last_run: dict[str, float] = {}


def assets_of(db, uid: str) -> list[tuple[str, str, str]]:
    """The member's watchlists as the classic page passes them: (kind, id, name)."""
    try:
        rows = db.table("user_preferences").select("crypto_watchlist, stock_watchlist").eq("user_id", uid).limit(1).execute().data or []
    except Exception:
        rows = []
    r = rows[0] if rows else {}
    crypto = r.get("crypto_watchlist") or {}
    stocks = r.get("stock_watchlist") or {}
    return ([("crypto", k, str(v)) for k, v in dict(crypto).items()]
            + [("equity", k, f"{v} ({k})") for k, v in dict(stocks).items()])


def _context(db, uid: str):
    from service.lattice import _plan, _saved
    import prism_board as pb

    plan, display, settings = _plan(db, uid)
    return pb.set_choices(_saved(db), uid), plan, display, settings


def _scans(db) -> tuple[list, list]:
    rows = db.table("prism_scans").select("*").order("created_at").execute().data or []
    return [r for r in rows if not r.get("builtin")], [r for r in rows if r.get("builtin")]


def _builtin_rows(db, builtins: list) -> list[dict]:
    """The built-in alerts' table (prism_view._builtin_section), as rows."""
    import builtin_alerts as ba
    import prism_view as pv

    if not builtins:
        return []
    order = {k: n for n, k in enumerate(ba.BUILTINS)}
    builtins = sorted(builtins, key=lambda r: order.get(r.get("builtin"), 99))
    _, latches = pv._history(db, [b["id"] for b in builtins])
    rows = []
    for b in builtins:
        reading, direction, _ = ba.BUILTINS[b["builtin"]]
        line = float((b.get("set_source") or {}).get("line") or 0)
        channel = (b.get("notify") or {}).get("channel") or "account"
        rows.append({"name": b["name"], "on": channel != "off", "yes_at": f"{direction * line:+.0f}",
                     "again_after": f"{direction * ba.rearm_level(line):+.0f}",
                     "goes": i18n.t(pv.CHANNEL_WORDS.get(channel, channel)),
                     "past": len(latches.get(b["id"], [])) if channel != "off" else None})
    return rows


def board(db, uid: str, lang: str, results: dict | None = None, open_new: str | None = None,
          focus_set: str | None = None) -> dict:
    import pandas as pd
    import prism_board as pb
    import prism_view as pv

    with i18n.using(lang):
        assets = assets_of(db, uid)
        choices, plan, display, settings = _context(db, uid)
        try:
            scans, builtins = _scans(db)
        except Exception:
            return {"ready": False, "message": i18n.t(pv.SQL_HINT)}
        runs, latches = pv._history(db, [s["id"] for s in scans])
        now = pd.Timestamp.now(tz="UTC")
        shown = settings.get("show_provided", True) is not False
        results = results or {}
        return {
            "ready": True, "has_assets": bool(assets),
            "board": {
                "library": pb.library(choices, assets, plan, display),
                "zones": pb.ZONES, "show_provided": shown,
                "scheduled": pb.scheduled_count(scans), "max_scheduled": pb.MAX_SCHEDULED,
                "open_new": open_new, "focus_set": focus_set,
                "scans": [{**pb.view(s, runs.get(s["id"], []), latches.get(s["id"], []), choices, assets, now,
                                     results.get(s["id"])), "history": None} for s in scans],
            },
            "builtins": _builtin_rows(db, builtins) if shown else [],
            "max_scans": pv.MAX_SCANS_TEXT,
        }


def action(db, uid: str, lang: str, act: dict) -> dict:
    """One press on the board. {"status": "ok" | "error", "message", and what the page does next: "open_new" (a
    scan to open), "result" ({scan, value}: a ▶ / ⏪ answer to keep), "goto" (a page address)}."""
    import pandas as pd
    import prism_board as pb
    import prism_view as pv

    with i18n.using(lang):
        op = act.get("op")
        choices, _, _, _ = _context(db, uid)
        scans, _ = _scans(db)
        by_id = {s["id"]: s for s in scans}
        scan = by_id.get(act.get("scan"))
        now = pd.Timestamp.now(tz="UTC")
        try:
            if op == "open_set":                 # 🔍 Look inside: open it in Signal Sets (a provided Set as your copy)
                c = choices.get(act.get("set"))
                if c is None:
                    return {"status": "error", "message": i18n.t("That Set is no longer available.")}
                start = act["set"] if c.get("provided") else f"saved:{c['config']}"
                return {"status": "ok", "message": "", "goto": "#lattice/sets/" + start}
            if op == "create":
                if act.get("set") not in choices:
                    return {"status": "error", "message": i18n.t("That Set is no longer available.")}
                fresh = pb.new_scan(act["set"], choices)
                fresh["name"] = pb.unique_name(fresh["name"], [s.get("name") for s in scans])
                new_id = pv._put(db, None, fresh)
                return {"status": "ok", "open_new": new_id,
                        "message": i18n.t("Scan added. Press ▶ to run it, or open it to choose its assets, schedule and alerts.")}
            if scan is None:
                return {"status": "error", "message": i18n.t("That scan no longer exists.")}
            obj = pb.tidy_snoozes(pb.scan_object(scan), now)
            if op in ("run", "run_past"):
                return _run(db, uid, scan, obj, op, act)
            if op in ("history", "history_close", "history_open"):
                return {"status": "error", "message": i18n.t("Visualize History is still in the classic app while it moves across.")}
            if op == "delete":
                db.rpc("prism_delete_scan", {"p_id": scan["id"]}).execute()
                return {"status": "ok", "message": i18n.t("Deleted “{name}”.", name=scan["name"]), "drop": scan["id"]}
            if op == "duplicate":
                new_id = pv._put(db, None, pb.duplicate(obj, [s.get("name") for s in scans]))
                return {"status": "ok", "open_new": new_id,
                        "message": i18n.t("Copied. The copy runs only when you press ▶ until you give it a schedule.")}
            if op in ("pause", "resume"):
                pv._put(db, scan["id"], {**obj, "paused": op == "pause"})
                return {"status": "ok", "message": i18n.t("Paused: no runs and no alerts until you resume.") if op == "pause" else
                        i18n.t("Resumed. The first run records answers without alerting, so resuming never sends a burst.")}
            if op == "add_asset":
                obj, problem = pb.add_asset(obj, act.get("item") or {})
            elif op == "remove_asset":
                obj, problem = pb.remove_asset(obj, int(act.get("index", -1)))
            elif op == "schedule":
                schedule, problem = pb.schedule_from(act)
                if schedule:
                    obj = {**obj, "schedule": schedule}
            elif op == "alerts":
                obj, problem = {**obj, "notify": pb.notify_from(act)}, None
            elif op == "snooze":
                obj, problem = pb.snooze(obj, str(act.get("key")), int(act.get("days") or 0), now), None
            elif op == "unsnooze":
                obj, problem = pb.unsnooze(obj, str(act.get("key"))), None
            elif op == "update_set":
                if act.get("key") not in choices:
                    return {"status": "error", "message": i18n.t("That version is no longer available.")}
                obj, problem = pb.switch_set(obj, act["key"], choices), None
            else:
                return {"status": "error", "message": "Unknown action."}
            if problem:
                return {"status": "error", "message": problem}
            pv._put(db, scan["id"], obj)
            return {"status": "ok", "message": i18n.t("Saved.")}
        except Exception as exc:
            return {"status": "error", "message": pv._rpc_message(exc)}


def _run(db, uid: str, scan: dict, obj: dict, op: str, act: dict) -> dict:
    """▶ Run now on the latest finished candles, or ⏪ a past moment rebuilt from today's data providers."""
    import pandas as pd
    import prism
    import prism_board as pb
    import prism_view as pv
    import signal_library as sl
    from signal_library import loaders

    if time.time() - _last_run.get(uid, 0.0) < COOLDOWN_SECONDS:
        return {"status": "error", "message": i18n.t('Please wait a few seconds between runs (at most one every {COOLDOWN_SECONDS} seconds).', COOLDOWN_SECONDS=COOLDOWN_SECONDS)}
    markets = pb.scan_markets(obj, assets_of(db, uid))
    picked = [(k if k == "crypto" else "equity", i, n) for m in ("crypto", "equity") for k, i, n in markets[m]]
    if not picked:
        return {"status": "error", "message": i18n.t("This scan has no assets on your Watchlist right now.")}
    if len(picked) > prism.MAX_ASSETS:
        return {"status": "error", "message": i18n.t('This scan covers {len_picked} assets; ▶ checks up to {prism_max_assets} at a time. Narrow its assets (for example All crypto), or let its schedule run them all.', len_picked=len(picked), prism_max_assets=prism.MAX_ASSETS)}
    _last_run[uid] = time.time()
    if op == "run":
        earlier = None
        if prism.steps_needed(obj["set"]) != 1:
            from signal_library.replay_display import display_run

            earlier = display_run(db, max_steps=prism.steps_needed(obj["set"]), shortcut=True)
        rows = prism.run_now(
            obj["set"], picked,
            live_context=lambda kind, aid: sl.DataContext(
                kind, aid, derivatives_loader=loaders.derivatives_loader(db), sentiment_loader=loaders.sentiment_loader(db),
                options_loader=loaders.options_loader(db)),
            market_context=lambda scope: sl.DataContext(
                "market", scope.split(":", 1)[1], flows_loader=loaders.flows_loader(db), sentiment_loader=loaders.sentiment_loader(db)),
            earlier_run=earlier)
        title = i18n.t('Run now at {pd_timestamp_now_tz_utc:%d %b %H:%M} UTC', pd_timestamp_now_tz_utc=pd.Timestamp.now(tz='UTC'))
    else:
        try:
            as_of = pd.Timestamp(f"{act.get('date')} {act.get('time') or '00:05'}", tz="UTC")
        except (ValueError, TypeError):
            _last_run.pop(uid, None)
            return {"status": "error", "message": i18n.t("Choose a date and time.")}
        if as_of >= pd.Timestamp.now(tz="UTC"):
            _last_run.pop(uid, None)
            return {"status": "error", "message": i18n.t("Choose a moment in the past.")}
        from signal_library.replay_display import display_run

        run = display_run(db, max_steps=prism.steps_needed(obj["set"]), shortcut=True)
        rows = prism.run_now(obj["set"], picked, live_context=None, replay=(run, as_of))
        title = i18n.t("Reconstruction at {as_of:%d %b %Y %H:%M} UTC: today's data providers, not a record of what was shown", as_of=as_of)
    counts = {a: sum(r["answer"] == a for r in rows) for a in ("yes", "no", "unknown")}
    value = {"title": f"{title} · Yes {counts['yes']} · No {counts['no']} · ? {counts['unknown']}",
             "rows": [{"asset": r["asset"], "answer": r["answer"], "reason": r["reason"],
                       **({"armed": r["armed"]} if r.get("armed") else {})} for r in rows]}
    return {"status": "ok", "result": {"scan": scan["id"], "value": value},
            "message": i18n.t('“{scan_name}”: Yes {counts_yes} · No {counts_no} · Unknown {counts_unknown}.', scan_name=scan['name'], counts_yes=counts['yes'], counts_no=counts['no'], counts_unknown=counts['unknown'])}
