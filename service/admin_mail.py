"""The admin page's two emails (the classic admin panel's): a welcome when an email is approved for the beta, and a
note when an account is barred. Sent through Resend with RESEND_API_KEY / RESEND_FROM on the data service; when the
key isn't there, nothing is sent and the admin is told so. Only an admin may send, and only to an address that is
on the matching list (approved, or barred), so this can't be used to mail anyone else. Nothing is logged."""
from __future__ import annotations

import html
import os

import requests


def _rows(db, function: str) -> list[dict]:
    try:
        data = db.rpc(function).execute().data
    except Exception:
        return []
    return [r for r in (data or []) if isinstance(r, dict)] if isinstance(data, list) else []


def _reason(response) -> str:
    """A short Resend error, with no key or address in it."""
    try:
        message = " ".join(str((response.json() or {}).get("message") or "").split())
    except Exception:
        message = ""
    if not message or "re_" in message.lower() or "@" in message:
        return f"Resend returned status {response.status_code}"
    return message[:180]


def send(db, kind: str, address: str, name: str = "") -> dict:
    address = " ".join(str(address or "").split()).lower()
    try:
        admin = bool(db.rpc("is_admin").execute().data)
    except Exception:
        admin = False
    if not admin:
        return {"sent": False, "why": "This account cannot send admin emails."}
    if kind == "welcome":
        listed = {str(r.get("email") or "").strip().lower() for r in _rows(db, "admin_beta_access")}
        listed |= {str(r.get("email") or "").strip().lower() for r in _rows(db, "admin_beta_requests") if r.get("status") == "approved"}
    elif kind == "barred":
        listed = {str(r.get("email") or "").strip().lower() for r in _rows(db, "admin_blacklist")}
    else:
        return {"sent": False, "why": "Unknown email."}
    if not address or address not in listed:
        return {"sent": False, "why": "that address isn't on the list"}
    api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not api_key:
        return {"sent": False, "why": "the Resend key isn't set on the data service yet"}
    sender = (os.getenv("RESEND_FROM") or "").strip() or "MarketNavi <onboarding@resend.dev>"
    if kind == "welcome":
        import beta_emails

        subject, page, plain = beta_emails.welcome_email(name, (os.getenv("APP_URL") or "https://app.marketnavi.ai").strip())
    else:
        from email_brand import render_email

        inbox = (os.getenv("REPORT_TO") or "").strip() or "support@marketnavi.ai"
        page, plain = render_email(
            "Your account is barred",
            ["Your MarketNavi account is barred at this time.",
             f'You can email <a href="mailto:{html.escape(inbox, quote=True)}" style="color:#1d5fd1;">{html.escape(inbox)}</a>.'],
            tone="down")
        subject = "Your MarketNavi account is barred"
    try:
        response = requests.post("https://api.resend.com/emails",
                                 json={"from": sender, "to": [address], "subject": subject, "html": page, "text": plain},
                                 headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, timeout=15)
    except Exception:
        return {"sent": False, "why": "Resend could not be reached"}
    if response.status_code < 300:
        return {"sent": True, "why": ""}
    return {"sent": False, "why": _reason(response)}
