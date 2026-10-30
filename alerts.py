"""
Shared alert rules for the dashboard and the background worker.

An alert stays latched while the score remains past the threshold. It re-arms
only after the score has moved 10 points back through that line, so a small
bounce does not alert again. One indicator flipping can move the score by
several points within a day, so a narrower gap let alerts repeat. Reading or clearing the notification does not
release that latch. The background worker is the only writer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

BULLISH = "BULLISH_THRESHOLD"
BEARISH = "BEARISH_THRESHOLD"
HELD_BULLISH = "BULLISH_THRESHOLD_HELD"
HELD_BEARISH = "BEARISH_THRESHOLD_HELD"
_HELD = {
    BULLISH: HELD_BULLISH,
    BEARISH: HELD_BEARISH,
}
# How far back through the line the score must travel before that alert can arm again.
_REARM_POINTS = 10.0


def latch_symbol(symbol: str) -> str:
    """One latch identity for an asset, whatever case the watchlist used."""
    return " ".join(str(symbol or "").split()).lower()


def canonical_alert(alert_type: str) -> str:
    """The open crossing a row represents, including one hidden after it was cleared."""
    if alert_type in (BULLISH, HELD_BULLISH):
        return BULLISH
    if alert_type in (BEARISH, HELD_BEARISH):
        return BEARISH
    return alert_type


def stored_types(alert_type: str) -> list[str]:
    """Rows that still mean this crossing, whether or not the feed is showing them."""
    held = _HELD.get(alert_type)
    if held:
        return [alert_type, held]
    return [alert_type]


def _missing(score) -> bool:
    if score is None:
        return True
    try:
        value = float(score)
    except (TypeError, ValueError):
        return True
    return value != value


def plan_alert_actions(results, latched, min_thresh, max_thresh):
    """
    Decide which latches to release and which alerts to open.

    latched is a set of (symbol, alert_type). Each action is
    ("resolve", symbol, alert_type) or
    ("open", symbol, name, alert_type, message).
    """
    actions = []
    held = set(latched)
    bullish_clear = min_thresh - _REARM_POINTS
    bearish_clear = max_thresh + _REARM_POINTS
    if bullish_clear < max_thresh:
        bullish_clear = max_thresh
    if bearish_clear > min_thresh:
        bearish_clear = min_thresh

    for row in results:
        score = row.get("score")
        if _missing(score):
            continue
        score = float(score)
        symbol = latch_symbol(row.get("key"))
        if not symbol:
            continue
        name = row.get("symbol") or symbol

        bullish = score >= min_thresh
        bearish = score <= max_thresh

        if score <= bullish_clear and (symbol, BULLISH) in held:
            actions.append(("resolve", symbol, BULLISH))
            held.discard((symbol, BULLISH))
        if score >= bearish_clear and (symbol, BEARISH) in held:
            actions.append(("resolve", symbol, BEARISH))
            held.discard((symbol, BEARISH))

        if bullish and (symbol, BULLISH) not in held:
            message = f"Score reached {score:.1f}/100 (strongly positive reading)"
            actions.append(("open", symbol, name, BULLISH, message))
            held.add((symbol, BULLISH))
        elif bearish and (symbol, BEARISH) not in held:
            message = f"Score dropped to {score:.1f}/100 (strongly negative reading)"
            actions.append(("open", symbol, name, BEARISH, message))
            held.add((symbol, BEARISH))

    return actions


def evaluate_alerts(supabase, user_id, results, alerts_config, notify_email=None, send_email=None):
    """
    Apply plan_alert_actions for one user.

    send_email(to_email, asset_name, message) runs once for each open crossing
    that has not been emailed yet. It does not run again while the score stays
    past the threshold.
    Returns the opened alert rows.
    """
    if not alerts_config or not alerts_config.get("enabled", True):
        return []

    min_thresh = float(alerts_config.get("min_score_alert", 70))
    max_thresh = float(alerts_config.get("max_score_alert", 30))

    existing = (
        supabase.table("user_notifications")
        .select("asset_symbol, alert_type")
        .eq("user_id", user_id)
        .in_("alert_type", [BULLISH, BEARISH, HELD_BULLISH, HELD_BEARISH])
        .execute()
        .data
        or []
    )
    stored = {}
    latched = set()
    for row in existing:
        raw = str(row.get("asset_symbol") or "")
        symbol = latch_symbol(raw)
        if not symbol:
            continue
        kind = canonical_alert(row.get("alert_type"))
        latched.add((symbol, kind))
        stored.setdefault((symbol, kind), set()).add(raw)
    opened = []

    for action in plan_alert_actions(results, latched, min_thresh, max_thresh):
        if action[0] == "resolve":
            _, symbol, alert_type = action
            for raw in stored.get((symbol, alert_type), {symbol}):
                (
                    supabase.table("user_notifications")
                    .update({"alert_type": f"{alert_type}_resolved"})
                    .eq("user_id", user_id)
                    .eq("asset_symbol", raw)
                    .in_("alert_type", stored_types(alert_type))
                    .execute()
                )
            continue

        _, symbol, name, alert_type, message = action
        already = (
            supabase.table("user_notifications")
            .select("asset_symbol")
            .eq("user_id", user_id)
            .eq("asset_symbol", symbol)
            .in_("alert_type", stored_types(alert_type))
            .limit(1)
            .execute()
            .data
            or []
        )
        if already:
            continue
        (
            supabase.table("user_notifications")
            .insert({
                "user_id": user_id,
                "asset_symbol": symbol,
                "asset_name": name,
                "alert_type": alert_type,
                "message": message,
            })
            .execute()
        )
        opened.append({
            "asset_symbol": symbol,
            "asset_name": name,
            "alert_type": alert_type,
            "message": message,
        })

    # Instant emails are on unless the user turned them off. A digest-only user
    # leaves the crossings unsent here; the digest picks them up.
    if notify_email and send_email and alerts_config.get("instant_email") is not False:
        _email_open_crossings(supabase, user_id, notify_email, send_email, logos_by_symbol(results))

    return opened


def logos_by_symbol(results) -> dict[str, str]:
    """Logo address for each scored asset, keyed the way alert rows store the asset."""
    logos = {}
    for row in results or []:
        url = str(row.get("logo") or "").strip()
        symbol = latch_symbol(row.get("key"))
        if url and symbol:
            logos[symbol] = url
    return logos


def _email_open_crossings(supabase, user_id, notify_email, send_email, logos=None) -> None:
    """Email each unresolved crossing once. A later run skips rows already marked."""
    logos = logos or {}
    try:
        pending = (
            supabase.table("user_notifications")
            .select("id, asset_symbol, asset_name, message")
            .eq("user_id", user_id)
            .in_("alert_type", [BULLISH, BEARISH, HELD_BULLISH, HELD_BEARISH])
            .is_("emailed_at", "null")
            # A crossing older than a day is stale. This also stops a burst of old
            # crossings if someone turns instant alerts back on after a while.
            .gte("created_at", (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat())
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(
            "Could not look for unsent alert emails. Run the latest supabase_rls.sql "
            f"in the Supabase SQL editor. {exc}"
        )
        return

    for note in pending:
        name = note.get("asset_name") or "Asset"
        logo = logos.get(latch_symbol(note.get("asset_symbol")), "")
        try:
            if logo:
                sent = bool(send_email(notify_email, name, note.get("message") or "", logo_url=logo))
            else:
                sent = bool(send_email(notify_email, name, note.get("message") or ""))
        except Exception as exc:
            print(f"Email failed for {name}: {exc}")
            continue
        if not sent:
            continue
        try:
            (
                supabase.table("user_notifications")
                .update({"emailed_at": datetime.now(timezone.utc).isoformat()})
                .eq("id", note["id"])
                .execute()
            )
        except Exception as exc:
            print(f"Email was accepted for {name} but could not be marked sent. {exc}")


def dismiss_read_alerts(supabase, user_id) -> None:
    """Remove read alerts from the feed. A score still past its line stays latched."""
    for open_type, held_type in _HELD.items():
        (
            supabase.table("user_notifications")
            .update({"alert_type": held_type, "is_read": True})
            .eq("user_id", user_id)
            .eq("is_read", True)
            .eq("alert_type", open_type)
            .execute()
        )
    (
        supabase.table("user_notifications")
        .delete()
        .eq("user_id", user_id)
        .eq("is_read", True)
        .neq("alert_type", "group_invite")
        .not_.in_("alert_type", [HELD_BULLISH, HELD_BEARISH, "moderation_warning", "report_update"])
        .execute()
    )
