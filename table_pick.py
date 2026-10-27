"""Which table row a click just chose, read before the tables are drawn.

A click on a table row arrives as a one-run trigger. The tables are drawn
before the app handles it, so without this the highlighted row would stay on
the old asset until the next click.
"""

from __future__ import annotations


def clicked_pick(session_state, kinds=("Crypto", "Stock")):
    """(kind, asset_id) from a row click waiting in session_state, else None."""
    for kind in kinds:
        try:
            state = session_state.get(f"score_table_{kind}")
        except Exception:
            continue
        raw = None
        if state is not None:
            raw = getattr(state, "picked", None)
            if raw is None and hasattr(state, "get"):
                try:
                    raw = state.get("picked")
                except Exception:
                    raw = None
        parts = str(raw).split("|") if raw else []
        if len(parts) >= 2 and parts[0] in ("Crypto", "Stock") and parts[1]:
            return parts[0], parts[1]
    return None
