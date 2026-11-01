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

BULLISH = "BULLISH_THRESHOLD"          # market-sentiment alerts (and, before signals v2, asset scores)
BEARISH = "BEARISH_THRESHOLD"
HELD_BULLISH = "BULLISH_THRESHOLD_HELD"
HELD_BEARISH = "BEARISH_THRESHOLD_HELD"
# Signals v2: asset alerts follow the Trend reading (-100..100). Separate types, so a v1 score latch or
# threshold can never act on a v2 reading.
TREND_UP = "TREND_UP"
TREND_DOWN = "TREND_DOWN"
HELD_TREND_UP = "TREND_UP_HELD"
HELD_TREND_DOWN = "TREND_DOWN_HELD"
_HELD = {
    BULLISH: HELD_BULLISH,
    BEARISH: HELD_BEARISH,
    TREND_UP: HELD_TREND_UP,
    TREND_DOWN: HELD_TREND_DOWN,
}
OPEN_TYPES = [BULLISH, BEARISH, TREND_UP, TREND_DOWN]
LATCH_TYPES = OPEN_TYPES + [HELD_BULLISH, HELD_BEARISH, HELD_TREND_UP, HELD_TREND_DOWN]
# How far back through the line the score must travel before that alert can arm again.
_REARM_POINTS = 10.0
TREND_LEVEL_DEFAULT = 50.0     # signals_v2.TREND_ALERT_DEFAULT
TREND_REARM = 20.0             # signals_v2.TREND_ALERT_REARM

# Whole-market sentiment alerts are stored like asset alerts, under these symbols.
MARKET_PREFIX = "market:"
MARKET_NAMES = {
    "crypto": "🪙 Crypto market sentiment",
    "stock": "📈 Stock market sentiment",
}


def is_market_symbol(symbol) -> bool:
    return str(symbol or "").strip().lower().startswith(MARKET_PREFIX)


def asset_message(score: float, alert_type: str) -> str:
    if alert_type == BULLISH:
        return f"Score reached {score:.1f}/100 (strongly positive reading)"
    return f"Score dropped to {score:.1f}/100 (strongly negative reading)"


def trend_message(value: float, alert_type: str) -> str:
    if alert_type == TREND_UP:
        return f"Trend turned up: {value:+.0f} on the -100 to +100 Trend reading (a description, not a forecast)"
    return f"Trend turned down: {value:+.0f} on the -100 to +100 Trend reading (a description, not a forecast)"


def market_message(score: float, alert_type: str) -> str:
    if alert_type == BULLISH:
        return f"Market sentiment reached {score:.0f}/100 (strongly positive mood)"
    return f"Market sentiment dropped to {score:.0f}/100 (strongly negative mood)"


def market_rows(scores: dict, markets) -> list[dict]:
    """Rows for plan_alert_actions, one per market this account follows that has a score."""
    rows = []
    for market in markets or []:
        score = (scores or {}).get(market)
        if market in MARKET_NAMES and not _missing(score):
            rows.append({"key": MARKET_PREFIX + market, "symbol": MARKET_NAMES[market], "score": float(score)})
    return rows


def latch_symbol(symbol: str) -> str:
    """One latch identity for an asset, whatever case the watchlist used."""
    return " ".join(str(symbol or "").split()).lower()


def canonical_alert(alert_type: str) -> str:
    """The open crossing a row represents, including one hidden after it was cleared."""
    for open_type, held_type in _HELD.items():
        if alert_type in (open_type, held_type):
            return open_type
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


def plan_alert_actions(results, latched, min_thresh, max_thresh, describe=None, field="score",
                       types=(BULLISH, BEARISH), rearm=_REARM_POINTS):
    """
    Decide which latches to release and which alerts to open.

    field names the value each row is judged on ("score" for market sentiment, "trend" for assets);
    types are the (high, low) alert types; rearm is how far back through the line a value must travel.

    latched is a set of (symbol, alert_type). Each action is
    ("resolve", symbol, alert_type) or
    ("open", symbol, name, alert_type, message).
    """
    describe = describe or asset_message
    high_type, low_type = types
    actions = []
    held = set(latched)
    bullish_clear = min_thresh - rearm
    bearish_clear = max_thresh + rearm
    if bullish_clear < max_thresh:
        bullish_clear = max_thresh
    if bearish_clear > min_thresh:
        bearish_clear = min_thresh

    for row in results:
        score = row.get(field)
        if _missing(score):
            continue
        score = float(score)
        symbol = latch_symbol(row.get("key"))
        if not symbol:
            continue
        name = row.get("symbol") or symbol

        bullish = score >= min_thresh
        bearish = score <= max_thresh

        if score <= bullish_clear and (symbol, high_type) in held:
            actions.append(("resolve", symbol, high_type))
            held.discard((symbol, high_type))
        if score >= bearish_clear and (symbol, low_type) in held:
            actions.append(("resolve", symbol, low_type))
            held.discard((symbol, low_type))

        if bullish and (symbol, high_type) not in held:
            actions.append(("open", symbol, name, high_type, describe(score, high_type)))
            held.add((symbol, high_type))
        elif bearish and (symbol, low_type) not in held:
            actions.append(("open", symbol, name, low_type, describe(score, low_type)))
            held.add((symbol, low_type))

    return actions


def evaluate_alerts(supabase, user_id, results, alerts_config, notify_email=None, send_email=None, markets=None):
    """
    Apply plan_alert_actions for one user: asset scores against the asset lines and,
    when switched on, market sentiment rows (see market_rows) against the market lines.

    send_email(to_email, asset_name, message) runs once for each open crossing
    that has not been emailed yet. It does not run again while the score stays
    past the threshold.
    Returns the opened alert rows.
    """
    if not alerts_config:
        return []
    assets_on = alerts_config.get("enabled", True) is not False
    markets_on = bool(alerts_config.get("market_alerts_enabled")) and bool(markets)
    if not assets_on and not markets_on:
        return []

    # Asset alerts follow the v2 Trend reading. The old 0-100 score lines (min/max_score_alert) are not used.
    try:
        trend_level = abs(float(alerts_config.get("trend_alert_level") or TREND_LEVEL_DEFAULT))
    except (TypeError, ValueError):
        trend_level = TREND_LEVEL_DEFAULT
    trend_level = min(95.0, max(10.0, trend_level))
    market_high = float(alerts_config.get("market_high_alert") or 65)
    market_low = float(alerts_config.get("market_low_alert") or 35)

    existing = (
        supabase.table("user_notifications")
        .select("asset_symbol, alert_type")
        .eq("user_id", user_id)
        .in_("alert_type", LATCH_TYPES)
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

    actions = []
    if assets_on:
        actions += plan_alert_actions(results, latched, trend_level, -trend_level, describe=trend_message,
                                      field="trend", types=(TREND_UP, TREND_DOWN), rearm=TREND_REARM)
    if markets_on:
        actions += plan_alert_actions(markets, latched, market_high, market_low, describe=market_message)
    for action in actions:
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
        _email_open_crossings(
            supabase, user_id, notify_email, send_email, logos_by_symbol(results), facts_by_symbol(results),
        )

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


def price_text(value) -> str:
    """A price at a sensible precision: 403.30, 67,250, 0.8826, 0.00001234."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number != number or number <= 0:
        return ""
    if number >= 1000:
        return f"{number:,.0f}"
    if number >= 1:
        return f"{number:,.2f}"
    return f"{number:.4g}"


def asset_facts(row: dict) -> str:
    """One line of context for an alert: price, the asset's own sentiment and its market's mood."""
    parts = []
    price = price_text(row.get("price"))
    if price:
        parts.append(f"Price {price}")
    if not _missing(row.get("sentiment")):
        parts.append(f"Sentiment {float(row['sentiment']):.0f}/100")
    if not _missing(row.get("market_score")):
        name = "Crypto market" if row.get("market") == "crypto" else "Stock market"
        parts.append(f"{name} mood {float(row['market_score']):.0f}/100")
    return " · ".join(parts)


def facts_by_symbol(results) -> dict[str, str]:
    """asset_facts for each scored asset, keyed the way alert rows store the asset."""
    facts = {}
    for row in results or []:
        symbol = latch_symbol(row.get("key"))
        line = asset_facts(row)
        if symbol and line:
            facts[symbol] = line
    return facts


def _email_open_crossings(supabase, user_id, notify_email, send_email, logos=None, facts=None) -> None:
    """Email each unresolved crossing once. A later run skips rows already marked."""
    logos = logos or {}
    facts = facts or {}
    try:
        pending = (
            supabase.table("user_notifications")
            .select("id, asset_symbol, asset_name, message")
            .eq("user_id", user_id)
            .in_("alert_type", LATCH_TYPES)
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
        symbol = latch_symbol(note.get("asset_symbol"))
        extras = {}
        if logos.get(symbol):
            extras["logo_url"] = logos[symbol]
        if facts.get(symbol):
            extras["facts"] = facts[symbol]
        try:
            sent = bool(send_email(notify_email, name, note.get("message") or "", **extras))
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
        .not_.in_("alert_type", [HELD_BULLISH, HELD_BEARISH, HELD_TREND_UP, HELD_TREND_DOWN,
                                 "moderation_warning", "report_update"])
        .execute()
    )
