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
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "beta_requests"
        return Query(self, name)


def test_only_email_decisions_are_sent_and_only_once():
    db = Db([
        {"id": 1, "name": "May", "email": "may@x.test", "status": "approved", "decided_via": "email", "notified_at": None},
        {"id": 2, "name": "Bob", "email": "bob@x.test", "status": "declined", "decided_via": "email", "notified_at": None},
        {"id": 3, "name": "Dash", "email": "d@x.test", "status": "approved", "decided_via": "dashboard", "notified_at": None},
        {"id": 4, "name": "Done", "email": "e@x.test", "status": "approved", "decided_via": "email", "notified_at": "2026-01-01"},
        {"id": 5, "name": "Wait", "email": "w@x.test", "status": "pending", "decided_via": None, "notified_at": None},
    ])
    sent = []
    count = run_alerts.send_beta_decision_emails(db, send=lambda to, subject, page, plain: sent.append((to, subject)) or True)
    assert count == 2
    assert sorted(to for to, _ in sent) == ["bob@x.test", "may@x.test"]
    assert any("You are in" in subject for _to, subject in sent)
    assert any("beta request" in subject for _to, subject in sent)
    again = run_alerts.send_beta_decision_emails(db, send=lambda *a: sent.append(a) or True)
    assert again == 0 and len(sent) == 2


def test_failed_send_is_released_for_the_next_run():
    db = Db([{"id": 1, "name": "May", "email": "may@x.test", "status": "approved", "decided_via": "email", "notified_at": None}])
    assert run_alerts.send_beta_decision_emails(db, send=lambda *a: False) == 0
    assert db.rows[0]["notified_at"] is None
    assert run_alerts.send_beta_decision_emails(db, send=lambda *a: True) == 1
    assert db.rows[0]["notified_at"] is not None
