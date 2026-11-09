"""
Prism Scans board: the data behind the 🔎 Prism Scan page (build stage 7, docs/design/lattice_stage7_report.md).

Pure functions, no Streamlit and no database: what each saved scan shows (summary row and details), what the
library lists hold (saved Sets, Watchlist), and how a button press becomes a new scan object for
`prism_put_scan` (sql/2026-11-08_prism_scan_objects.sql). The page (prism_view.py) reads and writes; the JS board
(prism_component.py) draws.
"""

from __future__ import annotations

import copy
from datetime import timedelta

import pandas as pd

import perspectives
import prism
import prism_scans as ps
import signal_groups as sg

MAX_SCHEDULED = ps.MAX_ACTIVE_SCANS
MAX_ASSET_ITEMS = 60
SNOOZE_DAYS = (1, 3, 7)
GROUPS = {"watchlist": "Whole Watchlist", "crypto": "All crypto", "shares": "All equities"}   # "shares" is the stored id; "equities" is the word used across the app
CHANNELS = {"instant": "Instant (app and email)", "digest": "Daily digest", "app": "App only", "off": "Off",
            "account": "As my alert settings"}
RUNS = {"manual": "Only when I press Play", "4H": "Each 4-hour close", "1D": "Each daily close",
        "1W": "Each weekly close", "times": "At set times"}
ZONES = ["Asia/Bangkok", "UTC", "Europe/London", "Europe/Berlin", "America/New_York", "America/Los_Angeles",
         "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney"]
DOT = {"yes": "yes", "no": "no", "unknown": "unknown", "failed": "failed"}


# ----------------------------------------------------------------------------------------------- library lists

def set_choices(saved: list[dict], user_id: str) -> dict[str, dict]:
    """Every scannable Set the account can read: the demo Sets and the newest scannable version of each saved Set.
    key -> {name, meta, doc, config, version, latest}."""
    out = {}
    for key, doc in prism.demo_sets().items():
        out[key] = {"name": doc["name"], "meta": "example Set", "doc": doc, "config": None, "version": None,
                    "provided": True}
    for c in saved:
        if c.get("kind") != "set":
            continue
        usable = [v for v in c.get("versions") or [] if sg.scannable(v.get("body") or {})]
        if not usable:
            continue
        v = max(usable, key=lambda v: v["version"])
        owner = "yours" if c.get("owner_id") == user_id else "shared"
        doc = v["body"]
        parts = len(doc.get("groups") or []) + len(doc.get("standalone") or [])
        out[f"saved:{c['id']}:{v['version']}"] = {
            "name": c["name"], "meta": f"v{v['version']} · {parts} part{'s' * (parts != 1)} · {owner}", "doc": doc,
            "config": c["id"], "version": v["version"]}
    return out


def latest_by_config(choices: dict) -> dict:
    return {c["config"]: (k, c) for k, c in choices.items() if c.get("config")}


def watchlist(assets: list[tuple[str, str, str]]) -> tuple[dict, dict]:
    """(crypto {id: name}, stocks {ticker: name}) from the page's asset list."""
    crypto = {aid: name for kind, aid, name in assets if kind == "crypto"}
    stocks = {aid.upper(): (name[: -len(f" ({aid})")] if name.endswith(f" ({aid})") else name)
              for kind, aid, name in assets if kind != "crypto"}
    return crypto, stocks


def _set_entry(key: str, c: dict) -> dict:
    """One library chip: name, the perspectives it looks at, a one-line description, and for provided Sets the
    "more…" explanation and evidence status (perspectives.py)."""
    doc = c.get("doc") or {}
    more = perspectives.explain(key) if c.get("provided") else None
    line = more["line"] if more else str(doc.get("purpose") or "")
    icon, words = perspectives.evidence(doc, key)
    return {"key": key, "name": c["name"], "meta": c["meta"], "provided": bool(c.get("provided")),
            "icons": perspectives.chips(doc), "line": line,
            "more": ({k: more[k] for k in ("measures", "why", "not_proven")} if more else None),
            "followed": perspectives.followed_card(doc, key),
            "evidence": {"icon": icon, "hover": words},
            "inside": _inside(doc),
            # Provided Sets open in Signal Sets as your own copy; yours open as they are.
            "open": "copy" if c.get("provided") else ("open" if c.get("config") and "yours" in c.get("meta", "") else None)}


def _inside(doc: dict) -> dict | None:
    import set_inside

    try:
        return set_inside.parts(doc)
    except Exception:
        return None


def library(choices: dict, assets: list[tuple[str, str, str]]) -> dict:
    crypto, stocks = watchlist(assets)
    return {
        "sets": [_set_entry(k, c) for k, c in choices.items()],
        "perspectives": [{"key": k, "icon": i, "hover": h} for k, i, h in perspectives.ICONS],
        "groups": [{"group": "watchlist", "name": GROUPS["watchlist"], "count": len(crypto) + len(stocks)},
                   {"group": "crypto", "name": GROUPS["crypto"], "count": len(crypto)},
                   {"group": "shares", "name": GROUPS["shares"], "count": len(stocks)}],
        "assets": [{"kind": "crypto" if kind == "crypto" else "equity", "id": aid, "name": name,
                    "market": "crypto" if kind == "crypto" else "equity"} for kind, aid, name in assets],
    }


# ----------------------------------------------------------------------------------------------- one scan

def scan_object(scan: dict) -> dict:
    """The writable part of a stored scan, as prism_put_scan takes it."""
    notify = scan.get("notify") or {}
    if "channel" not in notify:
        notify = {"channel": "account", "on_yes": True, "on_no": False, "on_fail": False, "email": notify.get("email", True)}
    return {"name": scan["name"], "set": scan["set_body"], "source": scan.get("set_source") or {},
            "schedule": scan.get("schedule") or {"kind": "manual"}, "notify": notify,
            "assets": scan.get("assets") or [{"group": "watchlist"}], "snoozes": scan.get("snoozes") or {},
            "paused": bool(scan.get("paused"))}


def for_database(obj: dict) -> dict:
    """"account" is how older scans are shown; saving any change turns it into an explicit Instant choice."""
    out = copy.deepcopy(obj)
    if out["notify"].get("channel") == "account":
        out["notify"] = {"channel": "instant" if out["notify"].get("email", True) else "app",
                         "on_yes": True, "on_no": False, "on_fail": False}
    out["notify"].pop("email", None)
    return out


def new_scan(choice_key: str, choices: dict) -> dict:
    c = choices[choice_key]
    return {"name": c["name"][:80], "set": c["doc"],
            "source": {"key": choice_key, "name": c["name"], "config": c.get("config"), "version": c.get("version")},
            "schedule": {"kind": "manual"}, "notify": {"channel": "instant", "on_yes": True, "on_no": False,
                                                       "on_fail": False},
            "assets": [{"group": "watchlist"}], "snoozes": {}, "paused": False}


def asset_label(item: dict, names: dict) -> str:
    if item.get("group"):
        return GROUPS.get(item["group"], item["group"])
    key = f"{item.get('kind')}:{item.get('id')}"
    return names.get(key) or str(item.get("id"))


def add_asset(obj: dict, item: dict) -> tuple[dict, str | None]:
    out = copy.deepcopy(obj)
    clean = ({"group": item["group"]} if item.get("group") in GROUPS else
             {"kind": item.get("kind"), "id": str(item.get("id") or "")[:60]}
             if item.get("kind") in ("crypto", "equity") and item.get("id") else None)
    if clean is None:
        return obj, "That can't be added to a scan."
    if clean == {"group": "watchlist"}:
        out["assets"] = [clean]                       # covers everything else
        return out, None
    if clean in out["assets"]:
        return obj, None
    if out["assets"] == [{"group": "watchlist"}]:
        # The whole Watchlist already covers it, so adding one asset or group means narrowing the scan to it.
        out["assets"] = [clean]
        return out, None
    if len(out["assets"]) >= MAX_ASSET_ITEMS:
        return obj, f"A scan holds at most {MAX_ASSET_ITEMS} entries."
    out["assets"].append(clean)
    return out, None


def remove_asset(obj: dict, index: int) -> tuple[dict, str | None]:
    if len(obj["assets"]) <= 1:
        return obj, ("A scan needs at least one asset or group. To scan something else, drop it here (or tap + "
                     "beside it in the Watchlist list): it takes the place of this one.")
    out = copy.deepcopy(obj)
    if 0 <= index < len(out["assets"]):
        out["assets"].pop(index)
    return out, None


def scan_markets(obj: dict, assets: list[tuple[str, str, str]]) -> dict[str, list]:
    wl = watchlist(assets)
    return {m: ps.scan_assets({"assets": obj["assets"]}, wl, m) for m in ps.MARKETS}


def next_run(schedule: dict, markets: list[str], now) -> pd.Timestamp | None:
    """When the scan next runs (the next cutoff plus the settle time), or None for a manual scan."""
    if not schedule or schedule.get("kind") == "manual" or ps.validate_schedule(schedule) or not markets:
        return None
    now = pd.Timestamp(now)
    best = None
    for market in markets:
        try:
            current = ps.latest_cutoff(schedule, market, now)
        except ValueError:
            current = None
        step = pd.Timedelta(minutes=10)
        probe = now + step
        for _ in range(8 * 24 * 6):
            try:
                cut = ps.latest_cutoff(schedule, market, probe)
            except ValueError:
                cut = None
            if cut is not None and cut != current:
                due = cut + (ps.SETTLE if schedule["kind"] == "close" else timedelta(0))
                best = due if best is None or due < best else best
                break
            probe += step
    return best


def _until(when, now) -> str:
    mins = max(0, int((pd.Timestamp(when) - pd.Timestamp(now)).total_seconds() // 60))
    if mins < 60:
        return f"next in {mins} min"
    hours, mins = divmod(mins, 60)
    if hours < 48:
        return f"next in {hours}h {mins:02d}m"
    return f"next in {hours // 24} days"


def _ago(when, now) -> str:
    mins = max(0, int((pd.Timestamp(now) - pd.Timestamp(when)).total_seconds() // 60))
    if mins < 60:
        return f"{mins} min ago"
    if mins < 48 * 60:
        return f"{mins // 60} h ago"
    return f"{mins // 1440} days ago"


def run_dot(run: dict) -> str:
    if run.get("status") != "ok":
        return "failed"
    answers = [r.get("answer") for r in run.get("results") or []]
    if "yes" in answers:
        return "yes"
    if answers and answers.count("unknown") * 2 >= len(answers):
        return "unknown"
    return "no"


def view(scan: dict, runs: list[dict], latched: list[str], choices: dict, assets: list[tuple[str, str, str]],
         now, session_result: dict | None = None) -> dict:
    """Everything the board shows for one scan."""
    obj = scan_object(scan)
    names = {f"{'crypto' if k == 'crypto' else 'equity'}:{i if k == 'crypto' else i.upper()}": n for k, i, n in assets}
    markets = scan_markets(obj, assets)
    in_use = [m for m, a in markets.items() if a]
    sched = obj["schedule"]
    paused = obj["paused"]
    when = None if paused else next_run(sched, in_use, now)
    if sched.get("kind") == "manual":
        next_text = "runs when you press Play"
    elif paused:
        next_text = "paused"
    else:
        next_text = _until(when, now) if when is not None else "no assets to scan"

    runs = sorted(runs, key=lambda r: str(r.get("cutoff")), reverse=True)
    latest, seen = [], set()
    for r in runs:
        if r.get("market") not in seen:
            seen.add(r.get("market"))
            latest.append(r)
    counts = {"yes": 0, "no": 0, "unknown": 0}
    stored = []
    for r in latest:
        for row in r.get("results") or []:
            counts[row.get("answer") if row.get("answer") in counts else "unknown"] += 1
            stored.append(row)
    last_text = (f"Last scheduled run {_ago(runs[0]['cutoff'], now)}" if runs else "Not run on a schedule yet")

    source = obj["source"] or {}
    newer = latest_by_config(choices).get(source.get("config")) if source.get("config") else None
    update = None
    if newer and source.get("version") and newer[1]["version"] > source["version"]:
        update = {"key": newer[0], "version": newer[1]["version"]}

    snoozes = {k: str(v)[:10] for k, v in obj["snoozes"].items() if k in ps.snoozed(scan, now)}
    results, results_title = stored, (last_text if stored else "")
    if session_result:
        results, results_title = session_result["rows"], session_result["title"]
    order = {"yes": 0, "unknown": 1, "no": 2}
    results = sorted(results, key=lambda r: (order.get(r.get("answer"), 3), str(r.get("asset"))))
    notify = obj["notify"]
    return {
        "id": scan["id"], "name": obj["name"],
        "version": f"v{source['version']}" if source.get("version") else "example",
        "update": update, "paused": paused, "scheduled": sched.get("kind") != "manual",
        "schedule": sched, "schedule_text": ps.describe_schedule(sched), "next_text": next_text,
        "notify": {"channel": notify.get("channel", "instant"), "on_yes": notify.get("on_yes", True),
                   "on_no": bool(notify.get("on_no")), "on_fail": bool(notify.get("on_fail"))},
        "assets": [{"label": asset_label(a, names), "group": bool(a.get("group")),
                    "watchlist": a.get("group") == "watchlist"} for a in obj["assets"]],
        "asset_count": sum(len(v) for v in markets.values()),
        # 🔍 Look inside: the Set this scan runs (as saved in the scan), and how to open it in Signal Sets
        "inside": _inside(obj["set"]),
        "set_key": source.get("key") if source.get("key") in choices else None,
        "set_open": ("copy" if (choices.get(source.get("key")) or {}).get("provided") else "open")
        if source.get("key") in choices else None,
        "counts": counts, "dots": [run_dot(r) for r in reversed(runs[:10])], "last_text": last_text,
        "yes_now": [{"key": k, "name": names.get(k) or k.split(":", 1)[-1]} for k in sorted(latched)],
        "snoozes": [{"key": k, "name": names.get(k) or k.split(":", 1)[-1], "until": u} for k, u in snoozes.items()],
        "results_title": results_title,
        "results": [_result_row(r) for r in results[:prism.MAX_ASSETS * 2]],
        "evidence": dict(zip(("icon", "hover"), perspectives.evidence(obj["set"]))),
        "warning": ps.schedule_warning(sched, obj["set"]) if sched.get("kind") == "close" else None,
    }


def _result_row(r: dict) -> dict:
    """Asset, answer, deciding line, and the data-completeness mark (● complete, ◐ partial, ○ none)."""
    out = {"asset": r.get("asset"), "answer": r.get("answer"), "reason": r.get("reason")}
    if r.get("armed"):
        out["armed"] = r["armed"]
    if r.get("available"):
        icon, words = perspectives.data_mark(r["available"])
        detail = r.get("available_detail") or ""
        out["data"] = {"icon": icon, "hover": words + (f": {detail}" if detail and detail != "All readings available" else "")}
    return out


def scheduled_count(scans: list[dict]) -> int:
    return sum(1 for s in scans if not s.get("paused") and (s.get("schedule") or {}).get("kind") != "manual")


# ----------------------------------------------------------------------------------------------- settings from the board

def schedule_from(raw: dict) -> tuple[dict | None, str | None]:
    runs = raw.get("runs")
    if runs == "manual":
        return {"kind": "manual"}, None
    if runs in ("4H", "1D", "1W"):
        return {"kind": "close", "timeframe": runs}, None
    if runs == "times":
        times = [t.strip() for t in str(raw.get("times") or "").split(",") if t.strip()]
        days = raw.get("days") if raw.get("days") in ("all", "weekdays") else "all"
        tz = raw.get("tz") if raw.get("tz") in ZONES else "Asia/Bangkok"
        schedule = {"kind": "times", "times": times, "days": days, "tz": tz}
        errors = ps.validate_schedule(schedule)
        return (None, errors[0]) if errors else (schedule, None)
    return None, "Choose when the scan runs."


def notify_from(raw: dict) -> dict:
    channel = raw.get("channel") if raw.get("channel") in ("instant", "digest", "app", "off") else "instant"
    return {"channel": channel, "on_yes": raw.get("on_yes", True) is not False, "on_no": bool(raw.get("on_no")),
            "on_fail": bool(raw.get("on_fail"))}


def snooze(obj: dict, key: str, days: int, now) -> dict:
    out = copy.deepcopy(obj)
    if days in SNOOZE_DAYS and isinstance(key, str) and len(key) <= 80:
        out["snoozes"][key] = (pd.Timestamp(now) + pd.Timedelta(days=days)).isoformat()
    return out


def unsnooze(obj: dict, key: str) -> dict:
    out = copy.deepcopy(obj)
    out["snoozes"].pop(key, None)
    return out


def tidy_snoozes(obj: dict, now) -> dict:
    """Drop snoozes that have ended, so the stored object stays small."""
    out = copy.deepcopy(obj)
    out["snoozes"] = {k: v for k, v in out["snoozes"].items() if k in ps.snoozed({"snoozes": out["snoozes"]}, now)}
    return out


def unique_name(name: str, taken) -> str:
    """The name, or "name (2)", "name (3)" … when one of your scans already has it (any letter case)."""
    base = " ".join(str(name or "Scan").split())[:72]
    used = {" ".join(str(t or "").split()).casefold() for t in taken}
    if base.casefold() not in used:
        return base
    n = 2
    while f"{base} ({n})".casefold() in used:
        n += 1
    return f"{base} ({n})"


def duplicate(obj: dict, taken=()) -> dict:
    out = copy.deepcopy(obj)
    out["name"] = unique_name(out["name"], taken)
    out["schedule"] = {"kind": "manual"}            # a copy starts manual, so it never pushes past the limit
    out["snoozes"] = {}
    out["paused"] = False
    return out


def switch_set(obj: dict, key: str, choices: dict) -> dict:
    c = choices[key]
    out = copy.deepcopy(obj)
    out["set"] = c["doc"]
    out["source"] = {"key": key, "name": c["name"], "config": c.get("config"), "version": c.get("version")}
    return out
