"""The new app's NDA gate (service/nda_page.py) follows nda.py's own rules."""
from types import SimpleNamespace

from service import nda_page


class _Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return SimpleNamespace(data=self.data)


class _Db:
    def __init__(self, state, email="tester@example.com", made="2026-11-25T00:00:00Z"):
        self.state, self.calls = state, []
        self.auth = SimpleNamespace(get_user=lambda token: SimpleNamespace(user=SimpleNamespace(email=email, created_at=made)))

    def rpc(self, name, args=None):
        self.calls.append(name)
        return _Rpc(self.state if name == "nda_status" else 1)


def test_unsigned_tester_is_asked_and_signed_one_is_not():
    assert nda_page.info(_Db({"is_admin": False, "signed": False}), "t")["needed"] is True
    assert nda_page.info(_Db({"is_admin": False, "signed": True}), "t")["needed"] is False
    assert nda_page.info(_Db({"is_admin": True, "signed": False}), "t")["needed"] is False


def test_exempt_and_older_accounts_are_not_asked():
    assert nda_page.info(_Db({"signed": False}, email="demo@angstromsignals.com"), "t")["needed"] is False
    assert nda_page.info(_Db({"signed": False}, made="2025-01-01T00:00:00Z"), "t")["needed"] is False


def test_signing_checks_the_form_and_preview_records_nothing():
    db = _Db({"is_admin": False, "signed": False})
    bad = nda_page.sign(db, "u", "t", "", "", False, "", False, "", "")
    assert bad["ok"] is False and len(bad["problems"]) == 4
    assert nda_page.sign(db, "u", "t", "A B", "TH", True, "", True, "", "")["ok"] is False   # preview: admins only
    assert "nda_sign" not in db.calls
