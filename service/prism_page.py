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
    from service import coin_names

    names = coin_names.labels(dict(crypto))
    return ([("crypto", k, names.get(k, str(v))) for k, v in dict(crypto).items()]
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
          focus_set: str | None = None, history: str | None = None) -> dict:
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
                                     results.get(s["id"])), "history": s["id"] == history or None} for s in scans],
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
            if op == "history":                  # the page opens 🕰️ Visualize History under the board
                return {"status": "ok", "message": "", "history": scan["id"]}
            if op == "history_close":
                _strips.pop((uid, scan["id"]), None)
                return {"status": "ok", "message": "", "history": None}
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


# ---- 🕰️ Visualize History: the scan's Set on every past day, for each asset (prism_view._history_*) -------------------

_strips: dict = {}               # (member, scan) -> the strip being worked out; kept while the service runs


def _scan_and_obj(db, scan_id: str):
    import prism_board as pb

    scans, _ = _scans(db)
    scan = next((s for s in scans if s["id"] == scan_id), None)
    return (scan, pb.scan_object(scan)) if scan else (None, None)


def _summary(scan: dict, obj: dict, strip: dict) -> dict:
    import set_history

    rows = [r for r in strip.get("rows") or [] if r.get("spans")]
    pending = int(strip.get("pending") or 0)
    ready = {o: (not pending) or set_history.covers(strip, y) for o, y in {"1Y": 1, "3Y": 3, "10Y": 10, "All": 0}.items()}
    return {"scan": scan["id"], "name": obj["name"], "assets": [{"key": r["key"], "name": r["name"], "kind": r["kind"], "id": r["id"]} for r in rows],
            "pending": pending, "total": len(strip.get("rows") or []), "ready": ready,
            "views": scan.get("chart_views") or {}}


def history_start(db, uid: str, scan_id: str, lang: str) -> dict:
    import prism_board as pb
    import set_history

    with i18n.using(lang):
        scan, obj = _scan_and_obj(db, scan_id)
        if not scan:
            return {"status": "error", "message": i18n.t("That scan no longer exists.")}
        markets = pb.scan_markets(obj, assets_of(db, uid))
        picked = [(k if k == "crypto" else "equity", i, n) for m in ("crypto", "equity") for k, i, n in markets[m]]
        if not picked:
            return {"status": "error", "message": i18n.t("This scan has no assets on your Watchlist right now.")}
        strip = set_history.quick_rows(db, obj["set"], picked)
        _strips[(uid, scan_id)] = strip
        if len(_strips) > 300:
            _strips.pop(next(iter(_strips)))
        return {"status": "ok", **_summary(scan, obj, strip)}


def history_more(db, uid: str, scan_id: str, lang: str) -> dict:
    """One more step of older years (3, then 10, then all), as the classic page does between redraws."""
    import set_history

    with i18n.using(lang):
        strip = _strips.get((uid, scan_id))
        if strip is None:
            return history_start(db, uid, scan_id, lang)
        scan, obj = _scan_and_obj(db, scan_id)
        if not scan:
            return {"status": "error", "message": i18n.t("That scan no longer exists.")}
        set_history.complete_row(db, obj["set"], strip)
        return {"status": "ok", **_summary(scan, obj, strip)}


def history_chart(db, uid: str, scan_id: str, top: str, years: str, dark: bool, show_no: bool, lang: str) -> dict:
    import history_chart as hc

    with i18n.using(lang):
        strip = _strips.get((uid, scan_id))
        if strip is None:
            started = history_start(db, uid, scan_id, lang)
            if started.get("status") != "ok":
                return started
            strip = _strips[(uid, scan_id)]
        scan, obj = _scan_and_obj(db, scan_id)
        if not scan:
            return {"status": "error", "message": i18n.t("That scan no longer exists.")}
        rows = [r for r in strip.get("rows") or [] if r.get("spans")]
        if not rows:
            return {"status": "ok", "chart": None, "message": i18n.t("No long daily history was available for these assets.")}
        names = {r["key"]: r for r in rows}
        top = top if top in names else rows[0]["key"]
        summary = _summary(scan, obj, strip)
        span = years if years in summary["ready"] else "1Y"
        note = ""
        if not summary["ready"][span]:
            best = max((o for o in ("1Y", "3Y", "10Y") if summary["ready"][o]), key=lambda o: {"1Y": 1, "3Y": 3, "10Y": 10}[o])
            note = i18n.t('⏳ {span} is still being worked out ({len_strip_rows_pending} of {len_strip_rows} assets complete); showing {best} until then.', span=span, len_strip_rows_pending=summary["total"] - summary["pending"], len_strip_rows=summary["total"], best=best)
            span = best
        data = hc.payload(strip, top, {"1Y": 1, "3Y": 3, "10Y": 10, "All": 0}[span], dark=dark, show_no=show_no, set_name=obj["name"])
        if not data:
            return {"status": "ok", "chart": None, "message": i18n.t("The chosen asset's daily history could not be loaded.")}
        r = names[top]
        yes = sum(1 for x in r["spans"] if x[2] == "yes")
        caption = i18n.t('Green = Yes (conditions met), amber = Unknown, clear = No · {names_top}: Yes {yes} times since {since}. Tap a small chart to put it on top. A description of the past, not a forecast; each day uses only data up to its close.', names_top=r["name"], yes=yes, since=r["spans"][0][0][:4])
        return {"status": "ok", "chart": data, "top": top, "span": span, "note": note, "caption": caption, **summary}
