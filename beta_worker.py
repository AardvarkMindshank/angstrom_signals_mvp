"""The part of the alert worker that emails beta applicants after Drew decides from the link in the request email."""
from __future__ import annotations

import os

import requests

import beta_emails


def _send_resend(to_email: str, subject: str, page: str, plain: str, attachments: list | None = None) -> bool:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key or not to_email:
        return False
    sender = (os.getenv("RESEND_FROM") or "").strip() or "Angstrom Signals <onboarding@resend.dev>"
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            json={"from": sender, "to": [to_email], "subject": subject, "html": page, "text": plain,
                  **({"attachments": attachments} if attachments else {})},
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


def nda_copy_email(full_name: str, version: str, signed_at: str, reference: str, for_admin: bool) -> tuple[str, str, str]:
    """(subject, html, plain text) carrying a signed NDA copy."""
    from email_brand import render_email

    import html as _html

    who = _html.escape(" ".join(str(full_name or "").split()) or "A tester")
    when = _html.escape(str(signed_at)[:16].replace("T", " "))
    if for_admin:
        lines = [f"{who} signed the beta NDA (version {_html.escape(version)}) on {when} UTC.",
                 f"The signed copy is attached. Signing reference: {_html.escape(reference)}."]
        subject = f"NDA signed: {' '.join(str(full_name).split())}"
    else:
        lines = [f"Hi {who.split(' ')[0]}, thank you for signing the Angstrom Signals beta non-disclosure agreement "
                 f"(version {_html.escape(version)}) on {when} UTC.",
                 "Your signed copy is attached. Please keep it for your records.",
                 f"Signing reference: {_html.escape(reference)}."]
        subject = "Your signed Angstrom Signals beta NDA"
    page, plain = render_email("NDA signed", lines, tone="info", preheader=subject)
    return subject, page, plain


def send_nda_copies(supabase, send=None, admin_emails=None, now=None) -> int:
    """Email each new signed NDA copy to its signer and to every admin. Claimed first (emailed_at), released if the
    signer's email fails, so it is retried; admin copies are best effort. Returns how many signers got their copy."""
    from datetime import datetime, timezone

    send = send or _send_resend
    if send is _send_resend and not (os.getenv("RESEND_API_KEY") or "").strip():
        return 0
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    try:
        rows = (supabase.table("nda_signatures")
                .select("id, reference, email, full_name, nda_version, signed_at, signed_pdf")
                .is_("emailed_at", "null").limit(10).execute().data or [])
    except Exception as exc:
        if "nda_signatures" not in str(exc):
            print(f"NDA copies skipped: {str(exc)[:160]}")
        return 0
    if rows and admin_emails is None:
        admin_emails = _admin_emails(supabase)
    sent = 0
    for row in rows:
        try:
            claimed = (supabase.table("nda_signatures").update({"emailed_at": stamp}).eq("id", row["id"])
                       .is_("emailed_at", "null").execute().data)
        except Exception as exc:
            print(f"NDA copy claim failed for {row.get('id')}: {exc}")
            continue
        if not claimed:
            continue
        attachment = [{"filename": f"Angstrom-beta-NDA-v{row['nda_version']}-signed.pdf", "content": row["signed_pdf"]}]
        subject, page, plain = nda_copy_email(row["full_name"], row["nda_version"], row["signed_at"],
                                              row["reference"], for_admin=False)
        if send(row["email"], subject, page, plain, attachment):
            sent += 1
        else:
            try:
                supabase.table("nda_signatures").update({"emailed_at": None}).eq("id", row["id"]).execute()
            except Exception as exc:
                print(f"Could not release NDA copy {row['id']}: {exc}")
            continue
        subject, page, plain = nda_copy_email(row["full_name"], row["nda_version"], row["signed_at"],
                                              row["reference"], for_admin=True)
        for address in admin_emails or []:
            if address and address.lower() != str(row["email"]).lower():
                try:
                    send(address, subject, page, plain, attachment)
                except Exception as exc:
                    print(f"NDA admin copy to {address} failed: {exc}")
    return sent


def _admin_emails(supabase) -> list[str]:
    try:
        ids = [r["user_id"] for r in (supabase.table("profiles").select("user_id").eq("role", "admin")
                                      .execute().data or [])]
    except Exception:
        return []
    out = []
    for uid in ids:
        try:
            user = getattr(supabase.auth.admin.get_user_by_id(uid), "user", None)
            if user is not None and getattr(user, "email", None):
                out.append(user.email)
        except Exception:
            continue
    return out
