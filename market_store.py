"""Shared prices and headline scores, one row per asset.

Every account reads the same row. The background worker replaces prices about
every 5 minutes and sentiment about every 12 hours. A session writes a row
only when that asset is not stored yet.
"""

from __future__ import annotations

import html
import json
import math
import re
from datetime import datetime, timezone

import pandas as pd

from sentiment import SENTIMENT_REFRESH_SECONDS, TECHNICAL_REFRESH_SECONDS

SPARKLINE_POINTS = 31
COMMENT_LIMIT = 160
COMMENT_EMOTICONS = ("😀", "🙂", "😐", "🙁", "😮", "🔥", "💩", "🚀", "📈", "📉")
_SIDEWAYS_PERCENT = 2.0
_WARNED = False
_AUTHOR_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


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


def sentiment_crowd(supabase, keys: list[str]) -> dict[str, dict]:
    """Agree and disagree counts for the current sentiment. Empty if the function is missing."""
    wanted = [key for key in keys if key]
    if not wanted:
        return {}
    try:
        response = supabase.rpc("sentiment_crowd", {"asset_keys": wanted}).execute()
    except Exception as exc:
        _warn(exc)
        return {}
    counts = {}
    for row in response.data or []:
        key = row.get("asset_key")
        if not key:
            continue
        try:
            mine = int(row.get("my_vote"))
        except (TypeError, ValueError):
            mine = None
        try:
            alt_count = int(row.get("alt_count") or 0)
        except (TypeError, ValueError):
            alt_count = 0
        counts[str(key)] = {
            "up": int(row.get("thumbs_up") or 0),
            "down": int(row.get("thumbs_down") or 0),
            "mine": mine,
            "alt_count": alt_count,
            "alt_avg": _optional_number(row.get("alt_avg")),
            "alt_spread": _optional_number(row.get("alt_spread")),
            "alt": _optional_number(row.get("my_alt")),
        }
    return counts


def _optional_number(value):
    try:
        if value is None or value == "":
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def market_mood_crowd(supabase, keys: list[str]) -> dict[str, dict]:
    """Agree and disagree counts for the current market sentiment. Empty if the function is missing."""
    wanted = [key for key in keys if key in ("crypto", "stock")]
    if not wanted:
        return {}
    try:
        response = supabase.rpc("market_mood_crowd", {"market_keys": wanted}).execute()
    except Exception as exc:
        _warn(exc)
        return {}
    counts = {}
    for row in response.data or []:
        key = row.get("market_key")
        if key not in ("crypto", "stock"):
            continue
        try:
            mine = int(row.get("my_vote"))
        except (TypeError, ValueError):
            mine = None
        try:
            alt_count = int(row.get("alt_count") or 0)
        except (TypeError, ValueError):
            alt_count = 0
        counts[str(key)] = {
            "up": int(row.get("thumbs_up") or 0),
            "down": int(row.get("thumbs_down") or 0),
            "mine": mine,
            "alt_count": alt_count,
            "alt_avg": _optional_number(row.get("alt_avg")),
            "alt_spread": _optional_number(row.get("alt_spread")),
            "alt": _optional_number(row.get("my_alt")),
        }
    return counts


def set_market_mood_vote(supabase, user_id, market_key: str, sentiment_at, vote, alt_score=None) -> None:
    """Save this account's thumb for the current market sentiment. None clears it."""
    if market_key not in ("crypto", "stock"):
        return
    if vote not in (1, -1):
        supabase.table("market_mood_votes").delete().eq("user_id", str(user_id)).eq("market_key", market_key).execute()
        return
    if not sentiment_at:
        return
    score = None
    if vote == -1 and alt_score is not None:
        number = _optional_number(alt_score)
        if number is not None and 0 <= number <= 100:
            score = int(number)
    supabase.table("market_mood_votes").upsert(
        {
            "user_id": str(user_id),
            "market_key": market_key,
            "sentiment_at": sentiment_at,
            "vote": int(vote),
            "alt_score": score,
        },
        on_conflict="user_id,market_key",
    ).execute()


def set_sentiment_vote(supabase, user_id, kind: str, asset_id: str, sentiment_at, vote, alt_score=None) -> None:
    """Save this account's thumb for the current sentiment. None clears it."""
    key = asset_market_key(kind, asset_id)
    if vote not in (1, -1):
        supabase.table("sentiment_votes").delete().eq("user_id", str(user_id)).eq("asset_key", key).execute()
        return
    if not sentiment_at:
        return
    score = None
    if vote == -1 and alt_score is not None:
        number = _optional_number(alt_score)
        if number is not None and 0 <= number <= 100:
            score = int(number)
    supabase.table("sentiment_votes").upsert(
        {
            "user_id": str(user_id),
            "asset_key": key,
            "sentiment_at": sentiment_at,
            "vote": int(vote),
            "alt_score": score,
        },
        on_conflict="user_id,asset_key",
    ).execute()


def _social_points(row) -> int:
    """The author's social score. Zero when the column is missing or blank."""
    try:
        points = int((row or {}).get("social_score") or 0)
    except (TypeError, ValueError):
        return 0
    return points if points > 0 else 0


def _author_id(row) -> str:
    """The account behind a note. Empty until the feed returns an id."""
    text = str((row or {}).get("author_id") or "").strip().lower()
    return text if _AUTHOR_ID.fullmatch(text) else ""


def _public_avatar(url) -> str:
    cleaned = str(url or "").strip()
    if (
        not cleaned.startswith("https://")
        or len(cleaned) > 500
        or any(mark in cleaned for mark in (" ", '"', "'", "<", ">", "\\"))
    ):
        return ""
    return cleaned


def _comment_time(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def _comment_groups(supabase, keys: list[str]) -> dict[str, list] | None:
    """Comments for these assets. An empty key list asks for every asset. None when the call fails."""
    try:
        response = supabase.rpc("sentiment_comments", {"asset_keys": keys}).execute()
    except Exception as exc:
        _warn(exc)
        return None
    grouped: dict[str, list] = {}
    for row in response.data or []:
        key = str(row.get("asset_key") or "")
        text = " ".join(str(row.get("body") or "").split())
        if not key or not text:
            continue
        try:
            note_id = int(row.get("id"))
        except (TypeError, ValueError):
            note_id = None
        try:
            vote = int(row.get("my_vote"))
        except (TypeError, ValueError):
            vote = 0
        if vote not in (1, -1):
            vote = 0
        grouped.setdefault(key, []).append({
            "id": note_id,
            "user": _author_id(row),
            "name": " ".join(str(row.get("author_name") or "Member").split())[:40] or "Member",
            "social": _social_points(row),
            "avatar": _public_avatar(row.get("avatar_url")),
            "at": _comment_time(row.get("created_at")),
            "text": text[:COMMENT_LIMIT],
            "mine": bool(row.get("mine")),
            "up": int(row.get("thumbs_up") or 0),
            "down": int(row.get("thumbs_down") or 0),
            "vote": vote,
            "score": _optional_number(row.get("responded_score")),
            "summary": _short_summary(row.get("responded_summary")),
        })
    return grouped


def sentiment_comment_lists(supabase, keys: list[str], every: bool = False) -> dict[str, list]:
    """Comments from the last 12 hours, newest first. Empty when the function is missing."""
    wanted = [key for key in keys if key]
    drop_expired_sentiment_comments(supabase)
    if every:
        grouped = _comment_groups(supabase, [])
        if grouped is not None:
            return grouped
    if not wanted:
        return {}
    return _comment_groups(supabase, wanted) or {}


def with_emoticon(text, face: str, limit: int = COMMENT_LIMIT) -> str:
    """Add one of the simple faces, with a space before it when the note already has words."""
    current = str(text or "")
    if face not in COMMENT_EMOTICONS:
        return current
    gap = "" if (not current or current[-1].isspace()) else " "
    if len(current) + len(gap) + len(face) <= limit:
        return current + gap + face
    if len(current) + len(face) <= limit:
        return current + face
    return current


def set_sentiment_comment(
    supabase, user_id, kind: str, asset_id: str, sentiment_at, body: str,
    responded_score=None, responded_summary: str = "",
) -> None:
    """Save this account's short comment and the sentiment it was answering. Blank removes it."""
    key = asset_market_key(kind, asset_id)
    text = " ".join(str(body or "").split())[:COMMENT_LIMIT]
    if not text:
        supabase.table("sentiment_comments").delete().eq("user_id", str(user_id)).eq("asset_key", key).execute()
        return
    if not sentiment_at:
        return
    summary = _short_summary(responded_summary)
    supabase.table("sentiment_comments").upsert(
        {
            "user_id": str(user_id),
            "asset_key": key,
            "sentiment_at": sentiment_at,
            "body": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "responded_score": _optional_number(responded_score),
            "responded_summary": summary or None,
        },
        on_conflict="user_id,asset_key",
    ).execute()


def drop_expired_sentiment_comments(supabase) -> None:
    """Delete comments older than 12 hours. Leaves newer notes when a score refreshes."""
    try:
        supabase.rpc("drop_expired_sentiment_comments").execute()
    except Exception as exc:
        _warn(exc)


def comment_balloon(comments, asset_key: str) -> str:
    """A speech balloon that opens the social signals stream. Empty when nobody has commented."""
    count = 0
    for note in comments or []:
        if " ".join(str((note or {}).get("text") or "").split()):
            count += 1
    if not count or not asset_key:
        return ""
    safe_key = html.escape(str(asset_key), quote=True)
    return (
        f"<button type='button' data-stream-key='{safe_key}' "
        "title='Open the social signals stream' "
        "style='background:#f8fafc;border:1px solid #d1d5db;border-radius:999px;"
        "padding:2px 10px;margin:0;cursor:pointer;font:inherit;font-weight:600;color:#111827;'>"
        f"💬 {count}</button>"
    )


def _sentiment_side(score) -> str:
    number = _optional_number(score)
    if number is None:
        return ""
    if number >= 53:
        return "positive"
    if number < 47:
        return "negative"
    return "mixed"


def _coverage_label(score) -> str:
    number = _optional_number(score)
    if number is None:
        return ""
    if number >= 60:
        return "Bullish coverage"
    if number >= 53:
        return "Mildly bullish coverage"
    if number >= 47:
        return "Mixed coverage"
    if number >= 40:
        return "Mildly bearish coverage"
    return "Bearish coverage"


def _short_summary(text, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[:limit].rsplit(" ", 1)[0]
    return (cut or cleaned[:limit]).rstrip(".,;:") + "…"


def load_chat(supabase) -> list[dict] | None:
    """Newest chat threads, replies oldest first. None when the chat tables are missing."""
    try:
        response = supabase.rpc("chat_feed").execute()
    except Exception:
        return None
    notes = []
    for row in response.data or []:
        text = " ".join(str(row.get("body") or "").split())
        try:
            message_id = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        if not text:
            continue
        parent = row.get("parent_id")
        try:
            parent_id = int(parent) if parent is not None else None
        except (TypeError, ValueError):
            parent_id = None
        try:
            vote = int(row.get("my_vote"))
        except (TypeError, ValueError):
            vote = 0
        if vote not in (1, -1):
            vote = 0
        notes.append({
            "id": message_id,
            "parent": parent_id,
            "user": _author_id(row),
            "name": " ".join(str(row.get("author_name") or "Member").split())[:40] or "Member",
            "social": _social_points(row),
            "avatar": _public_avatar(row.get("avatar_url")),
            "text": text[:COMMENT_LIMIT],
            "at": _comment_time(row.get("created_at")),
            "mine": bool(row.get("mine")),
            "up": int(row.get("thumbs_up") or 0),
            "down": int(row.get("thumbs_down") or 0),
            "vote": vote,
        })
    roots: dict[int, dict] = {}
    ordered = []
    for note in notes:
        if note["parent"] is not None:
            continue
        item = {key: note[key] for key in ("id", "user", "name", "social", "avatar", "text", "at", "mine", "up", "down", "vote")}
        item["replies"] = []
        roots[note["id"]] = item
        ordered.append(item)
    for note in notes:
        parent = roots.get(note["parent"])
        if parent is None:
            continue
        parent["replies"].append({
            key: note[key] for key in ("id", "user", "name", "social", "avatar", "text", "at", "mine", "up", "down", "vote")
        })
    ordered.sort(key=lambda item: item["at"], reverse=True)
    for item in ordered:
        item["replies"].sort(key=lambda reply: reply["at"])
    return ordered


def post_chat(supabase, user_id, body: str, parent_id: int | None = None) -> None:
    """Add a chat comment, or a reply to a top-level comment. Blank does nothing."""
    text = " ".join(str(body or "").split())[:COMMENT_LIMIT]
    if not text:
        return
    payload = {"user_id": str(user_id), "body": text}
    if parent_id:
        found = (
            supabase.table("chat_messages")
            .select("id,parent_id")
            .eq("id", int(parent_id))
            .limit(1)
            .execute()
        )
        rows = found.data or []
        if not rows or rows[0].get("parent_id") is not None:
            raise ValueError("Reply to a top-level comment.")
        payload["parent_id"] = int(parent_id)
    supabase.table("chat_messages").insert(payload).execute()


def delete_chat_message(supabase, user_id, message_id: int) -> None:
    """Delete one of your chat notes. A top-level note takes its replies with it."""
    del user_id
    if not message_id:
        return
    supabase.rpc("delete_own_chat_message", {"target_id": int(message_id)}).execute()


def set_chat_vote(supabase, user_id, message_id: int, vote) -> None:
    """Thumb a chat comment, including one you posted. The same thumb again clears it."""
    if not message_id:
        return
    found = (
        supabase.table("chat_messages")
        .select("id")
        .eq("id", int(message_id))
        .limit(1)
        .execute()
    )
    if not (found.data or []):
        return
    if vote not in (1, -1):
        (
            supabase.table("chat_votes")
            .delete()
            .eq("user_id", str(user_id))
            .eq("message_id", int(message_id))
            .execute()
        )
        return
    supabase.table("chat_votes").upsert(
        {"user_id": str(user_id), "message_id": int(message_id), "vote": int(vote)},
        on_conflict="user_id,message_id",
    ).execute()


def _vote_value(row) -> int:
    try:
        vote = int((row or {}).get("my_vote"))
    except (TypeError, ValueError):
        return 0
    return vote if vote in (1, -1) else 0


def sentiment_replies(supabase) -> dict[int, list]:
    """Replies for signal comments that are still in the 12-hour window. Empty when not installed."""
    try:
        response = supabase.rpc("sentiment_replies").execute()
    except Exception:
        return {}
    grouped: dict[int, list] = {}
    for row in response.data or []:
        text = " ".join(str(row.get("body") or "").split())
        try:
            reply_id = int(row.get("id"))
            comment_id = int(row.get("comment_id"))
        except (TypeError, ValueError):
            continue
        if not text:
            continue
        grouped.setdefault(comment_id, []).append({
            "id": reply_id,
            "user": _author_id(row),
            "name": " ".join(str(row.get("author_name") or "Member").split())[:40] or "Member",
            "social": _social_points(row),
            "avatar": _public_avatar(row.get("avatar_url")),
            "text": text[:COMMENT_LIMIT],
            "at": _comment_time(row.get("created_at")),
            "mine": bool(row.get("mine")),
            "up": int(row.get("thumbs_up") or 0),
            "down": int(row.get("thumbs_down") or 0),
            "vote": _vote_value(row),
        })
    for notes in grouped.values():
        notes.sort(key=lambda item: item["at"])
    return grouped


def post_signal_reply(supabase, user_id, comment_id: int, body: str) -> None:
    """Reply to one signal comment. Blank does nothing."""
    text = " ".join(str(body or "").split())[:COMMENT_LIMIT]
    if not text or not comment_id:
        return
    found = (
        supabase.table("sentiment_comments")
        .select("id")
        .eq("id", int(comment_id))
        .limit(1)
        .execute()
    )
    if not (found.data or []):
        raise ValueError("That comment is no longer here.")
    supabase.table("sentiment_replies").insert(
        {"user_id": str(user_id), "comment_id": int(comment_id), "body": text}
    ).execute()


def delete_signal_message(supabase, user_id, message_id: int, kind: str) -> None:
    """Delete one of your signal notes. A comment takes its replies with it."""
    del user_id
    if not message_id:
        return
    supabase.rpc(
        "delete_own_signal_message",
        {"target_id": int(message_id), "target_kind": "reply" if kind == "reply" else "comment"},
    ).execute()


def set_signal_vote(supabase, user_id, message_id: int, vote, kind: str) -> None:
    """Thumb a signal comment or a reply, including one you posted. The same thumb again clears it."""
    if not message_id:
        return
    if kind == "reply":
        table = "sentiment_replies"
        votes = "sentiment_reply_votes"
        column = "reply_id"
    else:
        table = "sentiment_comments"
        votes = "sentiment_comment_votes"
        column = "comment_id"
    found = supabase.table(table).select("id").eq("id", int(message_id)).limit(1).execute()
    if not (found.data or []):
        return
    if vote not in (1, -1):
        supabase.table(votes).delete().eq("user_id", str(user_id)).eq(column, int(message_id)).execute()
        return
    supabase.table(votes).upsert(
        {"user_id": str(user_id), column: int(message_id), "vote": int(vote)},
        on_conflict=f"user_id,{column}",
    ).execute()


def social_stream_items(comments_by_key, shared, names, logos=None, watchlist_keys=None, list_keys=None, replies=None) -> list[dict]:
    """Comments for the slide-in stream, newest first, with the sentiment they answered."""
    items = []
    on_watchlist = {str(key) for key in (watchlist_keys or []) if key}
    lists = {}
    for name, keys in (list_keys or {}).items():
        for key in keys or []:
            if key:
                lists[str(key)] = name
    for key, notes in (comments_by_key or {}).items():
        report, _stored_at = sentiment_from_row((shared or {}).get(key))
        current_score = _optional_number((report or {}).get("score")) if report else None
        current_summary = _short_summary((report or {}).get("summary")) if report else ""
        _kind, _bar, asset_id = str(key).partition("|")
        asset = str((names or {}).get(key) or asset_id or key)
        logo = _public_avatar((logos or {}).get(key))
        for note in notes or []:
            text = " ".join(str((note or {}).get("text") or "").split())
            if not text:
                continue
            score = _optional_number((note or {}).get("score"))
            summary = _short_summary((note or {}).get("summary"))
            if score is None:
                score = current_score
                summary = summary or current_summary
            note_id = note.get("id")
            thread = []
            if note_id is not None:
                thread = list((replies or {}).get(note_id) or [])
            items.append({
                "id": note_id,
                "key": str(key),
                "asset": asset,
                "watchlist": str(key) in on_watchlist,
                "list": lists.get(str(key), ""),
                "logo": logo,
                "side": _sentiment_side(score),
                "score": None if score is None else int(round(score)),
                "coverage": _coverage_label(score),
                "summary": summary,
                "user": str((note or {}).get("user") or ""),
                "name": str((note or {}).get("name") or "Member")[:40] or "Member",
                "social": int((note or {}).get("social") or 0),
                "avatar": _public_avatar((note or {}).get("avatar")),
                "at": str((note or {}).get("at") or ""),
                "text": text[:COMMENT_LIMIT],
                "mine": bool((note or {}).get("mine")),
                "up": int((note or {}).get("up") or 0),
                "down": int((note or {}).get("down") or 0),
                "vote": (note or {}).get("vote") if (note or {}).get("vote") in (1, -1) else 0,
                "replies": thread,
            })
    items.sort(key=lambda item: item["at"], reverse=True)
    return items


def crowd_mark(up, down, active: bool = True, alt_count=0, alt_avg=None, alt_spread=None) -> str:
    """Agree and disagree counts. Hover the down thumb for the crowd's own scores."""
    try:
        up_count = int(up or 0)
        down_count = int(down or 0)
    except (TypeError, ValueError):
        up_count = down_count = 0
    if not active:
        return "<span style='color:#6b7280;' title='No sentiment to react to yet.'>—</span>"
    scored = 0
    try:
        scored = int(alt_count or 0)
    except (TypeError, ValueError):
        scored = 0
    average = _optional_number(alt_avg)
    spread = _optional_number(alt_spread)
    up_title = html.escape(f"{up_count} agree with this sentiment.")
    detail = f"{down_count} disagree."
    if scored >= 1 and average is not None:
        detail = f"{down_count} disagree. {scored} gave their own score."
        if scored >= 2 and spread is not None:
            detail += f" The spread is ±{round(spread)}."
    detail += " These reset when the sentiment is refreshed."
    slot = (
        "display:inline-block;min-width:4.5ch;text-align:left;"
        "font-variant-numeric:tabular-nums;"
    )
    return (
        "<span style='display:inline-flex;align-items:center;gap:8px;white-space:nowrap;'>"
        f"<span title='{up_title}' style='color:#15803d;font-weight:700;display:inline-flex;align-items:center;gap:4px;'>"
        f"<span>👍</span><span style='{slot}'>{html.escape(_thumb_count_label(up_count))}</span></span>"
        f"<span title='{html.escape(detail)}' style='color:#b91c1c;font-weight:700;display:inline-flex;align-items:center;gap:4px;'>"
        f"<span>👎</span><span style='{slot}'>{html.escape(_thumb_count_label(down_count))}</span></span></span>"
    )


def _thumb_count_label(number: int) -> str:
    """Shown count. Above 100 the label stays '>100' so the thumbs keep their places."""
    return str(number) if number <= 100 else ">100"


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
    """Up to three people and the count. Above 100 the label reads >100."""
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
    shown = str(number) if number <= 100 else ">100"
    label = "1 account holds this" if number == 1 else f"{number} accounts hold this"
    return (
        f"<span title='{html.escape(label)}' style='display:inline-flex;align-items:center;gap:6px;'>"
        f"<span style='display:inline-flex;align-items:center;'>{''.join(faces)}</span>"
        f"<span style='font-weight:650;color:inherit;'>{html.escape(shown)}</span></span>"
    )


def trend_tone(percent) -> str:
    """Same colors as the 30-day column. Orange inside ±2%, else green or red."""
    try:
        number = float(percent)
    except (TypeError, ValueError):
        return "#6b7280"
    if number != number:
        return "#6b7280"
    if abs(number) < _SIDEWAYS_PERCENT:
        return "#d97706"
    if number > 0:
        return "#15803d"
    return "#b91c1c"


def sparkline_svg(closes, change_percent=None) -> str:
    """A short line for one table row. Color matches the 30-day percent."""
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
    if change_percent is None:
        start = values[0]
        change_percent = ((values[-1] - start) / abs(start) * 100) if start else 0.0
    color = trend_tone(change_percent)
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


_PRICE_LIMIT = 500
_SHARED_COLUMNS = (
    "asset_key, closes, logo_url, sentiment_report, sentiment_updated_at, "
    "prices, prices_updated_at"
)
_SHARED_COLUMNS_LEGACY = "asset_key, closes, logo_url, sentiment_report, sentiment_updated_at"


def _finite(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def records_from_frame(frame) -> list[dict]:
    """Daily open, high, low, close, and volume. The last 500 bars are enough to score."""
    if frame is None or getattr(frame, "empty", True):
        return []
    if any(column not in frame.columns for column in ("open", "high", "low", "close")):
        return []
    records = []
    for ts, row in frame.tail(_PRICE_LIMIT).iterrows():
        when = pd.Timestamp(ts)
        if when.tzinfo is not None:
            when = when.tz_convert("UTC")
        prices = [_finite(row[name]) for name in ("open", "high", "low", "close")]
        if any(price is None for price in prices):
            continue
        volume = _finite(row["volume"]) if "volume" in frame.columns else 0.0
        records.append({
            "t": when.strftime("%Y-%m-%d"),
            "o": prices[0],
            "h": prices[1],
            "l": prices[2],
            "c": prices[3],
            "v": 0.0 if volume is None else volume,
        })
    return records


def frame_from_records(records) -> pd.DataFrame:
    """The stored daily bars, oldest first. Empty when there are not enough to score."""
    if isinstance(records, str):
        try:
            records = json.loads(records)
        except json.JSONDecodeError:
            return pd.DataFrame()
    if not isinstance(records, list):
        return pd.DataFrame()
    rows = []
    index = []
    for item in records:
        if not isinstance(item, dict):
            continue
        prices = [_finite(item.get(name)) for name in ("o", "h", "l", "c")]
        if any(price is None for price in prices):
            continue
        try:
            when = pd.Timestamp(item.get("t"))
        except (TypeError, ValueError):
            continue
        if pd.isna(when):
            continue
        index.append(when)
        volume = _finite(item.get("v"))
        rows.append({
            "open": prices[0],
            "high": prices[1],
            "low": prices[2],
            "close": prices[3],
            "volume": 0.0 if volume is None else volume,
        })
    if len(rows) < 15:
        return pd.DataFrame()
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(index))
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def frame_from_row(row: dict | None) -> pd.DataFrame:
    """Price history saved on one shared asset row."""
    if not isinstance(row, dict):
        return pd.DataFrame()
    return frame_from_records(row.get("prices"))


def row_timestamp(row: dict | None, field: str) -> float | None:
    """When one column on a shared row was written, in seconds."""
    if not isinstance(row, dict):
        return None
    return _stored_at(row.get(field))


def sentiment_refresh_due(stored_at: float | None) -> bool:
    """True when sentiment has never been saved, or the 12-hour window has passed."""
    return stored_at is None or _age_expired(stored_at)


def technical_refresh_due(stored_at: float | None) -> bool:
    """True when prices have never been saved, or the 5-minute window has passed."""
    if stored_at is None:
        return True
    return datetime.now(timezone.utc).timestamp() - stored_at >= TECHNICAL_REFRESH_SECONDS


def save_price_frame(supabase, kind: str, asset_id: str, frame) -> bool:
    """Store daily bars and the sparkline closes. Leaves sentiment and the logo in place."""
    records = records_from_frame(frame)
    if len(records) < 15:
        return False
    identity = _canonical_id(kind, asset_id)
    if not identity:
        return False
    closes = recent_closes([item["c"] for item in records])
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "asset_key": asset_market_key(kind, identity),
        "kind": kind,
        "asset_id": identity,
        "closes": closes,
        "closes_updated_at": now,
        "prices": records,
        "prices_updated_at": now,
    }
    try:
        supabase.table("asset_market").upsert(payload, on_conflict="asset_key").execute()
    except Exception as exc:
        _warn(exc)
        if "prices" in str(exc).lower():
            save_price_paths(supabase, [{"kind": kind, "asset_id": identity, "closes": closes}])
        return False
    return True


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


def asset_logo(url, label: str, size: int = 22) -> str:
    """Round logo. A letter shows until the picture loads, and if it never does."""
    size = min(48, max(16, int(size)))
    font = max(11, round(size * 0.46))
    letter = next((ch.upper() for ch in str(label or "") if ch.isalnum()), "•")
    mark = (
        f"<span style='width:{size}px;height:{size}px;border-radius:999px;background:#eef2ff;"
        f"color:#3730a3;font-size:{font}px;font-weight:700;display:inline-flex;"
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
        f"<span style='position:relative;width:{size}px;height:{size}px;flex:none;display:inline-flex;'>"
        f"{mark}"
        f"<img src='{safe}' alt='' width='{size}' height='{size}' "
        f"style='position:absolute;inset:0;width:{size}px;height:{size}px;border-radius:999px;"
        "object-fit:cover;background:#ffffff;' onerror='this.remove()'>"
        "</span>"
    )


def heading_with_logo(text: str, url, label: str) -> str:
    """A section title with the asset logo at the same height as the heading."""
    safe = html.escape(text)
    logo = asset_logo(url, label or text, size=32)
    return (
        "<div style='display:flex;align-items:center;gap:12px;margin:0.2rem 0 0.4rem;'>"
        f"{logo}<h3 style='margin:0;padding:0;line-height:1.2;font-size:1.5rem;font-weight:600;'>"
        f"{safe}</h3></div>"
    )


def load_market_moods(supabase) -> dict[str, dict] | None:
    """The crypto and stock sentiment rows. None when the table is not there yet."""
    try:
        response = (
            supabase.table("market_mood")
            .select("market_key, query, sentiment_report, sentiment_updated_at")
            .execute()
        )
    except Exception as exc:
        _warn(exc)
        return None
    return {
        str(row.get("market_key")): row
        for row in (response.data or [])
        if row.get("market_key")
    }


def save_market_mood(supabase, market_key: str, query: str, report: dict, stored_at: float) -> bool:
    """Store one whole-market score so every account can show it."""
    if market_key not in ("crypto", "stock") or not isinstance(report, dict) or not report.get("ok"):
        return False
    try:
        score = float(report.get("score"))
    except (TypeError, ValueError):
        return False
    if score != score:
        return False
    payload = {
        "market_key": market_key,
        "query": query,
        "sentiment_score": score,
        "sentiment_report": report,
        "sentiment_updated_at": datetime.fromtimestamp(stored_at, timezone.utc).isoformat(),
    }
    try:
        supabase.table("market_mood").upsert(payload, on_conflict="market_key").execute()
    except Exception as exc:
        _warn(exc)
        return False
    _record_sentiment_history(supabase, market_key, score, stored_at)
    return True


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
        return
    _record_sentiment_history(supabase, asset_market_key(kind, identity), score, stored_at)
    drop_expired_sentiment_comments(supabase)


def _record_sentiment_history(supabase, subject_key: str, score: float, stored_at: float) -> None:
    """Append one score. A repeat of the same update is ignored. Older than 30 days is removed."""
    if not subject_key:
        return
    try:
        supabase.rpc("record_sentiment_score", {
            "subject_key": subject_key,
            "score": score,
            "recorded_at": datetime.fromtimestamp(stored_at, timezone.utc).isoformat(),
        }).execute()
    except Exception as exc:
        print(f"Sentiment history was not stored for {subject_key}: {exc}")


def load_shared_market(supabase, keys: list[str]) -> dict[str, dict]:
    """Rows already stored for these assets. Empty when the table is not there yet."""
    wanted = [key for key in keys if key]
    if not wanted:
        return {}
    try:
        response = (
            supabase.table("asset_market")
            .select(_SHARED_COLUMNS)
            .in_("asset_key", wanted)
            .execute()
        )
    except Exception as exc:
        if "prices" not in str(exc).lower():
            _warn(exc)
            return {}
        try:
            response = (
                supabase.table("asset_market")
                .select(_SHARED_COLUMNS_LEGACY)
                .in_("asset_key", wanted)
                .execute()
            )
        except Exception as fallback:
            _warn(fallback)
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
    """The last shared headline report, including one waiting on the next update."""
    if not row:
        return None, None
    stored_at = _stored_at(row.get("sentiment_updated_at"))
    if stored_at is None:
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
