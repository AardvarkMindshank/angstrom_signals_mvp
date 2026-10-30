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

from alerts import BEARISH, BULLISH, HELD_BEARISH, HELD_BULLISH, asset_facts, facts_by_symbol, is_market_symbol, latch_symbol, logos_by_symbol, price_text
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


WATCHLIST_SHOWN = 10   # assets in the watchlist summary, split across crypto and stocks

_GREEN, _GREEN_SOFT, _GREEN_BG = "#0f9d46", "#7cd39b", "#dcfce7"
_RED, _RED_SOFT, _RED_BG = "#c0392b", "#f0a29a", "#fde2e0"
_AMBER = "#f2a33a"   # neutral middle scores
_GREY, _GREY_BG, _TRACK = "#64748b", "#eef1f6", "#e3e8f0"
_INK, _MUTED, _PAPER, _RULE = "#0c1b3a", "#4a5876", "#f7f9fc", "#d5dce8"
_FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def watchlist_on(config: dict) -> bool:
    """The watchlist summary is on unless switched off (a missing column counts as on)."""
    return (config or {}).get("digest_watchlist") is not False


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def score_colour(score, high=70.0, low=30.0) -> str:
    """Strong green at or above the positive line, strong red at or below the negative one, softer near them,
    amber in the neutral middle (above 45 and below 55)."""
    if score is None:
        return _GREY
    if score >= high:
        return _GREEN
    if score >= 55:
        return _GREEN_SOFT
    if score <= low:
        return _RED
    if score <= 45:
        return _RED_SOFT
    return _AMBER


def _mood_colour(value) -> tuple[str, str]:
    """(text, background) for a 0-100 sentiment reading."""
    if value is None:
        return _GREY, _GREY_BG
    if value >= 60:
        return _GREEN, _GREEN_BG
    if value <= 40:
        return _RED, _RED_BG
    return _GREY, _GREY_BG


def _pill(text: str, colour: str, background: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:999px;background:{background};'
        f'color:{colour};font:700 13px/1.5 {_FONT};white-space:nowrap;">{text}</span>'
    )


def change_pill(change) -> str:
    if change is None:
        return ""
    if change >= 0.0005:
        return _pill(f"&#9650; {change * 100:.1f}%", _GREEN, _GREEN_BG)
    if change <= -0.0005:
        return _pill(f"&#9660; {abs(change) * 100:.1f}%", _RED, _RED_BG)
    return _pill("0.0%", _GREY, _GREY_BG)


def score_bar(score, high=70.0, low=30.0) -> str:
    """A small 0-100 bar, drawn with a table so it shows in Outlook as well."""
    if score is None:
        return ""
    filled = max(2, min(100, int(round(score))))
    colour = score_colour(score, high, low)
    rest = (
        f'<td width="{100 - filled}" style="width:{100 - filled}px;background:{_TRACK};font-size:0;line-height:0;">&nbsp;</td>'
        if filled < 100 else ""
    )
    return (
        '<table role="presentation" cellspacing="0" cellpadding="0" '
        'style="display:inline-table;vertical-align:middle;border-collapse:collapse;border-radius:4px;overflow:hidden;">'
        f'<tr style="height:8px;"><td width="{filled}" style="width:{filled}px;background:{colour};font-size:0;line-height:0;">&nbsp;</td>'
        f'{rest}</tr></table>'
    )


def pick_watchlist(results, limit: int = WATCHLIST_SHOWN) -> list[tuple[str, list[dict], int]]:
    """[(market, rows to show strongest first, how many that market has)] for crypto then stocks.

    The limit is shared between the markets present. A market with more assets than its share shows
    its strongest and weakest, with the strongest getting the extra one."""
    groups = {}
    for row in results or []:
        if _number(row.get("score")) is None:
            continue
        groups.setdefault(row.get("market") or "crypto", []).append(row)
    present = [m for m in ("crypto", "stock") if m in groups] + [m for m in groups if m not in ("crypto", "stock")]
    if not present:
        return []
    share = max(2, limit // len(present))
    picked = []
    for market in present:
        rows = sorted(groups[market], key=lambda r: _number(r.get("score")), reverse=True)
        if len(rows) > share:
            top = (share + 1) // 2
            rows = rows[:top] + rows[-(share - top):]
        picked.append((market, rows, len(groups[market])))
    return picked


def _watchlist_row(row: dict, high: float, low: float) -> tuple[str, str]:
    name = " ".join(str(row.get("symbol") or row.get("key") or "").split())
    score = _number(row.get("score"))
    price = price_text(row.get("price"))
    change = _number(row.get("change"))
    sentiment = _number(row.get("sentiment"))
    mood_text, mood_bg = _mood_colour(sentiment)
    sentiment_html = (
        f'<span style="font:400 13px/1.5 {_FONT};color:{_MUTED};">Sentiment</span> '
        + _pill(f"{sentiment:.0f}", mood_text, mood_bg)
        if sentiment is not None else ""
    )
    html_row = (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        f'style="margin:0 0 6px;background:{_PAPER};border-radius:6px;border-left:4px solid {score_colour(score, high, low)};">'
        f'<tr><td style="padding:8px 12px 2px;font:700 15px/1.4 {_FONT};color:{_INK};">'
        f'{asset_logo(row.get("logo") or "")}{html.escape(name)}</td>'
        f'<td align="right" style="padding:8px 12px 2px;font:600 15px/1.4 {_FONT};color:{_INK};white-space:nowrap;">'
        f'{html.escape(price)} {change_pill(change)}</td></tr>'
        f'<tr><td colspan="2" style="padding:2px 12px 9px;font:400 13px/1.5 {_FONT};color:{_MUTED};">'
        f'Score {score_bar(score, high, low)} <strong style="color:{_INK};">{score:.0f}</strong>'
        + (f' &nbsp;&middot;&nbsp; {sentiment_html}' if sentiment_html else "")
        + '</td></tr></table>'
    )
    parts = [f"score {score:.0f}"]
    if price:
        parts.insert(0, price + (f" ({change * 100:+.1f}%)" if change is not None else ""))
    if sentiment is not None:
        parts.append(f"sentiment {sentiment:.0f}")
    return html_row, f"- {name}: " + " · ".join(parts)


def _watchlist_section(results, config) -> tuple[str, str]:
    high = _number(config.get("min_score_alert")) or 70.0
    low = _number(config.get("max_score_alert")) or 30.0
    html_parts, plain = [], []
    for market, rows, total in pick_watchlist(results):
        title = "&#129689; Crypto" if market == "crypto" else "&#128200; Stocks"
        mood = _number(rows[0].get("market_score")) if rows else None
        mood_html = ""
        if mood is not None:
            text, bg = _mood_colour(mood)
            mood_html = (
                f'<span style="font:400 13px/1.5 {_FONT};color:{_MUTED};">Market mood</span> '
                + _pill(f"{mood:.0f}", text, bg)
            )
        html_parts.append(
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:14px 0 6px;"><tr>'
            f'<td style="font:800 16px/1.4 {_FONT};color:{_INK};">{title}</td>'
            f'<td align="right">{mood_html}</td></tr></table>'
        )
        label = "Crypto" if market == "crypto" else "Stocks"
        plain.append(label + (f" (market mood {mood:.0f})" if mood is not None else ""))
        for row in rows:
            row_html, row_plain = _watchlist_row(row, high, low)
            html_parts.append(row_html)
            plain.append(row_plain)
        if total > len(rows):
            top = (len(rows) + 1) // 2
            note = f"Your {top} strongest and {len(rows) - top} weakest of {total}. The rest are on the dashboard."
            html_parts.append(f'<p style="margin:2px 0 4px;font:400 12px/1.5 {_FONT};color:{_MUTED};">{note}</p>')
            plain.append(note)
        plain.append("")
    return "".join(html_parts), "\n".join(plain)


def render_digest(notes, results, config, app_url: str, markets=None) -> tuple[str, str, str]:
    """(subject, html, plain text). The alerts that crossed come first; then, if switched on,
    a colour-coded summary of the watchlist. markets: current market sentiment rows."""
    zone = safe_zone(config.get("digest_tz"))
    market_notes = [note for note in notes if is_market_symbol(note.get("asset_symbol"))]
    asset_notes = [note for note in notes if not is_market_symbol(note.get("asset_symbol"))]
    up, down = split_crossings(asset_notes)
    market_up, market_down = split_crossings(market_notes)
    total = len(up) + len(down) + len(market_up) + len(market_down)
    plural = "" if total == 1 else "s"
    with_watchlist = watchlist_on(config) and bool(results)
    if total:
        subject = f"Angstrom daily summary: {total} alert{plural}"
    else:
        subject = "Angstrom daily summary: no new alerts"

    html_parts: list[str] = []
    plain: list[str] = []
    # Logos come with the current scores; alert rows only carry the asset.
    logo_for_symbol = logos_by_symbol(results)
    facts_for_symbol = facts_by_symbol(results)
    facts_for_name = {
        str(row.get("symbol") or row.get("key") or ""): asset_facts(row) for row in results or []
    }
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
            symbol = latch_symbol(note.get("asset_symbol"))
            facts = facts_for_symbol.get(symbol) or facts_for_name.get(name, "")
            detail = html.escape(message) + (f" · {html.escape(when)}" if when else "")
            if facts:
                detail += "<br>Now: " + html.escape(facts)
            logo = logo_for_symbol.get(symbol) or logo_for_name.get(name, "")
            html_parts.append(list_row(asset_logo(logo) + html.escape(name), detail, tone))
            plain.append(f"- {name}: {message}" + (f" ({when})" if when else "") + (f". Now: {facts}" if facts else ""))
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
    if not asset_notes and config.get("enabled", True) is not False:
        html_parts.append(
            f'<p style="margin:8px 0 0;font:400 15px/1.5 {_FONT};color:{_MUTED};">'
            "No asset scores crossed your alert lines since the last summary.</p>"
        )
        plain += ["No asset scores crossed your alert lines since the last summary.", ""]

    if with_watchlist:
        section_html, section_plain = _watchlist_section(results, config)
        if section_html:
            html_parts.append(f'<hr style="border:none;border-top:2px solid {_RULE};margin:22px 0 4px;">')
            html_parts.append(section_title("Your watchlist today"))
            html_parts.append(section_html)
            plain += ["----------------------------------------", "Your watchlist today", section_plain]

    hour = digest_hour(config)
    zone_name = str(config.get("digest_tz") or DEFAULT_ZONE)
    when_sent = (
        f"Sent every day at {hour:02d}:00 ({html.escape(zone_name)})."
        if watchlist_on(config) else
        f"Sent once a day at {hour:02d}:00 ({html.escape(zone_name)}), and only on days with at least one alert."
    )
    page, text = render_email(
        f"Your daily summary: {total} alert{plural}" if total else "Your daily summary",
        [
            "What crossed your alert lines since your last summary"
            + (", then how your watchlist looks today." if with_watchlist else ".")
            + " Scores describe current conditions and are not forecasts.",
        ],
        button=("Open the dashboard", app_url),
        footnote=when_sent + " Change this under Configure Alert Rules.",
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

    if not notes and not (watchlist_on(config) and results):
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
        if notes:
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
