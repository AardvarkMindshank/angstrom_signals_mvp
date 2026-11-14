"""
📱 Push notifications for the installable web app (14 Nov 2026).

Each device someone turns notifications on for (Settings → Notifications) is a row in push_subscriptions
(sql/2026-11-28_push_notifications.sql). The alert worker calls run_pending() every few minutes: every new notification
(user_notifications) goes to that person's devices once, then is marked pushed. Devices the browser reports gone are
removed.

Keys: web push signs each message with a key pair ("VAPID"). The public key goes to the browser when a device signs
up; the private key stays on the server.
    VAPID_PUBLIC_KEY    Render and GitHub (not secret, but kept beside the private one)
    VAPID_PRIVATE_KEY   Render and GitHub secrets
    VAPID_SUBJECT       a contact address, e.g. mailto:info@angstromsignals.com
An admin makes a pair in the app (Admin → 📱 Push keys); the keys are shown only to them, never stored by the app.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone

MAX_AGE_MINUTES = 60          # older notifications are never pushed (e.g. the first run after switching this on)
DEFAULT_SUBJECT = "mailto:info@angstromsignals.com"

TITLES = {                    # the notification's title by kind; anything else: "Angstrom · <asset>"
    "funnel": "🔻 Funnel",
    "chart_share": "📤 Shared chart",
    "study": "📊 Study finished",
    "group_invite": "👥 Community invite",
    "group_joined": "👥 Community",
    "invite_joined": "👋 Invite accepted",
    "test": "📱 Angstrom",
}


def _setting(name: str) -> str:
    value = os.getenv(name) or ""
    if not value:
        try:
            import streamlit as st

            value = str(st.secrets.get(name) or (st.secrets.get("push", {}) or {}).get(name.lower()) or "")
        except Exception:
            value = ""
    return value.strip().strip('"').strip("'")


def public_key() -> str:
    return _setting("VAPID_PUBLIC_KEY")


def ready() -> bool:
    """Both keys are there, so pushes can be sent."""
    return bool(public_key() and _setting("VAPID_PRIVATE_KEY"))


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_keys() -> tuple[str, str]:
    """A new key pair (public, private), both base64url, in the form browsers and pywebpush take."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return _b64url(public), _b64url(private)


def note_payload(note: dict) -> dict:
    """What one notification shows on a phone: a title, the message, and the app to open."""
    kind = str(note.get("alert_type") or "")
    name = " ".join(str(note.get("asset_name") or "").split())
    title = TITLES.get(kind) or (f"Angstrom · {name}" if name else "Angstrom Signals")
    body = " ".join(str(note.get("message") or "").split())
    if len(body) > 220:
        body = body[:217].rstrip() + "…"
    note_id = note.get("id")
    # Tapping it opens the app where the notification's card in the Alert Feed would go (app.py _take_push_open).
    return {"title": title, "body": body, "url": f"/?note={note_id}" if note_id else "/",
            "tag": f"note-{note_id}" if note_id else ""}


def send(sub: dict, payload: dict, webpush=None) -> str:
    """Send one push. Returns "ok", "gone" (the device unsubscribed: remove it) or "failed"."""
    if webpush is None:
        from pywebpush import webpush
    try:
        webpush(
            subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
            data=json.dumps(payload),
            vapid_private_key=_setting("VAPID_PRIVATE_KEY"),
            vapid_claims={"sub": _setting("VAPID_SUBJECT") or DEFAULT_SUBJECT},
            ttl=6 * 3600,
            timeout=10,
        )
        return "ok"
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return "gone" if status in (404, 410) else "failed"


def send_to_user(supabase, user_id: str, payload: dict, webpush=None) -> int:
    """Send to every device of one person (the Settings test). Returns how many devices got it."""
    rows = (supabase.table("push_subscriptions").select("endpoint, p256dh, auth").eq("user_id", str(user_id))
            .execute().data or [])
    sent = 0
    for sub in rows:
        if send(sub, payload, webpush=webpush) == "ok":
            sent += 1
    return sent


def run_pending(supabase, now=None, webpush=None, log=print) -> dict:
    """The worker's step: push every new notification to its owner's devices, once."""
    if not ready():
        return {"skipped": "no push keys"}
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(minutes=MAX_AGE_MINUTES)).isoformat()
    try:
        subs = supabase.table("push_subscriptions").select("id, user_id, endpoint, p256dh, auth").execute().data or []
    except Exception as exc:
        log(f"push: no subscriptions table yet ({str(exc)[:80]})")
        return {"skipped": "no table"}
    by_user: dict[str, list[dict]] = {}
    for sub in subs:
        by_user.setdefault(str(sub["user_id"]), []).append(sub)
    if not by_user:
        return {"notes": 0, "sent": 0}
    notes = (supabase.table("user_notifications").select("id, user_id, alert_type, asset_name, message, created_at")
             .is_("pushed_at", "null").gte("created_at", since).in_("user_id", list(by_user)).order("created_at")
             .limit(500).execute().data or [])
    sent = gone = 0
    dead: set = set()
    for note in notes:
        payload = note_payload(note)
        for sub in by_user.get(str(note["user_id"]), []):
            if sub["id"] in dead:
                continue
            result = send(sub, payload, webpush=webpush)
            if result == "ok":
                sent += 1
            elif result == "gone":
                dead.add(sub["id"])
                gone += 1
        supabase.table("user_notifications").update({"pushed_at": now.isoformat()}).eq("id", note["id"]).execute()
    for sub_id in dead:
        supabase.table("push_subscriptions").delete().eq("id", sub_id).execute()
    if notes:
        log(f"push: {len(notes)} notifications, {sent} pushes sent, {gone} devices gone")
    return {"notes": len(notes), "sent": sent, "gone": gone}


if __name__ == "__main__":
    from supabase import create_client

    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        print(run_pending(create_client(url, key)))
    else:
        print("push: no Supabase settings")
