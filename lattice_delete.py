"""
Deleting your own Group or Set in Angstrom Lattice, with no loose ends (owner's rule, 8 Nov 2026):

- A Group can't be deleted while one of your Sets uses it; a Set can't be deleted while one of your scans uses it.
  The screen names them so they can be removed first.
- A table column showing it is only a display choice: deleting removes the column.
- Deleting archives the item (hidden everywhere, kept in the database); Undo brings it back
  (sql/2026-11-13_restore_config.sql).
"""

from __future__ import annotations


def sets_using(group_id: str, saved: list[dict], user_id: str) -> list[str]:
    """Names of your Sets whose newest version contains this Group."""
    out = []
    for c in saved:
        if c.get("kind") != "set" or c.get("owner_id") != user_id or c.get("archived") or not c.get("versions"):
            continue
        body = c["versions"][-1].get("body") or {}
        if any((g.get("provenance") or {}).get("source_config") == group_id for g in body.get("groups") or []):
            out.append(c["name"])
    return out


def scans_using(set_id: str, scans: list[dict]) -> list[str]:
    """Names of your scans built from this Set."""
    return [s.get("name") or "a scan" for s in scans if (s.get("set_source") or {}).get("config") == set_id]


def column_settings_without(settings: dict, key: str) -> dict | None:
    """The account's table-column choice with this item removed, or None if it wasn't a column."""
    cols = (settings or {}).get("table_columns")
    if not isinstance(cols, dict):
        return None
    out, changed = {}, False
    for part, keys in cols.items():
        kept = [k for k in (keys or []) if k != key]
        changed |= len(kept) != len(keys or [])
        out[part] = kept
    return out if changed else None


def blocked_message(kind: str, users: list[str]) -> str:
    what = "Sets" if kind == "group" else "scans"
    names = ", ".join(users[:6]) + (f" and {len(users) - 6} more" if len(users) > 6 else "")
    one = "Set" if kind == "group" else "scan"
    return (f"Used in {len(users)} of your {what}: {names}. Remove it from "
            f"{'them' if len(users) > 1 else 'that ' + one} first, then delete.")
