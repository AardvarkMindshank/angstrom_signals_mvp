import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")


def test_social_groups_are_called_communities():
    assert '"👥 Communities", "my_groups"' in APP  # same section id, so saved open/closed state is kept
    assert "My Groups" not in APP


def test_browser_and_server_use_the_same_member_message():
    # The social stream recognises this server message by its exact text.
    assert APP.count("They are already in that community.") >= 3
    assert "They are already in that group." not in APP


def test_database_notifications_use_community_wording():
    sql = (ROOT / "supabase_rls.sql").read_text(encoding="utf-8")
    migration = (ROOT / "sql" / "2026-11-03_communities_wording.sql").read_text(encoding="utf-8")
    for text in (sql, migration):
        assert "' invited you to the community '" in text and "' joined your community '" in text
        assert "' invited you to the group '" not in text and "' joined your group '" not in text
