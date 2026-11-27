"""🛠️ Admin › System for the new app: whether the background lookups are working (the classic admin panel's
earnings dates and market overview status). Admins only; read-only. Nothing is logged."""
from __future__ import annotations

import time


def status(db) -> dict:
    try:
        if not bool(db.rpc("is_admin").execute().data):
            return {"ok": False}
    except Exception:
        return {"ok": False}
    import market_overview as mo
    import market_store as ms

    earnings = ms.load_earnings_status(db)
    saved = mo.load_overview(db) or {}
    now = time.time()
    fetched = float(saved.get("fetched_at") or 0)
    return {"ok": True, "earnings": earnings,
            "overview": {"readings": len(saved.get("items") or {}), "ago": (now - fetched) if fetched else None,
                         "refresh": mo.REFRESH_SECONDS, "stale": mo.STALE_SECONDS,
                         "errors": [str(e)[:200] for e in (saved.get("errors") or [])][:12]}}
