"""Beta decision emails: the wording, and the worker that sends them exactly once."""
import beta_emails
import beta_worker as run_alerts


def test_welcome_and_declined_wording():
    subject, page, plain = beta_emails.welcome_email("Ana <b>Maria</b>", "https://app.example/")
    assert "You are in" in subject and "Hi Ana" in plain and "<b>" not in page
    assert "https://app.example/" in page
    subject, page, plain = beta_emails.declined_email("")
    assert "Hi there" in plain and "not able to offer you one" in plain


class Query:
    def __init__(self, db, name):
        self.db, self.name, self.filters, self.patch = db, name, {}, None

    def select(self, *_a):
        return self

    def update(self, patch):
        self.patch = patch
        return self

    def eq(self, key, value):
        self.filters[key] = ("eq", value)
        return self

    def is_(self, key, value):
        self.filters[key] = ("null", None)
        return self

    def in_(self, key, values):
        self.filters[key] = ("in", values)
        return self

    def limit(self, _n):
        return self

    def _match(self, row):
        for key, (kind, value) in self.filters.items():
            have = row.get(key)
            if kind == "eq" and have != value:
                return False
            if kind == "null" and have is not None:
                return False
            if kind == "in" and have not in value:
                return False
        return True

    def execute(self):
        rows = [row for row in self.db.rows if self._match(row)]
        if self.patch is not None:
            for row in rows:
                row.update(self.patch)
        return type("R", (), {"data": [dict(row) for row in rows]})()


class Db:
    def __init__(self, rows, table="beta_requests"):
        self.rows, self.name = rows, table

    def table(self, name):
        assert name == self.name
        return Query(self, name)


def test_only_declines_go_from_decisions_and_only_once():
    db = Db([
        {"id": 1, "name": "May", "email": "may@x.test", "status": "approved", "decided_via": "email", "notified_at": None},
        {"id": 2, "name": "Bob", "email": "bob@x.test", "status": "declined", "decided_via": "email", "notified_at": None},
        {"id": 3, "name": "Dash", "email": "d@x.test", "status": "approved", "decided_via": "dashboard", "notified_at": None},
        {"id": 5, "name": "Wait", "email": "w@x.test", "status": "pending", "decided_via": None, "notified_at": None},
    ])
    sent = []
    count = run_alerts.send_beta_decision_emails(db, send=lambda to, subject, page, plain: sent.append((to, subject)) or True)
    assert count == 1 and sent[0][0] == "bob@x.test" and "beta request" in sent[0][1]
    assert db.rows[0]["notified_at"] is not None          # the approval is claimed; its welcome goes from the access list
    assert run_alerts.send_beta_decision_emails(db, send=lambda *a: sent.append(a) or True) == 0 and len(sent) == 1


def test_welcome_carries_the_link_and_goes_once():
    db = Db([{"email": "may@x.test", "request_id": None, "welcomed_at": None},
             {"email": "old@x.test", "request_id": None, "welcomed_at": "2026-01-01"}], table="beta_access")
    sent = []
    n = run_alerts.send_welcome_links(db, send=lambda to, subject, page, plain: sent.append((to, page)) or True,
                                      link=lambda _db, address: f"https://auth.example/verify?for={address}")
    assert n == 1 and sent[0][0] == "may@x.test" and "https://auth.example/verify?for=may@x.test" in sent[0][1]
    assert "Set your password" in sent[0][1]
    assert run_alerts.send_welcome_links(db, send=lambda *a: True, link=lambda *a: "x") == 0


def test_failed_welcome_is_released_and_barred_note_goes_once():
    db = Db([{"email": "may@x.test", "request_id": None, "welcomed_at": None}], table="beta_access")
    assert run_alerts.send_welcome_links(db, send=lambda *a: False, link=lambda *a: "") == 0
    assert db.rows[0]["welcomed_at"] is None
    bars = Db([{"email": "spam@x.test", "notified_at": None}], table="email_blacklist")
    got = []
    assert run_alerts.send_barred_notes(bars, send=lambda to, subject, *a: got.append(subject) or True) == 1
    assert "barred" in got[0] and run_alerts.send_barred_notes(bars, send=lambda *a: True) == 0
