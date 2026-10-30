"""Daily digest: one email a day that gathers the alert crossings, instead of one email each.

The background worker calls send_due_digest for each user on every run. It decides
whether that user's digest is due, builds it, sends it and marks what it covered.
Instant emails and the digest use separate markers (emailed_at and digested_at),
so neither can send or hide the other's alerts.
"""

from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from alerts import BEARISH, BULLISH, HELD_BEARISH, HELD_BULLISH, is_market_symbol, latch_symbol, logos_by_symbol
from email_brand import asset_logo, list_row, render_email, section_title

# A crossing can be resolved (the score moved back) before the digest goes out.
# It still happened that day, so resolved rows are included.
CROSSING_TYPES = [
    BULLISH, BEARISH, HELD_BULLISH, HELD_BEARISH,
    f"{BULLISH}_resolved", f"{BEARISH}_resolved",
]
# Rows older than this are not worth reporting if a digest was missed for days.
LOOKBACK_HOURS = 48
DEFAULT_HOUR = 8
DEFAULT_ZONE = "UTC"
READINGS_SHOWN = 3

# A short list for the settings page. Any valid zone name in the database still works.
COMMON_ZONES = (
    "UTC", "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Madrid", "Europe/Rome",
    "Europe/Athens", "Europe/Moscow", "Africa/Cairo", "Africa/Johannesburg", "Asia/Dubai",
    "Asia/Karachi", "Asia/Kolkata", "Asia/Dhaka", "Asia/Bangkok", "Asia/Jakarta",
    "Asia/Singapore", "Asia/Hong_Kong", "Asia/Shanghai", "Asia/Manila", "Asia/Tokyo",
    "Asia/Seoul", "Australia/Perth", "Australia/Sydney", "Pacific/Auckland",
    "America/St_Johns", "America/Halifax", "America/New_York", "America/Chicago",
    "America/Denver", "America/Phoenix", "America/Los_Angeles", "America/Anchorage",
    "Pacific/Honolulu", "America/Mexico_City", "America/Bogota", "America/Sao_Paulo",
    "America/Argentina/Buenos_Aires",
)


def safe_zone(name) -> ZoneInfo:
    """The named time zone, or UTC when the name is empty or unknown."""
    try:
        return ZoneInfo(str(name or DEFAULT_ZONE))
    except Exception:
        return ZoneInfo(DEFAULT_ZONE)


def digest_hour(config: dict) -> int:
    try:
        hour = int(config.get("digest_hour"))
    except (TypeError, ValueError):
        return DEFAULT_HOUR
    return hour if 0 <= hour <= 23 else DEFAULT_HOUR


def _as_datetime(value):
    if isinstance(value, datetime):
        moment = value
    elif value:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def digest_due(config: dict, now_utc: datetime) -> str:
    """
    "off"   the digest is not switched on
    "start" switched on but never sent; the worker records now so the first one
            goes out at the next chosen hour
    "wait"  nothing due yet
    "send"  the chosen hour has passed today and no digest has gone out since
    """
    if not config or not config.get("digest_enabled"):
        return "off"
    last = _as_datetime(config.get("last_digest_at"))
    if last is None:
        return "start"
    zone = safe_zone(config.get("digest_tz"))
    local_now = now_utc.astimezone(zone)
    slot = local_now.replace(hour=digest_hour(config), minute=0, second=0, microsecond=0)
    if local_now >= slot and last.astimezone(zone) < slot:
        return "send"
    return "wait"


def split_crossings(notes: list[dict]) -> tuple[list[dict], list[dict]]:
    """(turned positive, turned negative), oldest first."""
    up, down = [], []
    for note in sorted(notes, key=lambda n: str(n.get("created_at") or "")):
        kind = str(note.get("alert_type") or "")
        if kind.startswith(BULLISH):
            up.append(note)
        elif kind.startswith(BEARISH):
            down.append(note)
    return up, down


def strongest_and_weakest(results: list[dict], count: int = READINGS_SHOWN):
    """The highest and lowest current scores. Bad or missing scores are ignored."""
    scored = []
    for row in results or []:
        try:
            value = float(row.get("score"))
        except (TypeError, ValueError):
            continue
        if value != value:
            continue
        scored.append((value, str(row.get("symbol") or row.get("key") or "")))
    scored.sort(key=lambda item: item[0])
    weakest = scored[:count]
    strongest = list(reversed(scored[-count:])) if scored else []
    # With few assets the two lists would repeat each other.
    weakest = [item for item in weakest if item not in strongest]
    return strongest, weakest


def _local_time(note: dict, zone: ZoneInfo) -> str:
    moment = _as_datetime(note.get("created_at"))
    return moment.astimezone(zone).strftime("%H:%M") if moment else ""


def render_digest(notes, results, config, app_url: str, markets=None) -> tuple[str, str, str]:
    """(subject, html, plain text). markets: current market sentiment rows, shown when market alerts are on."""
    zone = safe_zone(config.get("digest_tz"))
    market_notes = [note for note in notes if is_market_symbol(note.get("asset_symbol"))]
    asset_notes = [note for note in notes if not is_market_symbol(note.get("asset_symbol"))]
    up, down = split_crossings(asset_notes)
    market_up, market_down = split_crossings(market_notes)
    total = len(up) + len(down) + len(market_up) + len(market_down)
    plural = "" if total == 1 else "s"
    subject = f"Angstrom daily digest: {total} alert{plural}"

    html_parts: list[str] = []
    plain: list[str] = []
    # Logos come with the current scores; alert rows only carry the asset.
    logo_for_symbol = logos_by_symbol(results)
    logo_for_name = {
        str(row.get("symbol") or row.get("key") or ""): str(row.get("logo") or "")
        for row in results or []
        if row.get("logo")
    }

    def crossing_rows(title: str, rows: list[dict], tone: str) -> None:
        if not rows:
            return
        html_parts.append(section_title(f"{html.escape(title)} ({len(rows)})"))
        plain.append(f"{title} ({len(rows)})")
        for note in rows:
            name = " ".join(str(note.get("asset_name") or "Asset").split())
            message = " ".join(str(note.get("message") or "").split())
            when = _local_time(note, zone)
            detail = html.escape(message) + (f" · {html.escape(when)}" if when else "")
            logo = logo_for_symbol.get(latch_symbol(note.get("asset_symbol"))) or logo_for_name.get(name, "")
            html_parts.append(list_row(asset_logo(logo) + html.escape(name), detail, tone))
            plain.append(f"- {name}: {message}" + (f" ({when})" if when else ""))
        plain.append("")

    readings = list(markets or []) if config.get("market_alerts_enabled") else []
    if market_notes or readings:
        html_parts.append(section_title("Market sentiment"))
        plain.append("Market sentiment")
        for note in market_up + market_down:
            name = " ".join(str(note.get("asset_name") or "Market").split())
            message = " ".join(str(note.get("message") or "").split())
            when = _local_time(note, zone)
            tone = "up" if note in market_up else "down"
            detail = html.escape(message) + (f" · {html.escape(when)}" if when else "")
            html_parts.append(list_row(html.escape(name), detail, tone))
            plain.append(f"- {name}: {message}" + (f" ({when})" if when else ""))
        crossed = {latch_symbol(note.get("asset_symbol")) for note in market_notes}
        for row in readings:
            if latch_symbol(row.get("key")) in crossed:
                continue
            name = str(row.get("symbol") or "")
            score = float(row.get("score"))
            html_parts.append(list_row(html.escape(name), f"Now {score:.0f}/100, no alert", "info"))
            plain.append(f"- {name}: now {score:.0f}/100, no alert")
        plain.append("")

    crossing_rows("Turned positive", up, "up")
    crossing_rows("Turned negative", down, "down")

    strongest, weakest = strongest_and_weakest(results)
    for title, rows, tone in (
        ("Strongest readings now", strongest, "up"),
        ("Weakest readings now", weakest, "down"),
    ):
        if not rows:
            continue
        html_parts.append(section_title(html.escape(title)))
        plain.append(title)
        for value, name in rows:
            html_parts.append(list_row(asset_logo(logo_for_name.get(name, "")) + html.escape(name), f"Score {value:.0f}", tone))
            plain.append(f"- {name}: score {value:.0f}")
        plain.append("")

    hour = digest_hour(config)
    zone_name = str(config.get("digest_tz") or DEFAULT_ZONE)
    page, text = render_email(
        f"Your daily digest: {total} alert{plural}",
        [
            "Here is what crossed your alert lines since your last digest. "
            "Scores describe current conditions and are not forecasts.",
        ],
        button=("Open the dashboard", app_url),
        footnote=(
            f"Sent once a day at {hour:02d}:00 ({html.escape(zone_name)}), and only on days "
            "with at least one alert. Change this under Configure Alert Rules."
        ),
        preheader=(
            f"{len(up)} turned positive, {len(down)} turned negative"
            + (f", {len(market_notes)} market sentiment" if market_notes else "")
        ),
        extra_html="".join(html_parts),
        extra_plain="\n".join(plain),
    )
    return subject, page, text


def _stamp(supabase, user_id: str, moment: datetime) -> None:
    (
        supabase.table("alert_preferences")
        .update({"last_digest_at": moment.isoformat()})
        .eq("user_id", user_id)
        .execute()
    )


def send_due_digest(
    supabase, user_id, config, results, notify_email, send_email, app_url, now=None, markets=None
) -> str:
    """
    Send this user's digest if it is due. send_email(to, subject, html, plain) -> bool.
    Returns "off", "wait", "start", "quiet" (due, nothing to report), "sent" or "error".
    """
    now = now or datetime.now(timezone.utc)
    state = digest_due(config, now)
    if state in ("off", "wait"):
        return state
    try:
        if state == "start":
            _stamp(supabase, user_id, now)
            return "start"
        if not notify_email:
            return "error"
        since = (now - timedelta(hours=LOOKBACK_HOURS)).isoformat()
        notes = (
            supabase.table("user_notifications")
            .select("id, asset_symbol, asset_name, message, alert_type, created_at")
            .eq("user_id", user_id)
            .in_("alert_type", CROSSING_TYPES)
            .is_("digested_at", "null")
            .gte("created_at", since)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(
            "Could not prepare the daily digest. Run the latest supabase_rls.sql "
            f"in the Supabase SQL editor. {exc}"
        )
        return "error"

    if not notes:
        # A quiet day. Record it so a crossing at 3pm waits for tomorrow's digest.
        try:
            _stamp(supabase, user_id, now)
        except Exception as exc:
            print(f"Digest day could not be recorded for {user_id}: {exc}")
        return "quiet"

    subject, page, plain = render_digest(notes, results, config, app_url, markets=markets)
    try:
        sent = bool(send_email(notify_email, subject, page, plain))
    except Exception as exc:
        print(f"Digest email failed for {user_id}: {exc}")
        return "error"
    if not sent:
        return "error"
    try:
        (
            supabase.table("user_notifications")
            .update({"digested_at": now.isoformat()})
            .in_("id", [note["id"] for note in notes])
            .execute()
        )
        _stamp(supabase, user_id, now)
    except Exception as exc:
        print(f"Digest was sent to {user_id} but could not be marked. {exc}")
    return "sent"
