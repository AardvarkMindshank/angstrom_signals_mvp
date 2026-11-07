"""
Helpers for Signal Groups and Sets used by Angstrom Lattice and the checks: reading saved Groups and Sets, the
example Set, database error words, and point-in-time reconstruction. The admin panel that used to live here was
removed; Lattice and Prism replace it.
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

import signal_groups as sg
import signal_library as sl

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



def reconstruct(supabase, kind: str, body: dict, asset_kind: str, asset_id: str, as_of, title: str) -> tuple:
    """One as-of reconstruction (display mode: descriptive, not saved, not for statistics).
    Returns (title, kind, result or None, record or None, error or None)."""
    from signal_library.replay import ReplayRefused
    from signal_library.replay_display import display_run

    now = pd.Timestamp.now(tz="UTC")
    if as_of >= now:
        return title, kind, {"data_mode": "point_in_time"}, None, "Choose a time in the past."
    try:
        run = display_run(supabase, max_steps=1, shortcut=True)   # certified slicing only (approved 4 Nov)
        ctx = run.context(asset_kind, asset_id, as_of)
        if kind == "group":
            result = sg.evaluate_group(body, ctx, data_mode="point_in_time", as_of=as_of)
        else:
            result = sg.evaluate_set(body, ctx, data_mode="point_in_time",
                                     market_context=lambda scope: run.context("market", scope.split(":", 1)[1], as_of))
        return title, kind, result, run.record(), None
    except ReplayRefused as exc:
        return title, kind, {"data_mode": "point_in_time"}, None, str(exc)


