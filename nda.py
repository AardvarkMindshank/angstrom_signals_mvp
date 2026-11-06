"""
Beta NDA signing (docs/design/beta_nda.md, sql/2026-11-09_beta_nda.sql).

After Drew approves a beta request, the person creates their account as before. On every sign-in, until they have
signed the current NDA, the dashboard shows only the NDA page: the document, a tick, their typed full name and a
drawn signature. Signing stores a record (account, email, typed name, drawing, server time, IP address, browser, NDA
version and the PDF's SHA-256 fingerprint) and a signed copy: the NDA with a signature page added. The worker emails
the copy to the signer and to the admins. Admin accounts never need to sign.

The NDA lives in legal/nda/: current.json names the version and the PDF. Without it, nothing is asked of anyone.
A new version (new PDF, new version name in current.json) asks everyone to sign again.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NDA_DIR = ROOT / "legal" / "nda"
MIN_STROKE_BYTES = 400                    # a blank canvas encodes to well under this


def current(directory: Path | None = None) -> dict | None:
    """The NDA in force: {version, title, enforce, file, pdf (bytes), sha256, text}, or None when none is set up."""
    directory = directory or NDA_DIR
    meta_path = directory / "current.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        pdf = (directory / meta["file"]).read_bytes()
    except (OSError, ValueError, KeyError):
        return None
    return {"version": str(meta["version"]), "title": str(meta.get("title") or "Beta Non-Disclosure Agreement"),
            "enforce": meta.get("enforce", True) is True, "file": meta["file"], "pdf": pdf, "sha256": hashlib.sha256(pdf).hexdigest(), "text": pdf_text(pdf)}


def pdf_text(pdf: bytes) -> str:
    """The NDA's words, for reading on the page (iPhone browsers show only the first page of an embedded PDF)."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf))
        return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    except Exception:
        return ""


def check_signature(full_name: str, agreed: bool, drawing_png: str | None) -> list[str]:
    problems = []
    if not agreed:
        problems.append("Tick the box to confirm you have read and agree to the NDA.")
    if len(" ".join(str(full_name or "").split())) < 2 or len(str(full_name)) > 120:
        problems.append("Type your full legal name.")
    try:
        raw = base64.b64decode(drawing_png or "", validate=True)
    except (ValueError, TypeError):
        raw = b""
    if not raw.startswith(b"\x89PNG") or len(raw) < MIN_STROKE_BYTES:
        problems.append("Draw your signature in the box.")
    return problems


def signed_copy(nda: dict, *, reference: str, full_name: str, email: str, user_id: str, drawing_png: str,
                signed_at: datetime, ip: str, user_agent: str) -> bytes:
    """The NDA with a signature page added at the end."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    page = io.BytesIO()
    c = canvas.Canvas(page, pagesize=A4)
    width, height = A4
    x, y = 22 * mm, height - 30 * mm
    c.setFont("Helvetica-Bold", 15)
    c.drawString(x, y, f"Signature page: {nda['title']}")
    c.setFont("Helvetica", 10.5)
    y -= 10 * mm
    lines = [
        ("Signed by", " ".join(full_name.split())),
        ("Account email", email),
        ("Signed at (UTC)", signed_at.astimezone(timezone.utc).strftime("%d %B %Y, %H:%M:%S")),
        ("NDA version", nda["version"]),
        ("Document fingerprint (SHA-256)", nda["sha256"]),
        ("Signing reference", reference),
        ("Account id", user_id),
        ("IP address", ip or "not available"),
        ("Browser", _short(user_agent or "not available", 70)),
    ]
    for label, value in lines:
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(x, y, label)
        c.setFont("Helvetica", 9.5)
        c.drawString(x + 62 * mm, y, str(value))
        y -= 6.5 * mm
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(x, y, "Signature")
    image = ImageReader(io.BytesIO(base64.b64decode(drawing_png)))
    iw, ih = image.getSize()
    box_w = 90 * mm
    box_h = box_w * ih / iw
    c.drawImage(image, x, y - box_h - 4 * mm, width=box_w, height=box_h, mask="auto")
    c.line(x, y - box_h - 5 * mm, x + box_w, y - box_h - 5 * mm)
    y -= box_h + 16 * mm
    c.setFont("Helvetica", 9)
    text = c.beginText(x, y)
    for line in (
        "By ticking the agreement box, typing their full name and drawing their signature, the signer agreed",
        "electronically to the document identified by the fingerprint above, which is the document attached",
        "before this page. The record of this signature is kept by Angstrom Signals and cannot be changed.",
    ):
        text.textLine(line)
    c.drawText(text)
    c.showPage()
    c.save()

    writer = PdfWriter()
    for p in PdfReader(io.BytesIO(nda["pdf"])).pages:
        writer.add_page(p)
    for p in PdfReader(io.BytesIO(page.getvalue())).pages:
        writer.add_page(p)
    writer.add_metadata({"/Title": f"{nda['title']} (signed by {full_name})", "/Subject": f"Reference {reference}"})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _short(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _request_details(st) -> tuple[str, str]:
    try:
        headers = st.context.headers
        forwarded = str(headers.get("X-Forwarded-For") or headers.get("x-forwarded-for") or "")
        ip = forwarded.split(",")[0].strip() or str(getattr(st.context, "ip_address", "") or "")
        return ip[:100], str(headers.get("User-Agent") or headers.get("user-agent") or "")[:400]
    except Exception:
        return "", ""


def status(supabase, nda: dict) -> dict | None:
    """{is_admin, signed, signed_at} from the database, or None when the NDA tables are not installed yet."""
    try:
        data = supabase.rpc("nda_status", {"p_version": nda["version"]}).execute().data
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def gate(st, supabase, user) -> None:
    """Show the NDA page and stop, until the signed-in account has signed the current NDA. Admins pass.
    While "enforce" is false in current.json (a draft), nobody is asked; admins can open a preview."""
    nda = current()
    if nda is None:
        return
    if st.session_state.get("nda_preview"):
        _page(st, supabase, user, nda, preview=True)
        st.stop()
    if not nda["enforce"]:
        return
    key = f"nda_ok_{nda['version']}"
    copy = st.session_state.pop("nda_just_signed", None)
    if copy:
        st.success("Thank you: the NDA is signed. A signed copy is on its way to your email.")
        st.download_button("📄 Download your signed copy", copy, file_name=f"signed-{nda['file']}",
                           mime="application/pdf", key="nda_copy_now")
    if st.session_state.get(key):
        return
    state = status(supabase, nda)
    if state is None or state.get("is_admin") or state.get("signed"):
        st.session_state[key] = True          # signed (or nothing to enforce yet): not asked again this session
        return
    _page(st, supabase, user, nda)
    st.stop()


def _page(st, supabase, user, nda: dict, preview: bool = False) -> None:
    import nda_component

    if preview:
        st.info("👀 **Preview**: this is the page testers see before they can use the dashboard"
                + ("" if nda["enforce"] else " (switched off for now: nobody is asked to sign yet)")
                + ". Signing here records nothing; you get a sample signed copy to download.")
        if st.button("✕ Close the preview", key="nda_preview_close"):
            st.session_state.pop("nda_preview", None)
            st.session_state.pop("nda_sample", None)
            st.rerun()
        sample = st.session_state.get("nda_sample")
        if sample:
            st.download_button("📄 Download the sample signed copy", sample, file_name=f"SAMPLE-signed-{nda['file']}",
                               mime="application/pdf", key="nda_sample_dl")
    st.markdown(f"## ✍️ {nda['title']}")
    st.markdown("Welcome to the Angstrom Signals closed beta. Before you start, please read and sign the beta "
                "non-disclosure agreement. It takes a minute, and you only do it once.")
    st.download_button("📄 Download the NDA (PDF)", nda["pdf"], file_name=nda["file"], mime="application/pdf",
                       key="nda_download")
    with st.container(height=420, border=True):
        st.markdown(nda["text"].replace("\n", "  \n") if nda["text"] else
                    "_The NDA could not be shown here: please download the PDF above and read it._")
    st.caption(f"Version {nda['version']} · document fingerprint {nda['sha256'][:16]}…")
    agreed = st.checkbox("I have read the NDA and agree to its terms.", key="nda_agree")
    full_name = st.text_input("Your full legal name", key="nda_name", max_chars=120)
    st.markdown("**Your signature**: draw it with your finger or mouse.")
    drawn = nda_component.pad(key="nda_pad")
    sent = getattr(drawn, "png", None) if drawn is not None else None
    if sent is not None:
        st.session_state["nda_png"] = sent         # kept until signing, whatever else redraws the page
    drawing = st.session_state.get("nda_png")
    if st.button("✍️ Sign and continue", type="primary", key="nda_sign"):
        problems = check_signature(full_name, agreed, drawing)
        if problems:
            for p in problems:
                st.error(p)
            return
        ip, agent = _request_details(st)
        reference = str(uuid.uuid4())
        when = datetime.now(timezone.utc)
        email = str(getattr(user, "email", "") or "")
        copy = signed_copy(nda, reference=reference, full_name=full_name, email=email,
                           user_id=str(getattr(user, "id", "")), drawing_png=drawing, signed_at=when, ip=ip,
                           user_agent=agent)
        if preview:
            st.session_state["nda_sample"] = copy
            st.rerun()
        try:
            supabase.rpc("nda_sign", {
                "p_reference": reference, "p_version": nda["version"], "p_sha256": nda["sha256"],
                "p_full_name": " ".join(full_name.split()), "p_drawing": drawing,
                "p_signed_pdf": base64.b64encode(copy).decode(), "p_ip": ip, "p_user_agent": agent}).execute()
        except Exception as exc:
            if "already_signed" not in str(exc):
                st.error(f"The signature could not be saved ({str(exc)[:160]}). Please try again.")
                return
        st.session_state[f"nda_ok_{nda['version']}"] = True
        st.session_state["nda_just_signed"] = copy
        st.rerun()
    st.caption("Signing records your typed name, your drawn signature, the time, your IP address and browser, and "
               "which version of the NDA you signed. You will get a signed copy by email.")


def admin_cell(row: dict, nda: dict | None) -> tuple[str, str, str]:
    """(text, tooltip, colour) for the NDA column of the beta requests table."""
    if nda is None:
        return "—", "No NDA is set up yet.", ""
    if row.get("account_admin"):
        return "Admin", "Admins don't sign the NDA.", ""
    if str(row.get("status") or "") != "approved":
        return "—", "Asked to sign after approval.", ""
    signed_at = str(row.get("nda_signed_at") or "")
    if row.get("nda_version") == nda["version"] and signed_at:
        when = signed_at[:10]
        return f"✍️ {when}", f"Signed version {nda['version']} on {when}.", "#15803d"
    if row.get("nda_version"):
        return "↻ Older", f"Signed version {row['nda_version']}; asked to sign {nda['version']} at next sign-in.", "#b45309"
    if not row.get("has_account"):
        return "⏳ No account", "Approved; signs when they first sign in.", "#b45309"
    return "⏳ Waiting", "Has an account but has not signed yet; asked at every sign-in.", "#b45309"
