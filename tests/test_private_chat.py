"""Private conversations in the general chat (17 Nov 2026): every message has an audience (everyone, a community, one
person), the database keeps it to that audience, replies keep it, and blocks and "who can message me" are honoured.
The rules themselves were checked against a real Postgres while building (sql/2026-12-02_private_chat.sql)."""

import ast
import os
import shutil
import subprocess
import tempfile

import pytest

import i18n
import market_store as ms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEA = "00000000-0000-0000-0000-00000000000b"


def test_a_new_message_goes_to_the_audience_asked_for():
    assert ms.chat_audience_fields(None) == {}
    assert ms.chat_audience_fields({"kind": "public"}) == {}
    assert ms.chat_audience_fields({"kind": "group", "id": 7}) == {"audience": "group", "group_id": 7}
    assert ms.chat_audience_fields({"kind": "direct", "id": BEA.upper()}) == {"audience": "direct", "recipient_id": BEA}
    # a private or community message with a bad address is refused, never posted publicly instead
    for bad in ({"kind": "direct", "id": "Bea"}, {"kind": "group", "id": "x"}, {"kind": "group", "id": 0},
                {"kind": "everyone"}):
        with pytest.raises(ValueError):
            ms.chat_audience_fields(bad)


class _Db:
    def __init__(self):
        self.inserted = []

    def table(self, name):
        self.name = name
        return self

    def insert(self, payload):
        self.inserted.append(payload)
        return self

    def select(self, *_):
        return self

    def eq(self, *_):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        class R:
            data = [{"id": 3, "parent_id": None}]
        return R()


def test_posting_carries_the_audience_and_a_reply_leaves_it_to_the_database():
    db = _Db()
    ms.post_chat(db, "me", "just us", to={"kind": "direct", "id": BEA})
    assert db.inserted[-1] == {"user_id": "me", "body": "just us", "audience": "direct", "recipient_id": BEA}
    ms.post_chat(db, "me", "a reply", parent_id=3, to={"kind": "group", "id": 9})
    assert db.inserted[-1] == {"user_id": "me", "body": "a reply", "parent_id": 3}     # the reply keeps the thread's


def test_the_feed_reads_the_audience_and_older_feeds_read_as_public():
    def row(**extra):
        return {"id": 1, "body": "hi", "author_name": "Bea", "created_at": "2026-11-17T00:00:00Z", **extra}

    assert ms._chat_audience(row())["audience"] == "public"
    direct = ms._chat_audience(row(audience="direct", recipient_id=BEA, recipient_name="Bea"))
    assert direct["to"] == BEA and direct["to_name"] == "Bea" and direct["group"] is None
    group = ms._chat_audience(row(audience="group", group_id=7, group_name="Swing"))
    assert group["group"] == 7 and group["group_name"] == "Swing" and group["to"] == ""
    assert ms._chat_audience(row(audience="??"))["audience"] == "public"


def test_find_a_person_needs_two_letters_and_returns_names_only():
    class Rpc:
        def rpc(self, name, args):
            assert name == "chat_find_people" and args == {"typed": "dr"}
            return self

        def execute(self):
            class R:
                data = [{"id": BEA, "name": "Drew", "avatar_url": None, "social_score": 4}, {"id": "bad", "name": "x"}]
            return R()

    assert ms.find_people(Rpc(), "d") == []
    found = ms.find_people(Rpc(), "dr")
    assert [p["name"] for p in found] == ["Drew"] and set(found[0]) == {"id", "name", "avatar", "social"}


def test_the_database_rules_are_in_place():
    sql = open(os.path.join(ROOT, "sql", "2026-12-02_private_chat.sql"), encoding="utf-8").read()
    for piece in ("chat_can_read(audience, user_id, group_id, recipient_id, auth.uid())",   # who may read
                  "public.chat_may_message(auth.uid(), recipient_id)",                       # blocks and dm_from
                  "new.audience := parent.audience",                                          # replies keep it
                  "not (me.blocked ? chat_messages.user_id::text)",                           # blocked are hidden
                  "revoke all on function public.chat_settings(uuid) from public, anon, authenticated"):
        assert piece in sql, piece
    assert "sql/2026-12-02_private_chat.sql" in open(os.path.join(ROOT, "supabase_rls.sql"), encoding="utf-8").read()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_the_whole_social_panel_script_parses():
    """The panel's script is put together from pieces, so the general script check skips it."""
    from score_colours import sentiment_tone_js

    source = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    node = next(n for n in ast.parse(source).body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "_SOCIAL_STREAM_JS")
    script = eval(compile(ast.Expression(node.value), "app.py", "eval"), {"sentiment_tone_js": sentiment_tone_js})
    assert "chatTarget" in script and "openPrivateChat" in script
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "panel.mjs")
        open(path, "w", encoding="utf-8").write(i18n.js_ready(script))
        result = subprocess.run([shutil.which("node"), "--check", path], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[:400]
