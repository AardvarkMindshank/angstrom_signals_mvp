"""
The Trend, Stretch and Flow alerts as built-in Prism scans (docs/design/prism_builtin_alerts.md).

Every account has six: Trend, Stretch and Flow, each turning up and turning down. Each is a Prism scan whose Set is
the starter Group with the account's line ("Trend score is at least +50"), with a re-arm rule 20 points back
("Trend score is at most +30"), on the whole Watchlist, at each daily close. They are worked out on the stored daily
bars, exactly as the dashboard reads them, and alert in the same words as before.

The account's alert settings (Notifications → Configure Alert Rules) decide the line and whether each is on; the
worker keeps the six scans in step with them (sync). An alert that is off doesn't run. Switching one on records the
current answers quietly first, so it never sends a burst for assets that didn't just cross.

Nothing here runs between closes: a scan runs once per market per close (claimed in prism_scan_runs), and the
readings are worked out once per asset per pass, shared by every account.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

import alerts as al
import signal_groups as sg

READINGS = {"trend": "starter:trend", "stretch": "starter:stretch", "flow": "starter:flow"}
# builtin key -> (reading, direction, alert type)
BUILTINS = {
    "trend_up": ("trend", 1, al.TREND_UP), "trend_down": ("trend", -1, al.TREND_DOWN),
    "stretch_up": ("stretch", 1, al.STRETCH_UP), "stretch_down": ("stretch", -1, al.STRETCH_DOWN),
    "flow_up": ("flow", 1, al.FLOW_UP), "flow_down": ("flow", -1, al.FLOW_DOWN),
}
TITLES = {"trend": "Trend", "stretch": "Stretch", "flow": "Flow"}
SCHEDULE = {"kind": "close", "timeframe": "1D"}
ASSETS = [{"group": "watchlist"}]
MARKETS = ("crypto", "equity")
WAIT_FOR_BARS = timedelta(hours=2)     # after this, a close runs with whatever bars have arrived


def name(builtin: str) -> str:
    reading, direction, _ = BUILTINS[builtin]
    return f"{TITLES[reading]} turns {'up' if direction > 0 else 'down'}"


def rearm_level(line: float) -> float:
    """Where an alert re-arms: 20 points back through the line, never past the opposite line (as before)."""
    return max(line - al.READING_REARM, -line)


# ----------------------------------------------------------------------------------------------- the Sets

def _choices() -> dict:
    import lattice_sets as ls

    configs = [{"id": alias, "kind": "group", "name": TITLES[r], "owner_id": "system", "starter_alias": alias,
                "versions": [{"version": 1, "body": sg.starter(alias)}]} for r, alias in READINGS.items()]
    return ls.group_choices(configs, "system")


def _set(title: str, purpose: str, reading: str, op: str, value: float) -> dict:
    import lattice_sets as ls

    choices = _choices()
    model = {"name": title, "purpose": purpose,
             "groups": [{"key": reading, "source": f"saved:{READINGS[reading]}:1"}], "standalone": [],
             "lines": [{"target": "score", "group": reading, "op": op, "value": f"{value:+.0f}"}]}
    return ls.to_document(ls.clean_model(model, choices), choices)


def set_doc(builtin: str, line: float) -> dict:
    """Yes when the reading is past the line: "Trend score is at least +50" (up) or "at most -50" (down)."""
    reading, direction, _ = BUILTINS[builtin]
    level = abs(line)
    return _set(name(builtin), f"Alerts when {TITLES[reading]} reaches {direction * level:+.0f}.", reading,
                "gte" if direction > 0 else "lte", direction * level)


def rearm_doc(builtin: str, line: float) -> dict:
    """Yes once the reading is back 20 points: then the next crossing can alert again."""
    reading, direction, _ = BUILTINS[builtin]
    back = rearm_level(abs(line))
    return _set(f"{name(builtin)}: re-arm", f"Re-arms when {TITLES[reading]} is back at {direction * back:+.0f}.",
                reading, "lte" if direction > 0 else "gte", direction * back)


def wanted(alert_config: dict) -> dict:
    """builtin -> (line, on) from the account's alert settings."""
    out = {}
    for builtin, (reading, _, _) in BUILTINS.items():
        out[builtin] = (al.reading_alert_level(alert_config, reading), al.reading_alert_on(alert_config, reading))
    return out


def scan_row(owner, builtin: str, line: float, on: bool) -> dict:
    return {"owner_id": owner, "builtin": builtin, "name": name(builtin), "set_body": set_doc(builtin, line),
            "rearm": rearm_doc(builtin, line), "set_source": {"builtin": builtin, "line": line},
            "schedule": SCHEDULE, "assets": ASSETS, "paused": False, "quiet_next": True,
            "notify": {"channel": "account" if on else "off", "on_yes": True, "on_no": False, "on_fail": False}}


def plan_sync(owner, existing: dict, alert_config: dict) -> tuple[list, list]:
    """(rows to create, (id, changes) to update) so the account's six built-in scans match its alert settings.
    existing: builtin -> scan row. A line change re-writes the Sets; switching on records quietly first."""
    creates, updates = [], []
    for builtin, (line, on) in wanted(alert_config).items():
        scan = existing.get(builtin)
        if scan is None:
            creates.append(scan_row(owner, builtin, line, on))
            continue
        changes = {}
        if float((scan.get("set_source") or {}).get("line") or -1) != float(line):
            changes.update(set_body=set_doc(builtin, line), rearm=rearm_doc(builtin, line),
                           set_source={"builtin": builtin, "line": line},
                           set_version=int(scan.get("set_version") or 1) + 1)
        channel = (scan.get("notify") or {}).get("channel")
        if (channel == "off") == on:
            changes["notify"] = {**(scan.get("notify") or {}), "channel": "account" if on else "off"}
            if on:
                changes["quiet_next"] = True
        if changes:
            updates.append((scan["id"], changes))
    return creates, updates


def seed_latches(scan_rows: list[dict], notification_rows: list[dict], stocks: dict) -> list[dict]:
    """Latches for new built-in scans from the alerts already open (or cleared but still latched) on the account,
    so the switch-over never repeats an alert. Old rows name the asset in lower case; shares are matched to the
    Watchlist's tickers."""
    tickers = {str(t).lower(): str(t).upper() for t in stocks}
    by_type = {}
    for row in notification_rows:
        kind = al.canonical_alert(row.get("alert_type"))
        symbol = al.latch_symbol(row.get("asset_symbol"))
        if not symbol or symbol.startswith("signals:") or al.is_market_symbol(symbol):
            continue
        key = f"equity:{tickers[symbol]}" if symbol in tickers else f"crypto:{symbol}"
        by_type.setdefault(kind, set()).add(key)
    out = []
    for scan in scan_rows:
        alert_type = BUILTINS[scan["builtin"]][2]
        out += [{"scan_id": scan["id"], "asset_key": k} for k in sorted(by_type.get(alert_type, ()))]
    return out


# ----------------------------------------------------------------------------------------------- running

class Readings:
    """Each asset's stored daily bars, turned into an engine context once per pass and shared by every account."""

    def __init__(self, frame_of):
        self.frame_of = frame_of          # (kind "crypto" | "equity", id) -> stored frame or None
        self._ctx: dict = {}

    def context(self, kind: str, asset_id: str):
        key = (kind, asset_id)
        if key not in self._ctx:
            self._ctx[key] = None
            frame = self.frame_of(kind, asset_id)
            if frame is not None and not frame.empty and len(frame) >= 15:
                from group_readings import stored_context
                from scoring import calculate_indicators

                try:
                    self._ctx[key] = stored_context(calculate_indicators(frame), kind, asset_id=asset_id)
                except Exception as exc:
                    print(f"Built-in alerts: could not read {kind}:{asset_id}: {str(exc)[:120]}")
        return self._ctx[key]


def bars_ready(last_bar: pd.Timestamp, market: str, cutoff: pd.Timestamp) -> bool:
    """Has the daily bar that closed at `cutoff` arrived? Crypto's daily bar for day D closes at 00:00 UTC on
    D+1; a share's bar for day D closes at 16:00 New York on day D."""
    last = pd.Timestamp(last_bar)
    last = last.tz_localize("UTC") if last.tzinfo is None else last.tz_convert("UTC")
    if market == "crypto":
        return last.date() >= (cutoff - pd.Timedelta(days=1)).tz_convert("UTC").date()
    return last.date() >= cutoff.tz_convert("America/New_York").date()


def evaluate(doc: dict, rearm: dict | None, builtin: str, assets, readings: Readings) -> list[dict]:
    """Per asset: answer to the scan's Set, the re-arm answer, the reading's value (-100..+100) and the reason."""
    import prism

    reading = BUILTINS[builtin][0]
    group = sg.starter(READINGS[reading])
    rows = []
    for kind, asset_id, label in assets:
        got = readings.context(kind, asset_id)
        if got is None:
            rows.append({"kind": kind, "id": asset_id, "asset": label, "answer": "unknown", "rearm": None,
                         "value": None, "reason": "No stored daily bars yet.", "how_sure": "—", "available": "None"})
            continue
        ctx, _ = got
        result = sg.evaluate_set(doc, ctx)
        row = prism.row(label, result, "Stored daily bars (as the dashboard)")
        again = prism.row(label, sg.evaluate_set(rearm, ctx), "") if rearm else None
        value = (sg.evaluate_group(group, ctx).get("score") or {}).get("value")
        rows.append({**row, "kind": kind, "id": asset_id, "rearm": again["answer"] if again else None,
                     "value": None if value is None else value * 100})
    return rows


def plan(rows: list[dict], latched: set) -> tuple[list, list]:
    """(open, release) asset keys: a Yes opens once; the re-arm Set's Yes (or, without one, a No) releases."""
    opens, releases = [], []
    for r in rows:
        key = f"{r['kind']}:{r['id']}"
        if r["answer"] == "yes" and key not in latched:
            opens.append(key)
        elif key in latched and (r["rearm"] == "yes" if r.get("rearm") is not None else r["answer"] == "no"):
            releases.append(key)
    return opens, releases


def note(owner, builtin: str, row: dict, channel: str, now_iso: str) -> dict:
    """The alert in the same words, type and asset naming as before, so the feed, emails and digest are unchanged.
    app: never emailed or digested; digest: not emailed now; instant and account: left for the email step."""
    alert_type = BUILTINS[builtin][2]
    out = {"user_id": owner, "asset_symbol": al.latch_symbol(row["id"]), "asset_name": row["asset"],
           "alert_type": alert_type, "message": al.reading_message(row["value"] or 0.0, alert_type)}
    if channel in ("app", "digest"):
        out["emailed_at"] = now_iso
    if channel == "app":
        out["digested_at"] = now_iso
    return out


def run_account(db, owner, scans: list[dict], watchlist: tuple[dict, dict], readings: Readings, *, now=None,
                log=print) -> dict:
    """Run this account's due built-in scans. db: the scan store (prism_scans.SupabaseStore) plus .notes and
    .resolve. Returns {"ran", "opened", "notes": [inserted rows], "instant": bool}."""
    import prism_scans as ps

    now = ps._ts(now or datetime.now(timezone.utc))
    out = {"ran": 0, "opened": 0, "notes": [], "instant": False}
    for scan in scans:
        builtin = scan.get("builtin")
        channel = (scan.get("notify") or {}).get("channel") or "account"
        if builtin not in BUILTINS or channel == "off":
            continue
        for market in MARKETS:
            assets = ps.scan_assets(scan, watchlist, market)
            if not assets:
                continue
            cutoff = ps.latest_cutoff(SCHEDULE, market, now)
            if now < cutoff + ps.SETTLE:
                continue
            lasts = [g[1] for g in (readings.context(k, i) for k, i, _ in assets) if g is not None]
            if now < cutoff + WAIT_FOR_BARS and (not lasts or not all(bars_ready(t, market, cutoff) for t in lasts)):
                continue                       # the closed bar hasn't reached the stored prices yet
            run_id = db.claim(scan["id"], market, cutoff, now)
            if run_id is None:
                continue
            try:
                rows = evaluate(scan["set_body"], scan.get("rearm"), builtin, assets, readings)
                latched = db.latches(scan["id"])
                opens, releases = plan(rows, latched)
                db.open_latches(scan["id"], opens, cutoff)
                db.release_latches(scan["id"], releases)
                if releases:
                    db.resolve(owner, BUILTINS[builtin][2], [k.split(":", 1)[1] for k in releases])
                quiet = bool(scan.get("quiet_next"))
                muted = ps.snoozed(scan, now)
                by_key = {f"{r['kind']}:{r['id']}": r for r in rows}
                fresh = [] if quiet else [note(owner, builtin, by_key[k], channel, now.isoformat())
                                          for k in opens if k not in muted]
                inserted = db.notes(fresh)
                out["notes"] += inserted
                out["opened"] += len(opens)
                out["instant"] = out["instant"] or (channel == "instant" and bool(inserted))
                if quiet:
                    db.clear_quiet(scan["id"])
                    scan["quiet_next"] = False
                db.finish(run_id, {
                    "status": "ok", "finished_at": datetime.now(timezone.utc).isoformat(),
                    "late_seconds": max(0, int((now - cutoff - ps.SETTLE).total_seconds())),
                    "results": [{k: r[k] for k in ("kind", "id", "asset", "answer", "how_sure", "reason", "available")}
                                for r in rows],
                    "opened": opens, "released": releases, "set_version": scan.get("set_version"),
                    "record": {"source": "stored daily bars", "builtin": builtin, "quiet": quiet}})
                db.touch(scan["id"], now)
                out["ran"] += 1
            except Exception as exc:
                log(f"Built-in alert {builtin} ({market}) for {owner} failed: {str(exc)[:200]}")
                try:
                    db.finish(run_id, {"status": "failed", "error": str(exc)[:500],
                                       "finished_at": datetime.now(timezone.utc).isoformat()})
                except Exception:
                    pass
    return out


class Store:
    """The Prism scan store plus the alert rows the built-in scans write."""

    def __init__(self, supabase):
        import prism_scans as ps

        self.db = supabase
        self.scans = ps.SupabaseStore(supabase)

    def __getattr__(self, attr):
        return getattr(self.scans, attr)

    def notes(self, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        try:
            return self.db.table("user_notifications").insert(rows).execute().data or []
        except Exception:                 # a database without the digest column
            return self.db.table("user_notifications").insert(
                [{k: v for k, v in r.items() if k != "digested_at"} for r in rows]).execute().data or []

    def resolve(self, owner, alert_type: str, asset_ids: list[str]) -> None:
        """Re-armed: the feed stops showing the old crossing, as before."""
        for asset_id in asset_ids:
            (self.db.table("user_notifications").update({"alert_type": f"{alert_type}_resolved"})
             .eq("user_id", owner).eq("asset_symbol", al.latch_symbol(asset_id))
             .in_("alert_type", al.stored_types(alert_type)).execute())

    def builtin_scans(self) -> dict:
        rows = (self.db.table("prism_scans").select("*").not_.is_("builtin", "null").execute().data or [])
        out: dict = {}
        for r in rows:
            out.setdefault(r["owner_id"], {})[r["builtin"]] = r
        return out

    def sync(self, owner, existing: dict, alert_config: dict, stocks: dict) -> dict:
        """Create or update the account's six built-in scans; seed new ones' latches. Returns builtin -> scan."""
        creates, updates = plan_sync(owner, existing, alert_config)
        for scan_id, changes in updates:
            self.db.table("prism_scans").update(changes).eq("id", scan_id).execute()
            for row in existing.values():
                if row["id"] == scan_id:
                    row.update(changes)
        if creates:
            made = self.db.table("prism_scans").insert(creates).execute().data or []
            old = (self.db.table("user_notifications").select("asset_symbol, alert_type").eq("user_id", owner)
                   .in_("alert_type", al.LATCH_TYPES).execute().data or [])
            seeds = seed_latches(made, old, stocks)
            if seeds:
                self.db.table("prism_scan_latches").upsert(seeds).execute()
            for row in made:
                existing[row["builtin"]] = row
        return existing

