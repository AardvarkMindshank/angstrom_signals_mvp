"""
Shared alert rules for the dashboard and the background worker.

An alert stays latched while the score remains past the threshold. It re-arms
after the score leaves that threshold, so the same asset can alert again later.
"""

from __future__ import annotations

from datetime import datetime, timezone

BULLISH = "BULLISH_THRESHOLD"
BEARISH = "BEARISH_THRESHOLD"


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

    for row in results:
        score = row.get("score")
        if _missing(score):
            continue
        score = float(score)
        symbol = row.get("key")
        if not symbol:
            continue
        name = row.get("symbol") or symbol

        bullish = score >= min_thresh
        bearish = score <= max_thresh

        if not bullish and (symbol, BULLISH) in held:
            actions.append(("resolve", symbol, BULLISH))
            held.discard((symbol, BULLISH))
        if not bearish and (symbol, BEARISH) in held:
            actions.append(("resolve", symbol, BEARISH))
            held.discard((symbol, BEARISH))

        if bullish and (symbol, BULLISH) not in held:
            message = f"Score reached {score:.1f}/100 (bullish setup)"
            actions.append(("open", symbol, name, BULLISH, message))
            held.add((symbol, BULLISH))
        elif bearish and (symbol, BEARISH) not in held:
            message = f"Score dropped to {score:.1f}/100 (bearish setup)"
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
        .in_("alert_type", [BULLISH, BEARISH])
        .execute()
        .data
        or []
    )
    latched = {(row["asset_symbol"], row["alert_type"]) for row in existing}
    opened = []

    for action in plan_alert_actions(results, latched, min_thresh, max_thresh):
        if action[0] == "resolve":
            _, symbol, alert_type = action
            (
                supabase.table("user_notifications")
                .update({"alert_type": f"{alert_type}_resolved"})
                .eq("user_id", user_id)
                .eq("asset_symbol", symbol)
                .eq("alert_type", alert_type)
                .execute()
            )
            continue

        _, symbol, name, alert_type, message = action
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

    if notify_email and send_email:
        _email_open_crossings(supabase, user_id, notify_email, send_email)

    return opened


def _email_open_crossings(supabase, user_id, notify_email, send_email) -> None:
    """Email each unresolved crossing once. A later run skips rows already marked."""
    try:
        pending = (
            supabase.table("user_notifications")
            .select("id, asset_name, message")
            .eq("user_id", user_id)
            .in_("alert_type", [BULLISH, BEARISH])
            .is_("emailed_at", "null")
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
        try:
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
