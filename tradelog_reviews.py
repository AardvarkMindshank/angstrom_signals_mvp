"""Weekly reviews the new app asks for (marketnavi.ai/new/).

The new app runs in the member's browser and holds no AI keys, so "Write my review" saves a row with
review = {"pending": true, "zone": "<member's time zone>"} and this step, run by the background worker, writes it:
the same facts and the same checked AI review as the classic app (tradelog_coach), in the language the row asks for.
Logs only counts, never trades or amounts.
"""
from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

MAX_PER_PASS = 10


def _zone(name):
    try:
        return ZoneInfo(str(name or "UTC"))
    except Exception:
        return ZoneInfo("UTC")


def pending(supabase) -> list[dict]:
    try:
        return (supabase.table("trade_reviews").select("user_id,week_start,scope,language,review")
                .eq("review->>pending", "true").limit(MAX_PER_PASS).execute().data or [])
    except Exception:
        return []


def _ai_choice(supabase, user_id: str) -> str | None:
    try:
        rows = supabase.table("user_preferences").select("settings").eq("user_id", user_id).limit(1).execute().data or []
        return ((rows[0] or {}).get("settings") or {}).get("ai_navigator") if rows else None
    except Exception:
        return None


def _language(code) -> str:
    """The row keeps the app's language code (en, de, zh-CN…); the review is written in that language's English name."""
    import i18n

    return next((x["english"] for x in i18n.LANGUAGES if x["code"] == str(code or "")), "English")


def write_one(supabase, row: dict, write=None) -> str:
    """Write one pending review. Returns "written", "empty" or "failed"."""
    import tradelog_coach
    from tradelog_insights import _rows

    user_id = row["user_id"]
    start = date.fromisoformat(str(row["week_start"])[:10])
    week = (start, start + timedelta(days=6))
    zone = _zone((row.get("review") or {}).get("zone"))
    scope = str(row.get("scope") or "all")
    trips = _rows(supabase, "trade_round_trips", "*", user_id)
    trips = [t for t in trips if not t.get("reward")]
    since = (start - timedelta(days=92)).isoformat()
    ids = {t["id"] for t in trips if str(t.get("closed_at") or "")[:10] >= since}
    snaps = {}
    if ids:
        for s in _rows(supabase, "trade_snapshots", "round_trip_id,moment,readings", user_id, "round_trip_id", "moment"):
            if s["round_trip_id"] in ids:
                snaps[(s["round_trip_id"], s["moment"])] = s.get("readings") or {}
    fact = tradelog_coach.facts(trips, snaps, week, zone, scope)
    if not fact["trades"]:
        review, provider, state = {**tradelog_coach.plain_review(fact), "empty": True}, "", "empty"
    else:
        import ai_providers

        provider = ai_providers.pick("navigator", _ai_choice(supabase, user_id))
        language = _language(row.get("language"))
        review = (write or tradelog_coach.write)(fact, provider, language=language)
        state = "written"
    try:
        supabase.table("trade_reviews").update({"review": review, "provider": provider[:20]}) \
            .eq("user_id", user_id).eq("week_start", row["week_start"]).eq("scope", scope).execute()
    except Exception:
        return "failed"
    return state


def run_pending(supabase, write=None) -> str:
    rows = pending(supabase)
    done = {"written": 0, "empty": 0, "failed": 0}
    for row in rows:
        try:
            done[write_one(supabase, row, write)] += 1
        except Exception:
            done["failed"] += 1
    return f"{len(rows)} asked, {done['written']} written, {done['empty']} with no trades, {done['failed']} failed"
