"""The part of the alert worker that emails beta applicants after Drew decides from the link in the request email."""
from __future__ import annotations

import os

import requests

import beta_emails


def _send_resend(to_email: str, subject: str, page: str, plain: str) -> bool:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key or not to_email:
        return False
    sender = (os.getenv("RESEND_FROM") or "").strip() or "Angstrom Signals <onboarding@resend.dev>"
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json={"from": sender, "to": [to_email], "subject": subject, "html": page, "text": plain},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
    except Exception as exc:
        print(f"Beta email failed: {exc}")
        return False
    if response.status_code in (200, 201):
        return True
    print(f"Beta email failed: HTTP {response.status_code} {' '.join((response.text or '').split())[:200]}")
    return False


def send_beta_decision_emails(supabase, send=None, now=None) -> int:
    """Email people whose beta request was approved or declined from the link in the request email.
    Each request is claimed before sending, so two overlapping runs cannot send twice, and a failed
    send is released so the next run tries again. Returns how many were sent."""
    from datetime import datetime, timezone

    send = send or _send_resend
    if send is _send_resend and not (os.getenv("RESEND_API_KEY") or "").strip():
        return 0
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    app_url = (os.getenv("APP_URL") or "https://app.angstromsignals.com").strip()
    try:
        rows = (
            supabase.table("beta_requests")
            .select("id, name, email, status")
            .eq("decided_via", "email")
            .is_("notified_at", "null")
            .in_("status", ["approved", "declined"])
            .limit(25)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        print(f"Beta decision emails skipped: {exc}")
        return 0
    sent = 0
    for row in rows:
        request_id = row.get("id")
        status = str(row.get("status") or "")
        address = str(row.get("email") or "").strip()
        try:
            claimed = (
                supabase.table("beta_requests")
                .update({"notified_at": stamp})
                .eq("id", request_id)
                .is_("notified_at", "null")
                .execute()
                .data
            )
        except Exception as exc:
            print(f"Beta email claim failed for request {request_id}: {exc}")
            continue
        if not claimed:
            continue
        if status == "approved":
            subject, page, plain = beta_emails.welcome_email(row.get("name") or "", app_url)
        else:
            subject, page, plain = beta_emails.declined_email(row.get("name") or "")
        ok = bool(address) and send(address, subject, page, plain)
        if ok:
            sent += 1
            print(f"Beta email sent for request {request_id} ({status}).")
        else:
            try:
                supabase.table("beta_requests").update({"notified_at": None}).eq("id", request_id).execute()
            except Exception as exc:
                print(f"Could not release request {request_id}: {exc}")
    return sent
