"""Shared prices and headline scores, one row per asset.

Every account reads the same row. The dashboard and the alert worker both
write the recent closes. The dashboard writes the sentiment score after Grok
runs, and later accounts reuse it for 12 hours.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from sentiment import SENTIMENT_REFRESH_SECONDS

SPARKLINE_POINTS = 30
_WARNED = False


def asset_market_key(kind: str, asset_id: str) -> str:
    """Stable id for one crypto or stock, shared by every account."""
    identity = str(asset_id or "").strip()
    if str(kind) == "Stock":
        identity = identity.upper()
    else:
        identity = identity.lower()
    return f"{kind}|{identity}"


def recent_closes(values, limit: int = SPARKLINE_POINTS) -> list[float]:
    """Last daily closes, oldest first. Skips blanks."""
    if isinstance(values, str):
        try:
            values = json.loads(values)
        except json.JSONDecodeError:
            return []
    try:
        sequence = list(values or [])
    except TypeError:
        return []
    cleaned = []
    for value in sequence:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number:
            cleaned.append(round(number, 6))
    return cleaned[-limit:]


def holder_counts(supabase) -> dict[str, int]:
    """Accounts holding each asset. Empty when the count function is not installed yet."""
    try:
        response = supabase.rpc("asset_holder_counts").execute()
    except Exception as exc:
        _warn(exc)
        return {}
    counts = {}
    for row in response.data or []:
        key = row.get("asset_key")
        try:
            number = int(row.get("holders") or 0)
        except (TypeError, ValueError):
            continue
        if key and number > 0:
            counts[str(key)] = number
    return counts


def holders_mark(count) -> str:
    """Overlapping people and a number. A dash when the count is unknown."""
    try:
        number = int(count)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        return "<span style='color:#6b7280;'>—</span>"
    person = (
        "<svg width='14' height='14' viewBox='0 0 16 16' aria-hidden='true'>"
        "<circle cx='8' cy='5' r='2.3' fill='#4338ca'/>"
        "<path d='M3.2 13.4c.7-2.5 2.4-3.7 4.8-3.7s4.1 1.2 4.8 3.7' fill='#4338ca'/>"
        "</svg>"
    )
    faces = []
    for index in range(min(number, 3)):
        shift = "margin-left:-7px;" if index else ""
        faces.append(
            "<span style='width:18px;height:18px;border-radius:999px;background:#e0e7ff;"
            "display:inline-flex;align-items:center;justify-content:center;"
            f"border:1.5px solid #ffffff;{shift}'>{person}</span>"
        )
    label = "1 account holds this" if number == 1 else f"{number} accounts hold this"
    return (
        f"<span title='{label}' style='display:inline-flex;align-items:center;gap:6px;'>"
        f"<span style='display:inline-flex;align-items:center;'>{''.join(faces)}</span>"
        f"<span style='font-weight:650;color:#312e81;'>{number}</span></span>"
    )


def sparkline_svg(closes) -> str:
    """A short line for one table row. Green when the stretch rose, red when it fell."""
    values = recent_closes(closes, SPARKLINE_POINTS)
    if len(values) < 2:
        return "<span style='color:#6b7280;'>—</span>"
    width, height, pad = 76, 26, 2
    low, high = min(values), max(values)
    span = high - low or 1.0
    last = len(values) - 1
    points = []
    for index, value in enumerate(values):
        x = pad + (width - 2 * pad) * (index / last)
        y = pad + (height - 2 * pad) * (1 - (value - low) / span)
        points.append(f"{x:.1f},{y:.1f}")
    if values[-1] > values[0]:
        color = "#15803d"
    elif values[-1] < values[0]:
        color = "#b91c1c"
    else:
        color = "#6b7280"
    return (
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' "
        "aria-hidden='true' style='display:block;margin-left:auto;'>"
        f"<polyline fill='none' stroke='{color}' stroke-width='1.6' "
        f"stroke-linejoin='round' stroke-linecap='round' points='{' '.join(points)}'/>"
        "</svg>"
    )


def _warn(exc: Exception) -> None:
    global _WARNED
    if _WARNED:
        return
    _WARNED = True
    print(
        "Shared market data was not stored. Run supabase_rls.sql in the Supabase "
        f"SQL editor. {exc}"
    )


def _canonical_id(kind: str, asset_id: str) -> str:
    identity = str(asset_id or "").strip()
    return identity.upper() if str(kind) == "Stock" else identity.lower()


def save_price_paths(supabase, rows: list[dict]) -> None:
    """Store the recent closes for each asset. Leaves a saved sentiment score in place."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {}
    for row in rows:
        closes = recent_closes(row.get("closes") or [])
        if len(closes) < 2:
            continue
        kind = row.get("kind") or "Crypto"
        asset_id = _canonical_id(kind, row.get("asset_id") or "")
        if not asset_id:
            continue
        key = asset_market_key(kind, asset_id)
        payload[key] = {
            "asset_key": key,
            "kind": kind,
            "asset_id": asset_id,
            "closes": closes,
            "closes_updated_at": now,
        }
    if not payload:
        return
    payload = list(payload.values())
    try:
        supabase.table("asset_market").upsert(payload, on_conflict="asset_key").execute()
    except Exception as exc:
        _warn(exc)


def save_logos(supabase, rows: list[dict]) -> None:
    """Store one logo address per asset. Leaves prices and sentiment in place."""
    payload = {}
    for row in rows:
        url = str(row.get("logo_url") or "").strip()
        if not url.startswith("https://"):
            continue
        kind = row.get("kind") or "Crypto"
        asset_id = _canonical_id(kind, row.get("asset_id") or "")
        if not asset_id:
            continue
        key = asset_market_key(kind, asset_id)
        payload[key] = {
            "asset_key": key,
            "kind": kind,
            "asset_id": asset_id,
            "logo_url": url,
        }
    if not payload:
        return
    try:
        supabase.table("asset_market").upsert(list(payload.values()), on_conflict="asset_key").execute()
    except Exception as exc:
        _warn(exc)


def asset_logo(url, label: str) -> str:
    """Round logo. A letter shows until the picture loads, and if it never does."""
    letter = next((ch.upper() for ch in str(label or "") if ch.isalnum()), "•")
    mark = (
        "<span style='width:22px;height:22px;border-radius:999px;background:#eef2ff;"
        "color:#3730a3;font-size:11px;font-weight:700;display:inline-flex;"
        "align-items:center;justify-content:center;flex:none;overflow:hidden;'>"
        f"{html.escape(letter)}</span>"
    )
    cleaned = str(url or "").strip() if isinstance(url, str) else ""
    if (
        not cleaned.startswith("https://")
        or len(cleaned) > 500
        or any(mark_char in cleaned for mark_char in (" ", '"', "'", "<", ">", "\\"))
    ):
        return mark
    safe = html.escape(cleaned, quote=True)
    return (
        "<span style='position:relative;width:22px;height:22px;flex:none;display:inline-flex;'>"
        f"{mark}"
        f"<img src='{safe}' alt='' width='22' height='22' "
        "style='position:absolute;inset:0;width:22px;height:22px;border-radius:999px;"
        "object-fit:cover;background:#ffffff;' onerror='this.remove()'>"
        "</span>"
    )


def save_sentiment(supabase, kind: str, asset_id: str, report: dict, stored_at: float) -> None:
    """Store one headline score so every account can show it."""
    if not isinstance(report, dict) or not report.get("ok"):
        return
    try:
        score = float(report.get("score"))
    except (TypeError, ValueError):
        return
    if score != score:
        return
    identity = _canonical_id(kind, asset_id)
    if not identity:
        return
    payload = {
        "asset_key": asset_market_key(kind, identity),
        "kind": kind,
        "asset_id": identity,
        "sentiment_score": score,
        "sentiment_report": report,
        "sentiment_updated_at": datetime.fromtimestamp(stored_at, timezone.utc).isoformat(),
    }
    try:
        supabase.table("asset_market").upsert(payload, on_conflict="asset_key").execute()
    except Exception as exc:
        _warn(exc)


def load_shared_market(supabase, keys: list[str]) -> dict[str, dict]:
    """Rows already stored for these assets. Empty when the table is not there yet."""
    wanted = [key for key in keys if key]
    if not wanted:
        return {}
    try:
        response = (
            supabase.table("asset_market")
            .select("asset_key, closes, logo_url, sentiment_report, sentiment_updated_at")
            .in_("asset_key", wanted)
            .execute()
        )
    except Exception as exc:
        _warn(exc)
        return {}
    return {row["asset_key"]: row for row in (response.data or []) if row.get("asset_key")}


def _stored_at(value) -> float | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.timestamp()


def sentiment_from_row(row: dict | None) -> tuple[dict | None, float | None]:
    """The shared headline report, while it is still inside the 12-hour window."""
    if not row:
        return None, None
    stored_at = _stored_at(row.get("sentiment_updated_at"))
    if stored_at is None or _age_expired(stored_at):
        return None, None
    report = row.get("sentiment_report")
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except json.JSONDecodeError:
            return None, None
    if not isinstance(report, dict) or not report.get("ok"):
        return None, None
    return report, stored_at


def _age_expired(stored_at: float) -> bool:
    return datetime.now(timezone.utc).timestamp() - stored_at >= SENTIMENT_REFRESH_SECONDS
