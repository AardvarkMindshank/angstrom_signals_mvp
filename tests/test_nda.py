"""Beta NDA signing: the document, the signature, the signed copy, the gate, the admin column and the emailed copies.
A made-up NDA; no database."""

from __future__ import annotations

import base64
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import beta_emails
import beta_worker
import nda

ROOT = Path(__file__).resolve().parent.parent


def _pdf(text="This is a test non-disclosure agreement. The tester keeps beta features confidential.") -> bytes:
    from reportlab.pdfgen import canvas

    out = io.BytesIO()
    c = canvas.Canvas(out)
    c.drawString(72, 720, text)
    c.showPage()
    c.drawString(72, 720, "Page two of the agreement.")
    c.save()
    return out.getvalue()


def _png() -> str:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (600, 170), "white")
    d = ImageDraw.Draw(im)
    d.line([(20, 120), (120, 40), (220, 130), (320, 50), (420, 140), (560, 60)], fill="black", width=5)
    out = io.BytesIO()
    im.save(out, "PNG")
    return base64.b64encode(out.getvalue()).decode()


@pytest.fixture
def nda_dir(tmp_path, monkeypatch):
    (tmp_path / "nda.pdf").write_bytes(_pdf())
    (tmp_path / "current.json").write_text(json.dumps({"version": "draft-1", "file": "nda.pdf", "title": "Beta NDA"}))
    monkeypatch.setattr(nda, "NDA_DIR", tmp_path)
    return tmp_path


def test_no_nda_set_up_means_nothing_is_asked(tmp_path):
    assert nda.current(tmp_path) is None


def test_the_current_nda_has_a_version_a_fingerprint_and_readable_text(nda_dir):
    doc = nda.current(nda_dir)
    assert doc["version"] == "draft-1" and len(doc["sha256"]) == 64 and doc["enforce"] is True
    assert "confidential" in doc["text"] and "Page two" in doc["text"]
    (nda_dir / "current.json").write_text(json.dumps({"version": "draft-1", "file": "nda.pdf", "enforce": False}))
    assert nda.current(nda_dir)["enforce"] is False


def test_a_signature_needs_the_tick_a_name_and_a_drawing():
    assert nda.check_signature("Ann Lee", True, _png()) == []
    problems = nda.check_signature(" ", False, "")
    assert len(problems) == 3
    blank = base64.b64encode(b"\x89PNG" + b"0" * 10).decode()
    assert nda.check_signature("Ann Lee", True, blank) == ["Draw your signature in the box."]


def test_the_signed_copy_is_the_nda_plus_a_signature_page(nda_dir):
    from pypdf import PdfReader

    doc = nda.current(nda_dir)
    copy = nda.signed_copy(doc, reference="ref-123", full_name="Ann  Lee", email="ann@example.com", user_id="u1",
                           drawing_png=_png(), signed_at=datetime(2026, 11, 6, 4, 5, tzinfo=timezone.utc),
                           ip="203.0.113.9", user_agent="Mobile Safari")
    pages = PdfReader(io.BytesIO(copy)).pages
    assert len(pages) == 3
    last = pages[-1].extract_text()
    for words in ("Ann Lee", "ann@example.com", "06 November 2026, 04:05:00", doc["sha256"], "ref-123",
                  "203.0.113.9", "draft-1"):
        assert words in last, words
    assert pages[0].extract_text() == PdfReader(io.BytesIO(doc["pdf"])).pages[0].extract_text()


class Stop(Exception):
    pass


class FakeSt:
    def __init__(self, button=False, **inputs):
        self.session_state = {}
        self.inputs = {"nda_agree": True, "nda_name": "Ann Lee", **inputs}
        self.press = button
        self.shown = []
        self.context = type("C", (), {"headers": {"X-Forwarded-For": "203.0.113.9, 10.0.0.1", "User-Agent": "Safari"}})()

    def stop(self):
        raise Stop()

    def rerun(self):
        raise Stop()

    def markdown(self, text, *a, **k):
        self.shown.append(text)

    caption = info = success = error = markdown

    def download_button(self, *a, **k):
        self.shown.append("download")

    def container(self, *a, **k):
        import contextlib

        return contextlib.nullcontext()

    def checkbox(self, label, key=None, **k):
        return self.inputs.get(key)

    def text_input(self, label, key=None, **k):
        return self.inputs.get(key)

    def button(self, label, key=None, **k):
        return self.press and key == "nda_sign"


class FakeDb:
    def __init__(self, state):
        self.state, self.calls = state, []

    def rpc(self, name, args):
        self.calls.append((name, args))
        out = type("O", (), {})()
        out.data = self.state if name == "nda_status" else 1
        out.execute = lambda: out
        return out


USER = type("U", (), {"id": "u1", "email": "ann@example.com"})()


def test_the_gate(nda_dir, monkeypatch):
    import nda_component

    monkeypatch.setattr(nda_component, "pad", lambda key: type("R", (), {"png": _png()})())
    st = FakeSt()
    nda.gate(st, FakeDb({"is_admin": True, "signed": False}), USER)            # admins pass
    st = FakeSt()
    nda.gate(st, FakeDb({"is_admin": False, "signed": True}), USER)            # signed: passes, remembered
    assert st.session_state["nda_ok_draft-1"]
    st = FakeSt()
    with pytest.raises(Stop):
        nda.gate(st, FakeDb({"is_admin": False, "signed": False}), USER)       # unsigned: only the NDA page
    assert any("Beta NDA" in s for s in st.shown if isinstance(s, str))
    db = FakeDb({"is_admin": False, "signed": False})
    st = FakeSt(button=True)
    with pytest.raises(Stop):
        nda.gate(st, db, USER)
    name, args = db.calls[-1]
    assert name == "nda_sign" and args["p_version"] == "draft-1" and args["p_full_name"] == "Ann Lee"
    assert args["p_ip"] == "203.0.113.9" and args["p_user_agent"] == "Safari" and len(args["p_sha256"]) == 64
    assert base64.b64decode(args["p_signed_pdf"]).startswith(b"%PDF") and st.session_state["nda_ok_draft-1"]
    nda.gate(FakeSt(), FakeDb(None), USER)                                    # tables not installed: not blocked


def test_a_draft_asks_nobody_and_the_admin_preview_records_nothing(nda_dir, monkeypatch):
    import nda_component

    monkeypatch.setattr(nda_component, "pad", lambda key: type("R", (), {"png": _png()})())
    (nda_dir / "current.json").write_text(json.dumps({"version": "draft-1", "file": "nda.pdf", "enforce": False}))
    nda.gate(FakeSt(), FakeDb({"is_admin": False, "signed": False}), USER)     # draft: not asked
    st = FakeSt(button=True)
    st.session_state["nda_preview"] = True
    db = FakeDb({"is_admin": True, "signed": False})
    with pytest.raises(Stop):
        nda.gate(st, db, USER)
    assert not [c for c in db.calls if c[0] == "nda_sign"] and st.session_state["nda_sample"].startswith(b"%PDF")


def test_the_admin_column(nda_dir):
    doc = nda.current(nda_dir)
    cell = lambda **r: nda.admin_cell({"status": "approved", **r}, doc)[0]
    assert cell(status="pending") == "—" and cell(account_admin=True) == "Admin"
    assert cell(has_account=False) == "⏳ No account" and cell(has_account=True) == "⏳ Waiting"
    assert cell(nda_version="draft-1", nda_signed_at="2026-11-06T04:05:00+00:00") == "✍️ 2026-11-06"
    assert cell(nda_version="draft-0", nda_signed_at="2026-10-01") == "↻ Older"
    assert nda.admin_cell({"status": "approved"}, None)[0] == "—"


class CopyDb:
    def __init__(self, rows):
        self.rows, self.updates = rows, []

    def table(self, name):
        db = self

        class Q:
            def __init__(self):
                self.payload = None

            def select(self, *a):
                return self

            def is_(self, *a):
                return self

            def limit(self, *a):
                return self

            def eq(self, *a):
                return self

            def update(self, payload):
                self.payload = payload
                db.updates.append(payload)
                return self

            def execute(self):
                self.data = [{"id": 1}] if self.payload is not None else db.rows
                return self
        return Q()


def test_signed_copies_are_emailed_to_the_signer_and_admins():
    rows = [{"id": 1, "reference": "ref-1", "email": "ann@example.com", "full_name": "Ann Lee", "nda_version": "draft-1",
             "signed_at": "2026-11-06T04:05:00+00:00", "signed_pdf": base64.b64encode(b"%PDF-1.4").decode()}]
    sent = []
    db = CopyDb(rows)
    n = beta_worker.send_nda_copies(db, send=lambda to, s, p, t, a=None: sent.append((to, s, a)) or True,
                                    admin_emails=["boss@example.com", "ann@example.com"])
    assert n == 1 and [t for t, _, _ in sent] == ["ann@example.com", "boss@example.com"]
    assert sent[0][2][0]["content"] == rows[0]["signed_pdf"] and sent[0][2][0]["filename"].endswith(".pdf")
    db = CopyDb(rows)
    assert beta_worker.send_nda_copies(db, send=lambda *a: False, admin_emails=[]) == 0
    assert db.updates[-1] == {"emailed_at": None}                              # released, retried next run


def test_the_welcome_email_mentions_the_nda_only_when_it_is_on():
    assert "non-disclosure" in beta_emails.welcome_email("Ann", "https://x", nda=True)[2]
    assert "non-disclosure" not in beta_emails.welcome_email("Ann", "https://x", nda=False)[2]


def test_the_sql_keeps_signatures_unchangeable_and_owner_or_admin_only():
    sql = (ROOT / "sql" / "2026-11-09_beta_nda.sql").read_text()
    assert "revoke all on public.nda_signatures from public, anon, authenticated" in sql
    assert "grant update" not in sql and "grant delete" not in sql and "grant insert" not in sql
    assert "unique (user_id, nda_version)" in sql and "already_signed" in sql and "public.is_admin()" in sql
    assert "'nda_signed_at', s.signed_at" in sql and "'status', r.status" in sql


def test_the_dashboard_asks_for_the_nda_right_after_sign_in():
    app = (ROOT / "app.py").read_text()
    gate = app.index("_nda.gate(st, supabase, st.session_state.user)")
    assert app.index("user_id = st.session_state.user.id") < gate < app.index("def load_profile")
