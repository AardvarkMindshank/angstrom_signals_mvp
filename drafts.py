"""
Unsaved changes that survive closing the browser (or signing out and in, or another device).

The Group, Set and funnel editors keep a working copy while you edit. remember() stores it in editor_drafts
(sql/2026-11-22_editor_drafts.sql) whenever it differs from what it started from, and forgets it when it is back to
that or when you save or discard. When the editor opens the same Group, Set or funnel again, restore() hands back the
stored copy, and the editor says so, with a way to discard it.

Only the account itself can read or write its drafts (row-level security). Every call is best-effort: without the
table, or offline, editing works exactly as before, just without the safety net.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

KINDS = ("group", "set", "funnel")
TABLE = "editor_drafts"


def _digest(body) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _memo(state) -> dict:
    return state.setdefault("_draft_digests", {})


def restore(state, supabase, user_id, kind: str, key: str) -> tuple[dict, str] | None:
    """(body, saved at) of the stored draft for this Group, Set or funnel, or None."""
    if not user_id or supabase is None:
        return None
    try:
        rows = (supabase.table(TABLE).select("body, updated_at").eq("owner_id", user_id).eq("kind", kind)
                .eq("draft_key", str(key)).limit(1).execute().data or [])
    except Exception:
        return None
    if not rows or not isinstance(rows[0].get("body"), dict):
        return None
    _memo(state)[(kind, str(key))] = _digest(rows[0]["body"])
    return rows[0]["body"], str(rows[0].get("updated_at") or "")


def remember(state, supabase, user_id, kind: str, key: str, body, base) -> None:
    """Store the working copy when it differs from where it started; forget it when it is back to that."""
    if not user_id or supabase is None:
        return
    memo, k = _memo(state), (kind, str(key))
    if _digest(body) == _digest(base):
        if memo.get(k) is not None:
            forget(state, supabase, user_id, kind, key)
        return
    digest = _digest(body)
    if memo.get(k) == digest:
        return                                          # unchanged since the last store: no write
    try:
        supabase.table(TABLE).upsert({"owner_id": user_id, "kind": kind, "draft_key": str(key), "body": body,
                                      "updated_at": datetime.now(timezone.utc).isoformat()},
                                     on_conflict="owner_id,kind,draft_key").execute()
        memo[k] = digest
    except Exception:
        pass


def forget(state, supabase, user_id, kind: str, key: str) -> None:
    _memo(state)[(kind, str(key))] = None
    if not user_id or supabase is None:
        return
    try:
        (supabase.table(TABLE).delete().eq("owner_id", user_id).eq("kind", kind).eq("draft_key", str(key))
         .execute())
    except Exception:
        pass


def when(stamp: str) -> str:
    """'11 Nov 22:10 UTC' for the restored notice."""
    try:
        t = datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return "earlier"
    return f"{t.day} {t.strftime('%b %H:%M')} UTC"


# ----------------------------------------------------------------------------------- Group and Set editors

def after_load(state, supabase, user_id, kind: str, key: str, model_key: str, clean) -> None:
    """Right after an editor loads its starting point: remember that as the base, then put back a stored draft."""
    import copy

    state[f"_draft_base_{kind}"] = (key, clean(copy.deepcopy(state.get(model_key))))
    state.pop(f"_draft_restored_{kind}", None)
    kept = restore(state, supabase, user_id, kind, key)
    if kept:
        try:
            state[model_key] = clean(kept[0])
            state[f"_draft_restored_{kind}"] = (key, kept[1])
        except Exception:
            forget(state, supabase, user_id, kind, key)


def track(st, supabase, user_id, kind: str, key: str, model, clean, loaded_key: str, rerun) -> None:
    """Store the editor's model when it differs from its base; show the restored notice with Discard."""
    base = st.session_state.get(f"_draft_base_{kind}")
    if base and base[0] == key:
        remember(st.session_state, supabase, user_id, kind, key, clean(model), base[1])
    restored = st.session_state.get(f"_draft_restored_{kind}")
    if restored and restored[0] == key:
        box = st.container(horizontal=True, vertical_alignment="center")
        box.info(f"Your unsaved changes from {when(restored[1])} are back.", icon=":material/history:")
        if box.button("Discard them", icon=":material/undo:", key=f"draft_discard_{kind}",
                      help="Go back to the saved version (or the starting point) and forget these changes."):
            forget(st.session_state, supabase, user_id, kind, key)
            st.session_state.pop(f"_draft_restored_{kind}", None)
            st.session_state.pop(loaded_key, None)        # load the starting point again
            rerun(st)


def saved(state, supabase, user_id, kind: str, key: str) -> None:
    """The editor saved: its draft is done with."""
    forget(state, supabase, user_id, kind, key)
    state.pop(f"_draft_restored_{kind}", None)
    state.pop(f"_draft_base_{kind}", None)
