"""A "Study finished" notification opens the Set it is about (asked 10 Nov 2026). The note carries the study's Set
fingerprint (what_followed.logic_hash) as asset_symbol "study:<hash>"; older notes carry only the Set's name."""

from __future__ import annotations

import what_followed as wf


def pick_value(note: dict) -> str:
    """The click value for a study note: study|<hash>|<name>."""
    symbol = str(note.get("asset_symbol") or "")
    h = symbol.split(":", 1)[1] if symbol.startswith("study:") else ""
    return f"study|{h}|{str(note.get('asset_name') or '').replace('|', ' ')}"


def find_set(configs: list[dict], set_hash: str, name: str = "") -> tuple[str, int] | None:
    """(config id, version) of the reader's Set whose version has this fingerprint, newest version first; else the
    Set with this name (older notes). configs: signal_groups_inspector.saved_configs rows."""
    sets = [c for c in configs if c.get("kind") == "set"]
    if set_hash:
        for c in sets:
            for v in sorted(c.get("versions") or [], key=lambda v: -v["version"]):
                try:
                    if wf.logic_hash(v["body"]) == set_hash:
                        return c["id"], v["version"]
                except Exception:
                    continue
    for c in sets:
        if name and str(c.get("name") or "").strip() == name.strip():
            return c["id"], c.get("current_version") or 0
    return None
