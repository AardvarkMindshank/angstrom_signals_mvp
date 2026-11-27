"""✍️ The beta NDA for the new app (nda.py, the classic app's own rules): whether this account still has to sign, the
NDA to read, the PDF, and signing. Signing builds the same signed copy (the NDA with a signature page) and records it
through nda_sign as the member; the worker emails the copy to the signer and the admins, as before. Admins never sign,
but may open a preview, which records nothing and returns a sample copy. In English, as the NDA itself is."""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

import nda as nd


def _user(db, token: str) -> tuple[str, str]:
    try:
        u = db.auth.get_user(token).user
        return str(u.email or ""), str(u.created_at or "")
    except Exception:
        return "", ""


def _state(db, n: dict) -> dict:
    return nd.status(db, n) or {}


def info(db, token: str) -> dict:
    n = nd.current()
    if n is None:
        return {"needed": False}
    state = _state(db, n)
    email, made = _user(db, token)
    needed = bool(n["enforce"] and state and not state.get("is_admin") and not state.get("signed")
                  and nd.applies_to(n, email, made))
    return {"needed": needed, "admin": bool(state.get("is_admin")), "enforce": n["enforce"], "title": n["title"],
            "version": n["version"], "sha256": n["sha256"], "file": n["file"],
            "markdown": nd.smaller_headings(n["markdown"], 1) if n.get("markdown") else "", "text": n["text"],
            # for the NDA column of Admin › Beta requests (who is asked to sign), admins only
            **({"applies_from": n["applies_from"], "exempt": n["exempt"]} if state.get("is_admin") else {})}


def pdf() -> tuple[bytes, str] | None:
    n = nd.current()
    return (n["pdf"], n["file"]) if n else None


def sign(db, uid: str, token: str, full_name: str, country: str, agreed: bool, drawing: str, preview: bool,
         ip: str, agent: str) -> dict:
    n = nd.current()
    if n is None:
        return {"ok": False, "problems": ["No NDA is set up."]}
    state = _state(db, n)
    if preview and not state.get("is_admin"):
        return {"ok": False, "problems": ["Only admins can preview the NDA page."]}
    problems = nd.check_signature(full_name, agreed, drawing, country)
    if problems:
        return {"ok": False, "problems": problems}
    email, _made = _user(db, token)
    reference = str(uuid.uuid4())
    copy = nd.signed_copy(n, reference=reference, full_name=full_name, email=email, user_id=uid, drawing_png=drawing,
                          signed_at=datetime.now(timezone.utc), ip=ip, user_agent=agent, country=country)
    if not preview:
        try:
            db.rpc("nda_sign", {"p_reference": reference, "p_version": n["version"], "p_sha256": n["sha256"],
                                "p_full_name": " ".join(full_name.split()), "p_country": " ".join(country.split()),
                                "p_drawing": drawing, "p_signed_pdf": base64.b64encode(copy).decode(),
                                "p_ip": ip, "p_user_agent": agent}).execute()
        except Exception as exc:
            if "already_signed" not in str(exc):
                return {"ok": False, "problems": ["The signature could not be saved. Please try again."]}
    return {"ok": True, "pdf": base64.b64encode(copy).decode(),
            "name": ("SAMPLE-signed-" if preview else "signed-") + n["file"]}
