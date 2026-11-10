"""
Prism scheduled scans (docs/design/lattice_prism.md §5.2, build stage 3).

A scan is a Set (pinned copy of one version, with a decision) run on its owner's Watchlist on a schedule. It runs
inside the existing background worker (run_alerts.py, every 5 minutes), after all existing alert and digest work,
using only the time left (at most BUDGET_SECONDS). Nothing new runs all the time.

Each run:
1. is due when a cutoff T has passed: a candle close (4H, 1D, 1W; plus SETTLE so providers have the closed candle)
   or a set time in the owner's time zone. Crypto and shares are separate runs, because their candles close at
   different times; shares close at 16:00 New York on weekdays, as the library's share calendar does;
2. is claimed once per (scan, market, cutoff) by a unique database row, so a retry or a second worker cannot repeat
   it or its notifications;
3. evaluates every asset at T through the point-in-time reconstruction, and stores the run record (results, input
   hashes, code identity). The stored record is what the scan said; a later reconstruction may differ if a provider
   revises data;
4. updates the latch per (scan, asset): the first Yes ever seen alerts once; only a confirmed No releases it; Unknown
   and failed runs neither open nor release it;
5. notifies as the scan says (stage 7): instantly (app and email), in the daily digest, in the app only, or not at all;
   when an asset turns Yes, and optionally when it turns No or when the scan can't run. Snoozed assets and the first
   run after resuming a paused scan update the latches without alerting.

Each scan scans its own assets: groups that follow the Watchlist (whole, crypto, shares) and fixed assets. A
"manual" scan has no schedule and runs only with the Play button.

A failure is recorded for that scan only. Missed cutoffs are not back-filled: a late worker runs the latest one.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

import prism
import signal_groups as sg

ALERT_TYPE = "prism"
TIMEFRAMES = ("4H", "1D", "1W")
MARKETS = ("crypto", "equity")
SETTLE = timedelta(minutes=10)          # a candle that just closed may take a few minutes to reach the provider
BUDGET_SECONDS = 240
MAX_ACTIVE_SCANS = 5
MAX_TIMES = 4
KEEP_DAYS = 90
STALE_CLAIM = timedelta(minutes=30)
NEW_YORK = ZoneInfo("America/New_York")
SHARE_CLOSE = (16, 0)                  # chart_data._US_CLOSE: the library's share calendar
DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TF_ORDER = {"15m": 0, "30m": 0.5, "1h": 1, "4h": 2, "4H": 2, "12h": 2.5, "1D": 3, "1d": 3, "1W": 4, "1w": 4}
TF_WORDS = {"4H": "4-hour", "1D": "daily", "1W": "weekly"}


# ----------------------------------------------------------------------------------------------- schedules

def _ts(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def validate_schedule(schedule) -> list[str]:
    if not isinstance(schedule, dict):
        return ["the schedule must be an object"]
    kind = schedule.get("kind")
    if kind == "manual":
        return []
    if kind == "close":
        return [] if schedule.get("timeframe") in TIMEFRAMES else [f"timeframe must be one of {TIMEFRAMES}"]
    if kind != "times":
        return ["schedule kind must be close or times"]
    errors = []
    times = schedule.get("times")
    if not isinstance(times, list) or not 1 <= len(times) <= MAX_TIMES:
        errors.append(f"choose 1 to {MAX_TIMES} times a day")
    else:
        for t in times:
            try:
                h, m = (int(p) for p in str(t).split(":"))
                assert 0 <= h < 24 and 0 <= m < 60
            except (ValueError, AssertionError):
                errors.append(f"{t!r} is not a time like 08:00")
    try:
        ZoneInfo(str(schedule.get("tz") or ""))
    except Exception:
        errors.append("choose a valid time zone")
    days = schedule.get("days", "all")
    if days not in ("all", "weekdays") and not (isinstance(days, list) and days and all(d in range(7) for d in days)):
        errors.append("days must be all, weekdays or a list of weekday numbers (Monday = 0)")
    return errors


def _close_cutoff(timeframe: str, market: str, now: pd.Timestamp) -> pd.Timestamp:
    ready = now - SETTLE
    if market == "crypto":
        if timeframe == "4H":
            return ready.floor("4h")
        day = ready.floor("1D")
        return day if timeframe == "1D" else day - pd.Timedelta(days=day.weekday())
    # Shares: one close a day at 16:00 New York on weekdays; a 4-hour scan checks shares at that daily close.
    # (Exchange holidays are not modelled: on a holiday the last closed candle is the previous session's.)
    wanted = (lambda d: d == 4) if timeframe == "1W" else (lambda d: d < 5)
    day = ready.tz_convert(NEW_YORK).date()
    while not wanted(day.weekday()) or _ny_close(day) > ready:
        day -= timedelta(days=1)
    return _ny_close(day)


def _ny_close(day) -> pd.Timestamp:
    local = datetime(day.year, day.month, day.day, SHARE_CLOSE[0], SHARE_CLOSE[1], tzinfo=NEW_YORK)
    return pd.Timestamp(local).tz_convert("UTC")


def _times_cutoff(schedule: dict, now: pd.Timestamp) -> pd.Timestamp:
    zone = ZoneInfo(schedule["tz"])
    local_now = now.tz_convert(zone)
    days = schedule.get("days", "all")
    allowed = set(range(7)) if days == "all" else set(range(5)) if days == "weekdays" else set(days)
    slots = sorted(tuple(int(p) for p in str(t).split(":")) for t in schedule["times"])
    for back in range(0, 8):
        day = (local_now - pd.Timedelta(days=back)).date()
        if day.weekday() not in allowed:
            continue
        for h, m in reversed(slots):
            moment = pd.Timestamp(datetime(day.year, day.month, day.day, h, m, tzinfo=zone)).tz_convert("UTC")
            if moment <= now:
                return moment
    raise ValueError("no scheduled time in the last week")


def latest_cutoff(schedule: dict, market: str, now) -> pd.Timestamp:
    """The most recent cutoff T that is due by `now`."""
    now = _ts(now)
    if schedule["kind"] == "close":
        return _close_cutoff(schedule["timeframe"], market, now)
    return _times_cutoff(schedule, now)


def describe_schedule(schedule: dict) -> str:
    if schedule.get("kind") == "manual":
        return "only when you press Play"
    if schedule.get("kind") == "close":
        return f"every {TF_WORDS.get(schedule.get('timeframe'), '?')} close"
    days = schedule.get("days", "all")
    when = "every day" if days == "all" else "weekdays" if days == "weekdays" else \
        ", ".join(DAY_NAMES[d] for d in sorted(days))
    return f"at {', '.join(schedule.get('times') or [])} ({schedule.get('tz')}), {when}"


def _member_timeframes(doc: dict) -> list[str]:
    out = []
    for g in doc.get("groups") or []:
        out += [m["ref"]["timeframe"] for m in (g.get("snapshot") or {}).get("members") or []]
    out += [i["ref"]["timeframe"] for i in doc.get("standalone") or []]
    return [t for t in out if t in TF_ORDER]


def schedule_warning(schedule: dict, doc: dict) -> str | None:
    """A warning, never a block, when the scan runs more often than any of its members can change."""
    tfs = _member_timeframes(doc)
    if not tfs or schedule.get("kind") != "close":
        return None
    fastest = min(tfs, key=TF_ORDER.get)
    if TF_ORDER[schedule["timeframe"]] < TF_ORDER[fastest]:
        return (f"This Set reads {TF_WORDS.get(fastest.upper(), fastest)} candles at the fastest, so running every "
                f"{TF_WORDS[schedule['timeframe']]} close gives the same answer until the next "
                f"{TF_WORDS.get(fastest.upper(), fastest)} close.")
    return None


# ----------------------------------------------------------------------------------------------- latches

def plan_alerts(answers: dict, latched: set, mode: str) -> tuple[list, list, list]:
    """(open, release, notify) asset keys. answers: asset key -> "yes" | "no" | "unknown" | "failed"."""
    opens, releases, notify = [], [], []
    for key, answer in answers.items():
        if answer == "yes":
            if key not in latched:
                opens.append(key)
                notify.append(key)
            elif mode == "every":
                notify.append(key)
        elif answer == "no" and key in latched:
            releases.append(key)
    return opens, releases, notify


def message(scan_name: str, row: dict, ended: bool = False) -> str:
    if ended:
        return f"Prism: “{scan_name}” no longer says Yes. {row['reason']}"[:500]
    return f"Prism: “{scan_name}” says Yes. {row['reason']}"[:500]


CHANNELS = ("instant", "digest", "app", "off")
UNKNOWN_SHARE = 0.5                     # "can't run" also covers a run where at least half the answers are Unknown


def alert_settings(scan: dict) -> dict:
    """The scan's alert settings. Scans saved before stage 7 ({in_app, email}) keep their old behaviour: email only
    when the account has instant alerts on ("account")."""
    notify = scan.get("notify") or {}
    if "channel" not in notify:
        return {"channel": "account", "email": notify.get("email", True), "on_yes": True, "on_no": False,
                "on_fail": False}
    channel = notify.get("channel") if notify.get("channel") in CHANNELS else "instant"
    return {"channel": channel, "on_yes": notify.get("on_yes", True) is not False, "on_no": bool(notify.get("on_no")),
            "on_fail": bool(notify.get("on_fail"))}


def snoozed(scan: dict, now) -> set:
    """Asset keys whose alerts are snoozed on this scan at `now`."""
    out = set()
    for key, until in (scan.get("snoozes") or {}).items():
        try:
            if _ts(until) > _ts(now):
                out.add(key)
        except (ValueError, TypeError):
            continue
    return out


# ----------------------------------------------------------------------------------------------- storage

class SupabaseStore:
    """Database access for the worker (service role). Every table is defined in sql/2026-11-06_prism_scans.sql."""

    def __init__(self, supabase):
        self.db = supabase

    def active_scans(self) -> list[dict]:
        return (self.db.table("prism_scans").select("*").eq("paused", False).execute().data or [])

    def claim(self, scan_id, market, cutoff, started) -> int | None:
        try:
            rows = (self.db.table("prism_scan_runs")
                    .insert({"scan_id": scan_id, "market": market, "cutoff": cutoff.isoformat(),
                             "started_at": started.isoformat(), "status": "running"}).execute().data or [])
        except Exception as exc:          # unique (scan_id, market, cutoff): already claimed
            if "duplicate" in str(exc).lower() or "23505" in str(exc):
                return None
            raise
        return rows[0]["id"] if rows else None

    def finish(self, run_id, fields: dict) -> None:
        self.db.table("prism_scan_runs").update(fields).eq("id", run_id).execute()

    def latches(self, scan_id) -> set:
        rows = self.db.table("prism_scan_latches").select("asset_key").eq("scan_id", scan_id).execute().data or []
        return {r["asset_key"] for r in rows}

    def open_latches(self, scan_id, keys, cutoff) -> None:
        if keys:
            self.db.table("prism_scan_latches").upsert(
                [{"scan_id": scan_id, "asset_key": k, "opened_at": cutoff.isoformat()} for k in keys]).execute()

    def release_latches(self, scan_id, keys) -> None:
        for k in keys:
            self.db.table("prism_scan_latches").delete().eq("scan_id", scan_id).eq("asset_key", k).execute()

    def notify(self, rows: list[dict]) -> list[dict]:
        return (self.db.table("user_notifications").insert(rows).execute().data or []) if rows else []

    def mark_emailed(self, note_id, when) -> None:
        self.db.table("user_notifications").update({"emailed_at": when.isoformat()}).eq("id", note_id).execute()

    def touch(self, scan_id, when) -> None:
        self.db.table("prism_scans").update({"last_run_at": when.isoformat()}).eq("id", scan_id).execute()

    def clear_quiet(self, scan_id) -> None:
        self.db.table("prism_scans").update({"quiet_next": False}).eq("id", scan_id).execute()

    def mark_digested(self, note_ids, when) -> None:
        if note_ids:
            self.db.table("user_notifications").update({"digested_at": when.isoformat()}).in_("id", note_ids).execute()

    def expire_and_prune(self, now) -> None:
        (self.db.table("prism_scan_runs").update({"status": "failed", "error": "stopped before finishing"})
         .eq("status", "running").lt("started_at", (now - STALE_CLAIM).isoformat()).execute())
        self.db.table("prism_scan_runs").delete().lt("cutoff", (now - timedelta(days=KEEP_DAYS)).isoformat()).execute()


# ----------------------------------------------------------------------------------------------- worker

def _assets(watchlist: tuple[dict, dict], market: str) -> list[tuple[str, str, str]]:
    crypto, stocks = watchlist
    if market == "crypto":
        return [("crypto", str(k), str(v)) for k, v in crypto.items()]
    return [("equity", str(k).upper(), f"{v} ({str(k).upper()})") for k, v in stocks.items()]


def scan_assets(scan: dict, watchlist: tuple[dict, dict], market: str) -> list[tuple[str, str, str]]:
    """The scan's assets in one market: Watchlist groups as the Watchlist is now, plus fixed assets."""
    crypto, stocks = watchlist
    out: dict[str, tuple[str, str, str]] = {}
    for item in scan.get("assets") or [{"group": "watchlist"}]:
        group, kind, aid = item.get("group"), item.get("kind"), str(item.get("id") or "")
        if market == "crypto" and group in ("watchlist", "crypto"):
            out.update({f"crypto:{a[1]}": a for a in _assets(watchlist, "crypto")})
        elif market == "equity" and group in ("watchlist", "shares"):
            out.update({f"equity:{a[1]}": a for a in _assets(watchlist, "equity")})
        elif market == "crypto" and kind == "crypto" and aid:
            out.setdefault(f"crypto:{aid}", ("crypto", aid, str(crypto.get(aid) or aid.replace("-", " ").title())))
        elif market == "equity" and kind == "equity" and aid:
            t = aid.upper()
            name = stocks.get(t) or stocks.get(aid)
            out.setdefault(f"equity:{t}", ("equity", t, f"{name} ({t})" if name else t))
    return list(out.values())


def due_items(scans: list[dict], watchlists: dict, now) -> list[tuple]:
    """(cutoff, scan, market, assets) for every scheduled scan and market with assets, oldest cutoff first."""
    items = []
    for scan in scans:
        if validate_schedule(scan.get("schedule")) or (scan.get("schedule") or {}).get("kind") == "manual":
            continue
        if scan.get("builtin"):            # the built-in alerts run on stored bars (builtin_alerts.py)
            continue
        for market in MARKETS:
            assets = scan_assets(scan, watchlists.get(scan["owner_id"], ({}, {})), market)
            if not assets:
                continue
            try:
                cutoff = latest_cutoff(scan["schedule"], market, now)
            except ValueError:
                continue
            items.append((cutoff, scan, market, assets))
    return sorted(items, key=lambda i: (i[0], str(i[1].get("last_run_at") or ""), str(i[1]["id"])))


def default_evaluate(supabase):
    """Point-in-time evaluation at T for one scan and market (one replay step for every asset)."""
    def evaluate(doc, assets, cutoff):
        from signal_library.replay_display import display_run

        run = display_run(supabase, max_steps=prism.steps_needed(doc), shortcut=True)
        rows = prism.run_now(doc, assets, live_context=None, replay=(run, cutoff))
        return rows, run.record()
    return evaluate


def run_due_scans(store, *, watchlists: dict, prefs: dict, evaluate, now=None, budget_seconds=BUDGET_SECONDS,
                  send_email=None, email_of=None, log=print, clock=time.monotonic) -> dict:
    """Run every due scan that fits in the budget. watchlists: owner -> (crypto {id: name}, stocks {ticker: name});
    prefs: owner -> alert preferences row; evaluate(doc, assets, cutoff) -> (rows, record)."""
    now = _ts(now or datetime.now(timezone.utc))
    started = clock()
    summary = {"ran": 0, "skipped_claimed": 0, "failed": 0, "waiting": 0, "notified": 0}
    try:
        store.expire_and_prune(now)
    except Exception as exc:
        log(f"Prism: housekeeping skipped: {str(exc)[:160]}")
    items = due_items(store.active_scans(), watchlists, now)
    for n, (cutoff, scan, market, assets) in enumerate(items):
        if clock() - started > budget_seconds:
            summary["waiting"] = len(items) - n
            log(f"Prism: {summary['waiting']} scan runs wait for the next pass (time budget used).")
            break
        run_id = store.claim(scan["id"], market, cutoff, now)
        if run_id is None:
            summary["skipped_claimed"] += 1
            continue
        due_at = cutoff + (SETTLE if scan["schedule"]["kind"] == "close" else timedelta(0))
        late = max(0, int((now - due_at).total_seconds()))
        try:
            rows, record = evaluate(scan["set_body"], assets, cutoff)
            answers = {f"{r['kind']}:{r['id']}": r["answer"] for r in rows}
            latched = store.latches(scan["id"])
            opens, releases, notify = plan_alerts(answers, latched, scan.get("alert_mode") or "change")
            if scan.get("rearm"):          # re-arm only when the re-arm Set says Yes, not on any No
                again, _ = evaluate(scan["rearm"], [a for a in assets if f"{a[0]}:{a[1]}" in latched], cutoff)
                releases = [f"{r['kind']}:{r['id']}" for r in again if r["answer"] == "yes"]
            store.open_latches(scan["id"], opens, cutoff)
            store.release_latches(scan["id"], releases)
            by_key = {f"{r['kind']}:{r['id']}": r for r in rows}
            settings = alert_settings(scan)
            quiet = bool(scan.get("quiet_next")) or settings["channel"] == "off"
            muted = snoozed(scan, now)
            notes = []
            if not quiet:
                if settings["on_yes"]:
                    notes += [_note(scan, by_key[k], False) for k in notify if k not in muted]
                if settings["on_no"]:
                    notes += [_note(scan, by_key[k], True) for k in releases if k not in muted]
                unknown = sum(r["answer"] == "unknown" for r in rows)
                if settings["on_fail"] and rows and unknown / len(rows) >= UNKNOWN_SHARE:
                    notes.append(_fail_note(scan, f"{unknown} of {len(rows)} answers were Unknown (missing data)."))
            inserted = store.notify(notes)
            summary["notified"] += len(inserted)
            _deliver(store, scan, settings, inserted, prefs.get(scan["owner_id"]) or {}, send_email, email_of, now,
                     log)
            if scan.get("quiet_next"):
                store.clear_quiet(scan["id"])
            store.finish(run_id, {
                "status": "ok", "finished_at": datetime.now(timezone.utc).isoformat(), "late_seconds": late,
                "results": [{k: r[k] for k in ("kind", "id", "asset", "answer", "how_sure", "reason", "available",
                                               "armed") if k in r} for r in rows],
                "opened": opens, "released": releases, "record": record, "set_version": scan.get("set_version")})
            store.touch(scan["id"], now)
            summary["ran"] += 1
        except Exception as exc:          # this scan only; never counted as an answer
            summary["failed"] += 1
            log(f"Prism: scan {scan['id']} ({market}) failed: {str(exc)[:200]}")
            try:
                store.finish(run_id, {"status": "failed", "error": str(exc)[:500], "late_seconds": late,
                                      "finished_at": datetime.now(timezone.utc).isoformat()})
                settings = alert_settings(scan)
                if settings["on_fail"] and settings["channel"] != "off":
                    inserted = store.notify([_fail_note(scan, f"The run failed: {str(exc)[:160]}")])
                    _deliver(store, scan, settings, inserted, prefs.get(scan["owner_id"]) or {}, send_email,
                             email_of, now, log)
            except Exception:
                pass
    return summary


def _note(scan: dict, row: dict, ended: bool) -> dict:
    return {"user_id": scan["owner_id"], "asset_symbol": row["id"], "asset_name": row["asset"],
            "alert_type": ALERT_TYPE, "message": message(scan["name"], row, ended)}


def _fail_note(scan: dict, why: str) -> dict:
    return {"user_id": scan["owner_id"], "asset_symbol": None, "asset_name": scan["name"], "alert_type": ALERT_TYPE,
            "message": f"Prism: “{scan['name']}” could not run properly. {why}"[:500]}


def _deliver(store, scan, settings, notes, pref, send_email, email_of, now, log) -> None:
    """instant: email now, keep out of the digest; digest: leave for the daily digest; app: keep out of the digest.
    Scans saved before stage 7 follow the account's instant setting, as before."""
    if not notes:
        return
    channel = settings["channel"]
    if channel == "account":
        _instant_emails(store, scan, notes, pref, send_email, email_of, now, log)
        return
    if channel == "instant":
        _instant_emails(store, {**scan, "notify": {"email": True}}, notes, {"instant_email": True}, send_email,
                        email_of, now, log)
    if channel in ("instant", "app"):
        try:
            store.mark_digested([n["id"] for n in notes if n.get("id") is not None], now)
        except Exception as exc:
            log(f"Prism: could not keep notes out of the digest: {str(exc)[:120]}")


def _instant_emails(store, scan, notes, pref, send_email, email_of, now, log) -> None:
    if not notes or not send_email or not email_of or not (scan.get("notify") or {}).get("email", True):
        return
    if not pref.get("instant_email"):
        return                            # the daily digest picks them up
    to = email_of(scan["owner_id"])
    if not to:
        return
    for note in notes:
        try:
            if send_email(to, note["asset_name"], note["message"]):
                store.mark_emailed(note["id"], now)
        except Exception as exc:
            log(f"Prism: email for {note.get('asset_name')} failed: {str(exc)[:120]}")


def run_from_worker(supabase, user_prefs: list[dict], alert_rows: dict, send_email, email_of, log=print) -> dict:
    """Entry point for run_alerts.py, called after the existing alert and digest work."""
    watchlists = {}
    for p in user_prefs:
        crypto = p.get("crypto_watchlist") if isinstance(p.get("crypto_watchlist"), dict) else {}
        stocks = p.get("stock_watchlist") if isinstance(p.get("stock_watchlist"), dict) else {}
        watchlists[p["user_id"]] = (crypto, stocks)
    store = SupabaseStore(supabase)
    try:
        return run_due_scans(store, watchlists=watchlists, prefs=alert_rows, evaluate=default_evaluate(supabase),
                             send_email=send_email, email_of=email_of, log=log)
    except Exception as exc:
        text = str(exc)
        if "prism_scans" in text and ("does not exist" in text or "relation" in text or "PGRST" in text):
            return {"skipped": "Prism tables not installed (sql/2026-11-06_prism_scans.sql)"}
        raise


def latest_runs(supabase, scan_id) -> list[dict]:
    """Newest run per market for one scan (the owner reads these through row-level security)."""
    rows = (supabase.table("prism_scan_runs").select("*").eq("scan_id", scan_id)
            .order("cutoff", desc=True).limit(10).execute().data or [])
    out, seen = [], set()
    for r in rows:
        if r["market"] not in seen:
            seen.add(r["market"])
            out.append(r)
    return out


def group_results(runs: list[dict], latched_since: dict | None = None) -> dict:
    """Results of the latest runs grouped for the page: new_yes, still_yes, unknown, no, failed."""
    out = {"new_yes": [], "still_yes": [], "unknown": [], "no": [], "failed": []}
    for run in runs:
        if run.get("status") != "ok":
            out["failed"].append(run)
            continue
        opened = set(run.get("opened") or [])
        for r in run.get("results") or []:
            key = f"{r['kind']}:{r['id']}"
            bucket = {"yes": "new_yes" if key in opened else "still_yes", "no": "no"}.get(r["answer"], "unknown")
            out[bucket].append({**r, "cutoff": run["cutoff"]})
    return out
