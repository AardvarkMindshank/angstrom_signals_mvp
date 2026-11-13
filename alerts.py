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

from score_colours import sentiment_text

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
# Optional alerts on the other two readings (off unless the account switches them on).
STRETCH_UP = "STRETCH_UP"
STRETCH_DOWN = "STRETCH_DOWN"
FLOW_UP = "FLOW_UP"
FLOW_DOWN = "FLOW_DOWN"
_HELD = {
    BULLISH: HELD_BULLISH,
    BEARISH: HELD_BEARISH,
    TREND_UP: HELD_TREND_UP,
    TREND_DOWN: HELD_TREND_DOWN,
    STRETCH_UP: STRETCH_UP + "_HELD",
    STRETCH_DOWN: STRETCH_DOWN + "_HELD",
    FLOW_UP: FLOW_UP + "_HELD",
    FLOW_DOWN: FLOW_DOWN + "_HELD",
}
OPEN_TYPES = list(_HELD)
HELD_TYPES = list(_HELD.values())
LATCH_TYPES = OPEN_TYPES + HELD_TYPES
UP_TYPES = (BULLISH, TREND_UP, STRETCH_UP, FLOW_UP)
DOWN_TYPES = (BEARISH, TREND_DOWN, STRETCH_DOWN, FLOW_DOWN)
# How far back through the line the score must travel before that alert can arm again.
_REARM_POINTS = 10.0
TREND_LEVEL_DEFAULT = 50.0     # signals_v2.TREND_ALERT_DEFAULT
TREND_REARM = 20.0             # signals_v2.TREND_ALERT_REARM

# One entry per reading that can alert. "on" is the alerts_config key that switches it on (Trend uses the
# account's main asset-alert switch, "enabled", on by default); "level" is the +/- line; "start" is the
# marker symbol that records the silent first run for that reading.
READING_ALERTS = {
    "trend": {"types": (TREND_UP, TREND_DOWN), "on": "enabled", "on_default": True,
              "level": "trend_alert_level", "default": TREND_LEVEL_DEFAULT, "start": "signals:v2-start",
              "name": "Trend"},
    "stretch": {"types": (STRETCH_UP, STRETCH_DOWN), "on": "stretch_alert_on", "on_default": False,
                "level": "stretch_alert_level", "default": 65.0, "start": "signals:start:stretch",
                "name": "Stretch"},
    "flow": {"types": (FLOW_UP, FLOW_DOWN), "on": "flow_alert_on", "on_default": False,
             "level": "flow_alert_level", "default": 40.0, "start": "signals:start:flow",
             "name": "Flow"},
}
READING_REARM = TREND_REARM

# ------------------------------------------------------------------------------- border-crossing alerts (13 Nov 2026)
# An alert when a reading crosses one of the colour borders the tables show (-50, -20, +20, +50), in the directions
# the account ticks, once the new colour holds at the next daily close (research/alerts_replay.md). A jump from one
# side straight to the other between two closes is one "flip" alert. Zones: -2 strongly bearish .. +2 strongly bullish.
BORDERS = (("m50", -50), ("m20", -20), ("p20", 20), ("p50", 50))      # border i sits between zone i-2 and i-1
CROSSINGS = {   # key: (border, direction, plain words)
    "up_p50": ("p50", 1, "gets strongly bullish"),
    "dn_p50": ("p50", -1, "fades back from strongly bullish"),
    "up_p20": ("p20", 1, "turns bullish (leaves neutral)"),
    "dn_p20": ("p20", -1, "falls back into neutral"),
    "up_m20": ("m20", 1, "rises back into neutral"),
    "dn_m20": ("m20", -1, "turns bearish (leaves neutral)"),
    "up_m50": ("m50", 1, "fades back from strongly bearish"),
    "dn_m50": ("m50", -1, "gets strongly bearish"),
    "flip_up": (None, 1, "flips from bearish to bullish"),
    "flip_dn": (None, -1, "flips from bullish to bearish"),
}
DEFAULT_CROSSINGS = {
    "trend": ("up_p20", "dn_m20", "up_p50", "dn_m50", "flip_up", "flip_dn"),
    "stretch": ("up_p50", "dn_m50", "dn_p50", "up_m50"),
    "flow": ("up_p20", "dn_m20", "flip_up", "flip_dn"),
}
SETTINGS_KEYS = ("trend_alert_level", "stretch_alert_on", "stretch_alert_level", "flow_alert_on", "flow_alert_level",
                 "trend_crossings", "stretch_crossings", "flow_crossings")


def zone(value) -> int | None:
    """The colour zone of a -100..+100 reading, as the tables colour it: -2 .. +2 (None: no reading)."""
    from score_colours import reading_step

    return {"strong_up": 2, "up": 1, "mixed": 0, "down": -1, "strong_down": -2}.get(reading_step(value))


def reading_crossings(alerts_config: dict, reading: str) -> list[str]:
    """The crossings this account ticked for a reading (its saved list, else the defaults)."""
    saved = (alerts_config or {}).get(f"{reading}_crossings")
    if isinstance(saved, (list, tuple)):
        return [k for k in saved if k in CROSSINGS]
    return list(DEFAULT_CROSSINGS[reading])


def crossing_for(before: int | None, after: int | None, ticked) -> str | None:
    """The one alert for a move from zone `before` to zone `after`, or None. A flip (one side straight to the other)
    is its own alert when ticked; otherwise the ticked border furthest along the move speaks for it."""
    if before is None or after is None or before == after:
        return None
    up = after > before
    ticked = set(ticked or ())
    if (before <= -1 and after >= 1) or (before >= 1 and after <= -1):
        flip = "flip_up" if up else "flip_dn"
        if flip in ticked:
            return flip
    # border i lies between zone i-2 and zone i-1: crossed going up when before <= i-2 < after
    crossed = [name for i, (name, _) in enumerate(BORDERS) if min(before, after) <= i - 2 < max(before, after)]
    if not up:
        crossed.reverse()
    keys = [("up_" if up else "dn_") + name for name in crossed]
    chosen = [k for k in keys if k in ticked]
    return chosen[-1] if chosen else None


def crossing_message(reading: str, key: str, value: float, before: int, after: int) -> str:
    """'Trend gets strongly bullish: +56 (Strong uptrend), was Uptrend.'"""
    import signals_v2

    words = signals_v2.CLUSTER_WORDS[reading]            # strongest up first
    name = READING_ALERTS[reading]["name"]
    return (f"{name} {CROSSINGS[key][2]}: {value:+.0f} ({words[2 - after]}), was {words[2 - before].lower()}. "
            "Readings describe conditions, not forecasts.")


def reading_alert_on(alerts_config: dict, reading: str) -> bool:
    spec = READING_ALERTS[reading]
    value = (alerts_config or {}).get(spec["on"])
    return spec["on_default"] if value is None else value is not False


def reading_alert_level(alerts_config: dict, reading: str) -> float:
    spec = READING_ALERTS[reading]
    try:
        level = abs(float((alerts_config or {}).get(spec["level"]) or spec["default"]))
    except (TypeError, ValueError):
        level = spec["default"]
    return min(95.0, max(10.0, level))

# Switching to signals v2: the first worker run for an account records which assets are already past the
# Trend line as silent latches (held, read, already emailed and digested), so the switch does not send a
# burst of "Trend turned up/down" alerts for positions that did not just cross. This marker row (a held
# latch on a symbol no asset uses) records that the start was done, so it happens once per account.
V2_START_SYMBOL = "signals:v2-start"


def silent_latch_row(user_id, symbol: str, name: str, alert_type: str, message: str, now_iso: str) -> dict:
    """A latch that nobody is told about: hidden from the feed, never emailed, never in a digest."""
    return {
        "user_id": user_id,
        "asset_symbol": symbol,
        "asset_name": name,
        "alert_type": _HELD.get(alert_type, alert_type),
        "message": message,
        "is_read": True,
        "emailed_at": now_iso,
        "digested_at": now_iso,
    }


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


_READING_WORDS = {
    TREND_UP: ("Trend turned up", "Trend", ""),
    TREND_DOWN: ("Trend turned down", "Trend", ""),
    STRETCH_UP: ("Stretched up", "Stretch", ": price has run up within its recent range"),
    STRETCH_DOWN: ("Stretched down", "Stretch", ": price has run down within its recent range"),
    FLOW_UP: ("Flow turned up", "Flow", ": volume is backing rises"),
    FLOW_DOWN: ("Flow turned down", "Flow", ": volume is backing falls"),
}


def trend_message(value: float, alert_type: str) -> str:
    """The alert text for any of the three readings (named for the first one it served)."""
    title, reading, detail = _READING_WORDS[alert_type]
    return f"{title}: {value:+.0f} on the -100 to +100 {reading} reading{detail} (a description, not a forecast)"


reading_message = trend_message


def market_message(score: float, alert_type: str) -> str:
    if alert_type == BULLISH:
        return f"Market sentiment turned positive: {sentiment_text(score)} on the -100 to +100 scale (strongly positive mood)"
    return f"Market sentiment turned negative: {sentiment_text(score)} on the -100 to +100 scale (strongly negative mood)"


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
    readings_on = [r for r in READING_ALERTS if reading_alert_on(alerts_config, r)]
    assets_on = bool(readings_on)
    markets_on = bool(alerts_config.get("market_alerts_enabled")) and bool(markets)
    if not assets_on and not markets_on:
        return []

    # Asset alerts follow the Trend, Stretch and Flow readings (-100..+100), each with its own +/- line.
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
    reading_actions = {}
    for reading in readings_on:
        level = reading_alert_level(alerts_config, reading)
        reading_actions[reading] = plan_alert_actions(
            results, latched, level, -level, describe=reading_message, field=reading,
            types=READING_ALERTS[reading]["types"], rearm=READING_REARM,
        )
        actions += reading_actions[reading]
    if markets_on:
        actions += plan_alert_actions(markets, latched, market_high, market_low, describe=market_message)
    # The first run with a reading's alerts switched on latches its current positions silently instead of
    # alerting, so switching an alert on never sends a burst for positions that did not just cross.
    for reading in readings_on:
        spec = READING_ALERTS[reading]
        if any(symbol == spec["start"] for symbol, _kind in latched):
            continue
        now_iso = datetime.now(timezone.utc).isoformat()
        silent = [a for a in reading_actions[reading] if a[0] == "open"]
        rows = [silent_latch_row(user_id, a[1], a[2], a[3], a[4], now_iso) for a in silent]
        rows.append(silent_latch_row(user_id, spec["start"], f"{spec['name']} alerts start", spec["types"][0],
                                     f"{spec['name']} alerts started: current positions recorded without alerts.",
                                     now_iso))
        try:
            supabase.table("user_notifications").insert(rows).execute()
        except Exception:
            try:  # a database without the digest column
                supabase.table("user_notifications").insert(
                    [{k: v for k, v in r.items() if k != "digested_at"} for r in rows]).execute()
            except Exception as exc:
                print(f"{spec['name']} alerts start not recorded for {user_id}; trying again next run. {str(exc)[:120]}")
        # Never alert for these on this run, whether or not the start was recorded.
        actions = [a for a in actions if a not in silent]

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
        parts.append(f"Sentiment {sentiment_text(row['sentiment'])}")
    if not _missing(row.get("market_score")):
        name = "Crypto market" if row.get("market") == "crypto" else "Stock market"
        parts.append(f"{name} mood {sentiment_text(row['market_score'])}")
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
        .not_.in_("alert_type", HELD_TYPES + ["moderation_warning", "report_update"])
        .execute()
    )
