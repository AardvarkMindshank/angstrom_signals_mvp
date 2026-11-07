"""
Answers for table columns that read 4-hour, hourly or weekly candles (docs/design/table_columns.md).

The tables work daily columns out themselves, from the stored daily bars. Other timeframes are not stored (keeping
them would cost database egress every hour), so the background worker works those columns out at each close of
their shortest timeframe, from the price provider, through the same point-in-time reconstruction Prism uses, and
saves only the answer: score and label (Groups) or Yes / No / Unknown (Sets), the reason, and the moment it is "as
of". The tables read those small rows.

Only columns someone has chosen are worked out, once per definition, asset and close, shared by every account that
chose the same definition. Hourly is the most often anything runs (a 15-minute column is worked out hourly).
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

import pandas as pd

import table_columns as tc

SETTLE = pd.Timedelta(minutes=10)
MINUTES = {"15m": 15, "1h": 60, "4h": 240, "1D": 1440, "1W": 1440}
NEW_YORK = "America/New_York"
BUDGET_SECONDS = 120


def def_hash(doc: dict) -> str:
    """The same definition gives the same key, whoever chose it."""
    return hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest()[:24]


def timeframes(doc: dict) -> list[str]:
    refs = [m.get("ref") or {} for m in doc.get("members") or []]
    for g in doc.get("groups") or []:
        refs += [m.get("ref") or {} for m in (g.get("snapshot") or {}).get("members") or []]
    refs += [m.get("ref") or m for m in doc.get("standalone") or []]
    return [str(r.get("timeframe") or "1D") for r in refs]


def cadence(doc: dict) -> int:
    """Minutes between answers: the shortest timeframe it reads, at least an hour."""
    shortest = min((MINUTES.get(t, 1440) for t in timeframes(doc)), default=1440)
    return max(60, shortest)


def cutoff(doc: dict, market: str, now) -> pd.Timestamp:
    """The moment the answer is worked out at: the latest close of its cadence, a few minutes settled. Shares are
    held at the last New York close outside trading hours, so a closed market is worked out once."""
    now = pd.Timestamp(now).tz_convert("UTC") if pd.Timestamp(now).tzinfo else pd.Timestamp(now).tz_localize("UTC")
    step = cadence(doc)
    t = (now - SETTLE).floor(f"{step}min")
    if market == "equity":
        local = t.tz_convert(NEW_YORK)
        close = local.normalize() + pd.Timedelta(hours=16)
        opened = local.normalize() + pd.Timedelta(hours=9, minutes=30)
        if local.weekday() >= 5 or local < opened:
            day = local.normalize() - pd.Timedelta(days=1)
            while day.weekday() >= 5:
                day -= pd.Timedelta(days=1)
            t = (day + pd.Timedelta(hours=16)).tz_convert("UTC")
        elif local > close:
            t = close.tz_convert("UTC")
    return t


def wanted(user_prefs: list[dict], configs: dict) -> dict:
    """def hash -> {"spec", "assets": {(kind, id, label)}} for every chosen column that isn't daily-only.
    configs: config id -> config with versions (only the ones chosen)."""
    out: dict = {}
    for pref in user_prefs:
        settings = pref.get("settings") if isinstance(pref.get("settings"), dict) else {}
        specs = tc.resolve(tc.chosen(settings), list(configs.values()))
        specs = [s for s in specs if s["doc"] is not None and not tc.daily_only(s["doc"])]
        if not specs:
            continue
        crypto = pref.get("crypto_watchlist") if isinstance(pref.get("crypto_watchlist"), dict) else {}
        stocks = pref.get("stock_watchlist") if isinstance(pref.get("stock_watchlist"), dict) else {}
        assets = set()
        if settings.get("trade_crypto", True) is not False:
            assets |= {("crypto", str(k), str(v)) for k, v in crypto.items()}
        if settings.get("trade_equities", True) is not False:
            assets |= {("equity", str(k).upper(), f"{v} ({str(k).upper()})") for k, v in stocks.items()}
        for spec in specs:
            entry = out.setdefault(def_hash(spec["doc"]), {"spec": spec, "assets": set()})
            entry["assets"] |= assets
    return out


def chosen_config_ids(user_prefs: list[dict]) -> set[str]:
    ids = set()
    for pref in user_prefs:
        settings = pref.get("settings") if isinstance(pref.get("settings"), dict) else {}
        for part in tc.chosen(settings).values():
            ids |= {k.split(":", 1)[1] for k in part if k.startswith("saved:")}
    return ids


def evaluate(spec: dict, assets: list[tuple], at: pd.Timestamp, run) -> dict:
    """asset key -> answer row at `at`, through the point-in-time reconstruction (run: a display ReplayRun)."""
    import prism
    import signal_groups as sg

    out = {}
    for kind, asset_id, label in assets:
        key = f"{kind}:{asset_id}"
        try:
            ctx = run.context(kind, asset_id, at)
            if spec["part"] == "groups":
                result = sg.evaluate_group(spec["doc"], ctx, data_mode="point_in_time", as_of=at)
                score = (result.get("score") or {}).get("value")
                out[key] = {"value": None if score is None else score * 100,
                            "label": (result.get("outcome") or {}).get("label"), "why": tc._group_why(result)}
            else:
                result = sg.evaluate_set(spec["doc"], ctx, data_mode="point_in_time",
                                         subject_context=lambda k, i: run.context(k, i, at))
                row = prism.row(label, result, "")
                out[key] = {"answer": row["answer"], "why": row.get("reason") or ""}
        except Exception as exc:
            out[key] = {"error": str(exc)[:160]}
    return out


def _configs(supabase, ids: set[str]) -> dict:
    """The chosen Groups and Sets with their versions (service role: only these ids are read)."""
    ids = sorted(ids)
    configs = (supabase.table("analysis_configs").select("id, kind, name, owner_id, starter_alias, current_version")
               .in_("id", ids).execute().data or [])
    versions = (supabase.table("analysis_config_versions").select("config_id, version, body").in_("config_id", ids)
                .execute().data or [])
    by: dict = {}
    for v in versions:
        by.setdefault(v["config_id"], []).append(v)
    out = {}
    for c in configs:
        c["versions"] = sorted(by.get(c["id"], []), key=lambda v: v["version"])
        if c["versions"]:
            out[c["id"]] = c
    return out


def _ts(value) -> pd.Timestamp:
    if not value:
        return pd.Timestamp(0, tz="UTC")
    t = pd.Timestamp(value)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def run_from_worker(supabase, user_prefs: list[dict], *, now=None, log=print, clock=time.monotonic) -> dict:
    """Work out every due answer that fits in the time budget, and save it."""
    from market_store import MINIMAL
    from signal_library.replay_display import display_run

    now = _ts(now or datetime.now(timezone.utc))
    ids = chosen_config_ids(user_prefs)
    if not ids:
        return {"columns": 0}
    configs = _configs(supabase, ids)
    want = wanted(user_prefs, configs)
    if not want:
        return {"columns": 0}
    try:
        have = {(r["def_hash"], r["asset_key"]): r["cutoff"] for r in
                (supabase.table("column_answers").select("def_hash, asset_key, cutoff").in_("def_hash", list(want))
                 .execute().data or [])}
    except Exception as exc:
        return {"skipped": f"column_answers not installed (sql/2026-11-11_column_answers.sql): {str(exc)[:80]}"}
    started, saved, runs = clock(), 0, {}
    for h, entry in want.items():
        rows = []
        for market in ("crypto", "equity"):
            assets = sorted(a for a in entry["assets"] if a[0] == market)
            if not assets:
                continue
            at = cutoff(entry["spec"]["doc"], market, now)
            due = [a for a in assets if _ts(have.get((h, f"{a[0]}:{a[1]}"))) < at]
            if not due:
                continue
            if clock() - started > BUDGET_SECONDS:
                log("Table columns: the rest wait for the next pass (time budget used).")
                break
            run = runs.get(at) or display_run(None, max_steps=1, shortcut=True)
            runs[at] = run
            for key, answer in evaluate(entry["spec"], due, at, run).items():
                rows.append({"def_hash": h, "asset_key": key, "cutoff": at.isoformat(), "payload": answer,
                             "computed_at": datetime.now(timezone.utc).isoformat()})
        if rows:
            supabase.table("column_answers").upsert(rows, on_conflict="def_hash,asset_key", returning=MINIMAL).execute()
            saved += len(rows)
    return {"columns": len(want), "answers_saved": saved}


def load(supabase, hashes: list[str], asset_keys: list[str]) -> dict:
    """(def hash, asset key) -> {payload..., "as_of"} for the tables. Small rows only."""
    if not hashes or not asset_keys:
        return {}
    try:
        rows = (supabase.table("column_answers").select("def_hash, asset_key, cutoff, payload")
                .in_("def_hash", hashes).in_("asset_key", asset_keys).execute().data or [])
    except Exception:
        return {}
    return {(r["def_hash"], r["asset_key"]): {**(r.get("payload") or {}), "as_of": r.get("cutoff")} for r in rows}
