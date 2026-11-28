"""The part of the alert worker that emails beta applicants and barred addresses, whichever app or email link the admin
decided from: the welcome (with the person's own one-time "set your password" link), the decline, the barred note,
and signed NDA copies. Each email is claimed before sending, so it goes once; a failed send is released and retried.
Logs never carry addresses or names."""
from __future__ import annotations

import os

import requests

import beta_emails


def _send_resend(to_email: str, subject: str, page: str, plain: str, attachments: list | None = None) -> bool:
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key or not to_email:
        return False
    sender = (os.getenv("RESEND_FROM") or "").strip() or "MarketNavi <onboarding@resend.dev>"
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
    print(f"Beta email failed: HTTP {response.status_code}")
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
            continue                       # the welcome, with its own sign-in link, goes from send_welcome_links
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
        lines = [f"Hi {who.split(' ')[0]}, thank you for signing the MarketNavi beta non-disclosure agreement "
                 f"(version {_html.escape(version)}) on {when} UTC.",
                 "Your signed copy is attached. Please keep it for your records.",
                 f"Signing reference: {_html.escape(reference)}."]
        subject = "Your signed MarketNavi beta NDA"
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


# Where a welcome link lands: the new app, which sees the one-time sign-in in the address and asks for a password.
WELCOME_URL = (os.getenv("WELCOME_URL") or "https://marketnavi.ai/new/?welcome=1").strip()


def welcome_link(supabase, address: str) -> str:
    """A one-time sign-in link for an approved address: an invitation (it creates the account), or for an address that
    already has an account (it signed in with Google, say) a sign-in link. Empty when neither can be made."""
    for kind in ("invite", "magiclink"):
        try:
            got = supabase.auth.admin.generate_link({"type": kind, "email": address, "options": {"redirect_to": WELCOME_URL}})
            props = getattr(got, "properties", None)
            link = getattr(props, "action_link", "") if props is not None else ""
            if link:
                return str(link)
        except Exception:
            continue
    return ""


def send_welcome_links(supabase, send=None, link=None, now=None) -> int:
    """Welcome each newly approved address (beta_access rows not yet welcomed), with its own sign-in link."""
    from datetime import datetime, timezone

    send = send or _send_resend
    if send is _send_resend and not (os.getenv("RESEND_API_KEY") or "").strip():
        return 0
    link = link or welcome_link
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    try:
        rows = supabase.table("beta_access").select("email, request_id").is_("welcomed_at", "null").limit(25).execute().data or []
    except Exception as exc:
        if "welcomed_at" not in str(exc):
            print(f"Welcome emails skipped: {str(exc)[:160]}")
        return 0
    sent = 0
    for row in rows:
        address = str(row.get("email") or "").strip().lower()
        try:
            claimed = (supabase.table("beta_access").update({"welcomed_at": stamp}).eq("email", address)
                       .is_("welcomed_at", "null").execute().data)
        except Exception:
            continue
        if not claimed:
            continue
        name = ""
        if row.get("request_id"):
            try:
                got = supabase.table("beta_requests").select("name").eq("id", row["request_id"]).limit(1).execute().data or []
                name = (got[0].get("name") if got else "") or ""
            except Exception:
                pass
        subject, page, plain = beta_emails.welcome_email(name, WELCOME_URL, link=link(supabase, address))
        if address and send(address, subject, page, plain):
            sent += 1
        else:
            try:
                supabase.table("beta_access").update({"welcomed_at": None}).eq("email", address).execute()
            except Exception:
                pass
    if sent:
        print(f"Welcome emails sent: {sent}")
    return sent


def send_barred_notes(supabase, send=None, now=None) -> int:
    """Tell each newly barred address (email_blacklist rows not yet notified)."""
    from datetime import datetime, timezone

    send = send or _send_resend
    if send is _send_resend and not (os.getenv("RESEND_API_KEY") or "").strip():
        return 0
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    try:
        rows = supabase.table("email_blacklist").select("email").is_("notified_at", "null").limit(25).execute().data or []
    except Exception as exc:
        if "notified_at" not in str(exc):
            print(f"Barred emails skipped: {str(exc)[:160]}")
        return 0
    inbox = (os.getenv("REPORT_TO") or "").strip() or "support@marketnavi.ai"
    sent = 0
    for row in rows:
        address = str(row.get("email") or "").strip().lower()
        try:
            claimed = (supabase.table("email_blacklist").update({"notified_at": stamp}).eq("email", address)
                       .is_("notified_at", "null").execute().data)
        except Exception:
            continue
        if not claimed:
            continue
        subject, page, plain = beta_emails.barred_email(inbox)
        if address and send(address, subject, page, plain):
            sent += 1
        else:
            try:
                supabase.table("email_blacklist").update({"notified_at": None}).eq("email", address).execute()
            except Exception:
                pass
    if sent:
        print(f"Barred emails sent: {sent}")
    return sent
