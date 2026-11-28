"""The worker emails each new feedback note and comment report to the admins once, and releases it if sending fails."""
import beta_worker


class Q:
    def __init__(self, db, table):
        self.db, self.table, self.op, self.vals, self.filters = db, table, "select", None, []

    def select(self, *_):
        return self

    def limit(self, *_):
        return self

    def is_(self, col, _):
        self.filters.append((col, None))
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def update(self, vals):
        self.op, self.vals = "update", vals
        return self

    def execute(self):
        rows = [r for r in self.db[self.table] if all(r.get(c) == v for c, v in self.filters)]
        if self.op == "update":
            for r in rows:
                r.update(self.vals)

        class R:
            data = rows
        return R()


class DB:
    def __init__(self):
        self.db = {
            "feedback_notes": [{"id": 1, "user_email": "a@x.io", "kind": "issue", "body": "Broken <b>", "images": ["u/1.jpg"], "emailed_at": None}],
            "comment_reports": [{"id": 2, "user_email": "b@x.io", "place": "chat", "message_kind": "reply", "asset_key": "",
                                 "comment_body": "buy now", "reason": "spam", "note": "", "emailed_at": None}],
        }

    def table(self, name):
        return Q(self.db, name)


def test_sends_once_with_screenshots_and_reply_to():
    db, sent = DB(), []
    send = lambda to, subj, page, plain, att, reply: sent.append((to, subj, att, reply, page)) or True
    n = beta_worker.send_admin_notices(db, send=send, admin_emails=["admin@x.io"], shots=lambda p: b"jpg")
    assert n == 2
    subjects = [s[1] for s in sent]
    assert "MarketNavi feedback: Issue" in subjects and "MarketNavi report: Spam" in subjects
    fb = sent[subjects.index("MarketNavi feedback: Issue")]
    assert fb[2] and fb[2][0]["filename"] == "screenshot-1.jpg" and fb[3] == "a@x.io"
    assert "&lt;b&gt;" in fb[4]
    assert beta_worker.send_admin_notices(db, send=send, admin_emails=["admin@x.io"]) == 0


def test_release_on_failure():
    db = DB()
    n = beta_worker.send_admin_notices(db, send=lambda *a: False, admin_emails=["admin@x.io"], shots=lambda p: None)
    assert n == 0
    assert all(r["emailed_at"] is None for t in db.db.values() for r in t)


def test_invite_emails_once_and_skip_joined(monkeypatch):
    db = DB()
    db.db["invites"] = [{"id": 7, "inviter_id": "u1", "email": "friend@x.io", "credited_at": None, "emailed_at": None},
                        {"id": 8, "inviter_id": "u1", "email": "in@x.io", "credited_at": "2026-01-01", "emailed_at": None}]
    db.db["profiles"] = []
    sent = []
    monkeypatch.setattr(beta_worker, "_inviter_names", lambda supabase, ids: {"u1": "Captain <Ada>"})
    n = beta_worker.send_invite_emails(db, send=lambda to, subj, page, plain: sent.append((to, page)) or True)
    assert n == 1 and sent[0][0] == "friend@x.io" and "Captain &lt;Ada&gt;" in sent[0][1]
    assert beta_worker.send_invite_emails(db, send=lambda *a: True) == 0
