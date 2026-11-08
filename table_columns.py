"""
Reading columns in the asset tables: which Signal Groups and Signal Sets each watchlist table shows.

The account chooses them (settings["table_columns"] = {"groups": [...], "sets": [...]}); the default is the
dashboard's Trend, Stretch and Flow. Each column is worked out per asset from the stored daily bars, the same bars
and engine Prism's built-in alerts use, so a column and a scan never disagree. Definitions that read 4-hour or
hourly candles answer Unknown here ("daily bars only"): the tables use the stored daily bars.

The table shows each kind in its own section ("Groups", "Sets") that folds sideways in the browser.

Keys: "starter:<alias>" for the starter Groups (the three dashboard readings draw as before), "saved:<config id>"
for your saved Groups and Sets (always their newest version).

Pure functions apart from the engine, so they can be tested anywhere.
"""

from __future__ import annotations

import hashlib
import html
import json

import signal_groups as sg

DEFAULT = {"groups": ["starter:trend", "starter:stretch", "starter:flow"], "sets": []}
CLUSTER_OF = {"starter:trend": "trend", "starter:stretch": "stretch", "starter:flow": "flow"}
MAX_EACH = 12
YES, NO, UNKNOWN = ("#15803d", "#dcfce7"), ("#6b7280", "#f3f4f6"), ("#b45309", "#fef3c7")


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def chosen(settings: dict | None) -> dict:
    """The account's columns, cleaned: known key shapes, no repeats, at most MAX_EACH of each."""
    raw = (settings or {}).get("table_columns")
    if not isinstance(raw, dict):
        return {k: list(v) for k, v in DEFAULT.items()}
    out = {}
    for part in ("groups", "sets"):
        keys, seen = [], set()
        for key in raw.get(part) or []:
            key = str(key)
            if key in seen or not (key.startswith("saved:") or (part == "groups" and key in starter_keys())
                                   or (part == "sets" and key in provided_sets())):
                continue
            seen.add(key)
            keys.append(key)
        out[part] = keys[:MAX_EACH]
    return out


def provided_sets() -> dict:
    """The provided Sets (prism.demo_sets): key -> document."""
    import prism

    return prism.demo_sets()


def starter_keys() -> list[str]:
    return list(sg.STARTERS)


def options(saved: list[dict], user_id: str) -> tuple[dict, dict]:
    """(groups, sets): key -> label for everything a column can show. Groups: the starters, then the account's own
    and shared ones; Sets: every readable Set with a decision."""
    import perspectives

    tag = lambda doc: (" " + perspectives.icons(doc)) if perspectives.icons(doc) else ""
    groups = {alias: f"{sg.starter(alias)['name']}{tag(sg.starter(alias))} (provided)" for alias in sg.STARTERS}
    sets = {key: f"{doc['name']}{tag(doc)} (provided)" for key, doc in provided_sets().items()
            if not doc["name"].endswith("(demo)")}
    for c in saved:
        if not c.get("versions") or c.get("starter_alias"):
            continue
        owner = "yours" if c.get("owner_id") == user_id else "shared"
        if c.get("kind") == "group":
            groups[f"saved:{c['id']}"] = f"{c['name']}{tag(c['versions'][-1].get('body'))} ({owner})"
        elif c.get("kind") == "set" and sg.scannable(c["versions"][-1].get("body") or {}):
            sets[f"saved:{c['id']}"] = f"{c['name']}{tag(c['versions'][-1].get('body'))} ({owner})"
    return groups, sets


def resolve(columns: dict, saved: list[dict]) -> list[dict]:
    """Column specs in table order (Groups, then Sets): {key, part, name, doc, cluster, config, version}.
    A saved Group or Set that is no longer readable is left out."""
    by_id = {c["id"]: c for c in saved if c.get("versions")}
    specs = []
    for part in ("groups", "sets"):
        for key in columns.get(part) or []:
            if key in CLUSTER_OF:
                specs.append({"key": key, "part": part, "name": sg.starter(key)["name"], "doc": None,
                              "cluster": CLUSTER_OF[key], "config": None, "version": None})
            elif part == "sets" and key in provided_sets():
                doc = provided_sets()[key]
                specs.append({"key": key, "part": part, "name": doc["name"], "doc": doc, "cluster": None,
                              "config": None, "version": None})
            elif key.startswith("starter:"):
                specs.append({"key": key, "part": part, "name": sg.starter(key)["name"], "doc": sg.starter(key),
                              "cluster": None, "config": None, "version": None})
            else:
                c = by_id.get(key.split(":", 1)[1])
                if not c or c.get("kind") != part[:-1]:
                    continue
                v = c["versions"][-1]
                specs.append({"key": key, "part": part, "name": c["name"], "doc": v["body"], "cluster": None,
                              "config": c["id"], "version": v["version"]})
    return specs


def fingerprint(specs: list[dict]) -> str:
    """Changes when any column's definition changes (a new version, a different choice)."""
    blob = json.dumps([[s["key"], s["version"], s["doc"]] for s in specs], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ----------------------------------------------------------------------------------------------- working out

def evaluate(specs: list[dict], ctx, subject_context=None, as_of: str = "") -> dict:
    """key -> cell values for one asset, for every column that is not one of the three dashboard readings.
    ctx: the asset's stored-bar context (group_readings.stored_context); subject_context(kind, id) gives another
    asset's, for a Set line pinned to a fixed asset."""
    import prism

    out = {}
    for spec in specs:
        if spec["cluster"] or spec["doc"] is None or not daily_only(spec["doc"]):
            continue                      # the dashboard readings draw themselves; other timeframes: column_answers
        try:
            if spec["part"] == "groups":
                result = sg.evaluate_group(spec["doc"], ctx)
                score = (result.get("score") or {}).get("value")
                outcome = result.get("outcome") or {}
                out[spec["key"]] = {"value": None if score is None else score * 100, "label": outcome.get("label"),
                                    "status": result.get("status"), "why": _group_why(result), "as_of": as_of}
            else:
                row = prism.row(spec["name"], sg.evaluate_set(spec["doc"], ctx, subject_context=subject_context), "")
                out[spec["key"]] = {"answer": row["answer"], "why": row.get("reason") or "", "as_of": as_of,
                                    "available": row.get("available")}
        except Exception as exc:          # one column never breaks the table
            out[spec["key"]] = {"error": str(exc)[:160]}
    return out


def _group_why(result: dict) -> str:
    members = result.get("members") or []
    missing = [m.get("key") for m in members if m.get("state") not in ("observed", None)]
    status = result.get("status")
    if status and status != "ok":
        return {"vetoed": "Vetoed by one of its rules.", "veto_unknown": "A veto could not be checked.",
                "insufficient": "Not enough data."}.get(status, str(status))
    return ("Missing: " + ", ".join(missing[:4])) if missing else ""


# ----------------------------------------------------------------------------------------------- cells

def header(spec: dict) -> str:
    kind = "Signal Group" if spec["part"] == "groups" else "Signal Set"
    tail = f" v{spec['version']}" if spec.get("version") else ""
    when = ("on the latest finished daily bar" if daily_only(spec.get("doc")) else
            "worked out in the background at each close of its shortest timeframe")
    return f"{spec['name']}{tail}: your {kind}, {when}. Click a cell to see why it reads that way."


def freshness(spec: dict, cell: dict, now=None) -> tuple[str, bool]:
    """("as of …" words, may be out of date?) for a cell. Daily columns are as of the last daily close and can't be
    newer until the next one; other timeframes say when they were worked out, and get ⏳ once a close has passed
    without a new answer."""
    import pandas as pd

    as_of = cell.get("as_of")
    if not as_of:
        return "", False
    if daily_only(spec.get("doc")):
        return f"as of the {as_of} daily close", False
    import column_answers as ca

    try:
        t = pd.Timestamp(as_of)
        t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    except (ValueError, TypeError):
        return "", False
    now = pd.Timestamp(now or pd.Timestamp.now(tz="UTC"))
    step = ca.cadence(spec["doc"])
    stale = now - t > pd.Timedelta(minutes=2 * step + 20)
    words = f"as of {t:%H:%M} UTC, {t:%-d %b} ({_tf_words(step)} close)"
    return words + (" · may be out of date: a newer close has passed" if stale else ""), stale


def _tf_words(minutes: int) -> str:
    return {60: "hourly", 240: "4-hour"}.get(minutes, "daily")


def waiting_cell(spec: dict, section: str) -> str:
    """A column whose timeframe isn't stored, before its first background answer arrives."""
    tip = (f"{spec['name']}: reads {', '.join(sorted(set(_timeframes(spec['doc'])) - {'1D'}))} candles, so it is "
           "worked out in the background at each close; the first answer appears within the hour.")
    return (f"<td data-sort='' data-sec='{section}' style='padding:10px;text-align:center;'>"
            f"<span title='{_esc(tip)}' style='opacity:.55;'>—</span></td>")


def _timeframes(doc) -> list[str]:
    import column_answers as ca

    return ca.timeframes(doc or {})


def _stale_mark(stale: bool) -> str:
    return ("<span aria-label='may be out of date' style='font-size:11px;margin-left:3px;vertical-align:super;'>⏳</span>"
            if stale else "")


def _pick(spec: dict, row_pick: str | None) -> str:
    """With the row's asset, a click opens that asset's 🔍 Why block for this column; without, the Group or Set
    in Lattice."""
    if row_pick:
        return f"{row_pick}|breakdown|{spec['key']}"
    return f"lattice|{spec['part']}|{spec['config'] or spec['key']}"


def group_cell(spec: dict, cell: dict | None, row_pick: str | None = None) -> str:
    """Bar and number (or the Group's label), coloured like the dashboard readings; hover explains; click opens
    the Group in Signal Groups."""
    from signals_view import mini_bar, number_badge

    if cell is None and not daily_only(spec.get("doc")):
        return waiting_cell(spec, "g")
    cell = cell or {}
    value = cell.get("value")
    label = cell.get("label")
    when, stale = freshness(spec, cell)
    sort = "" if value is None else f"{float(value):.4f}"
    tip = f"{spec['name']}: " + ("no reading" if value is None else f"{value:+.0f}") + (f" · {label}" if label else "")
    if cell.get("why"):
        tip += f" · {cell['why']}"
    if cell.get("error"):
        tip += f" · could not be worked out ({cell['error']})"
    if when:
        tip += f" · {when}"
    inner = (f"<span style='display:inline-flex;align-items:center;gap:6px;'>{mini_bar(value, 48)}"
             + (f"<span style='font-size:12px;font-weight:600;'>{_esc(label)}</span>" if label else number_badge(value))
             + _stale_mark(stale) + "</span>")
    return _clickable(_pick(spec, row_pick), tip, inner, sort, "g")


ANSWER_MARK = {"yes": ("✓", "Yes", YES), "no": ("✕", "No", NO), "unknown": ("?", "Unknown", UNKNOWN)}
ANSWER_HOVER = {"yes": "Yes: conditions met", "no": "No: a condition failed",
                "unknown": "Unknown: nothing failed, but some data is missing"}


def set_cell(spec: dict, cell: dict | None, row_pick: str | None = None) -> str:
    """✓ Yes, ✕ No or ? Unknown in a small round badge; hover gives the reason; click opens the Set."""
    if cell is None and not daily_only(spec.get("doc")):
        return waiting_cell(spec, "s")
    cell = cell or {}
    answer = cell.get("answer") if cell.get("answer") in ANSWER_MARK else "unknown"
    when, stale = freshness(spec, cell)
    mark, word, (fg, bg) = ANSWER_MARK[answer]
    import perspectives

    tip = f"{spec['name']}: {ANSWER_HOVER[answer]}" + (f" · {cell['why']}" if cell.get("why") else "")
    if cell.get("available"):
        tip += " · " + " ".join(perspectives.data_mark(cell["available"]))
    tip += " · " + " ".join(perspectives.evidence(spec.get("doc"), spec.get("key")))
    if cell.get("error"):
        tip += f" · could not be worked out ({cell['error']})"
    if when:
        tip += f" · {when}"
    inner = (f"<span aria-label='{_esc(word)}' style='display:inline-flex;align-items:center;justify-content:center;"
             f"width:24px;height:24px;border-radius:50%;background:{bg};color:{fg};font-weight:700;'>{mark}</span>"
             + _stale_mark(stale))
    sort = {"yes": "2", "unknown": "1", "no": "0"}[answer]
    return _clickable(_pick(spec, row_pick), tip, inner, sort, "s", center=True)


def _clickable(pick: str, tip: str, inner: str, sort: str, section: str, center: bool = False) -> str:
    align = "text-align:center;" if center else ""
    return (f"<td data-sort='{_esc(sort)}' data-sec='{section}' style='padding:10px;white-space:nowrap;{align}'>"
            f"<button type='button' data-pick='{_esc(pick)}' title='{_esc(tip)}' style='display:inline-block;margin:0;"
            "padding:0;border:none;background:transparent;cursor:pointer;font:inherit;color:inherit;'>"
            f"{inner}</button></td>")


def folded_cell(part: str, cells: list[dict]) -> str:
    """The one narrow cell a folded section shows: Sets, how many said Yes; Groups, a dot."""
    if part == "sets":
        yes = sum(1 for c in cells if (c or {}).get("answer") == "yes")
        inner = (f"<span title='{yes} of {len(cells)} Sets say Yes' style='font-weight:600;color:"
                 f"{YES[0] if yes else NO[0]};'>{yes}✓</span>")
        return f"<td data-sort='{yes}' data-sec-folded='s' style='padding:10px;text-align:center;'>{inner}</td>"
    return "<td data-sort='' data-sec-folded='g' style='padding:10px;text-align:center;opacity:.5;'>…</td>"


def daily_only(doc: dict | None) -> bool:
    """True when every member reads daily candles (the tables have stored daily bars only)."""
    if not doc:
        return True
    try:
        refs = [m["ref"] for m in doc.get("members") or []]
        for g in doc.get("groups") or []:
            refs += [m["ref"] for m in (g.get("snapshot") or {}).get("members") or []]
        refs += [m.get("ref") or m for m in doc.get("standalone") or []]
        return all((r or {}).get("timeframe", "1D") == "1D" for r in refs)
    except Exception:
        return True

