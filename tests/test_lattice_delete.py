"""Deleting your own Group or Set: refused while something is built on it; its table column goes with it."""

import lattice_delete as ld


def _set(cid, name, sources, owner="me", archived=False):
    groups = [{"key": f"g{i}", "provenance": {"source_config": s}} for i, s in enumerate(sources)]
    return {"id": cid, "kind": "set", "name": name, "owner_id": owner, "archived": archived,
            "versions": [{"version": 1, "body": {"groups": groups}}]}


def test_a_group_used_by_your_sets_is_named():
    saved = [_set("s1", "Pullback test", ["g-1"]), _set("s2", "Other", ["g-2"]),
             _set("s3", "Someone else's", ["g-1"], owner="you"), _set("s4", "Deleted", ["g-1"], archived=True)]
    assert ld.sets_using("g-1", saved, "me") == ["Pullback test"]
    assert ld.sets_using("g-9", saved, "me") == []
    msg = ld.blocked_message("group", ["A", "B"])
    assert "2 of your Sets: A, B" in msg and "Remove it from them first" in msg


def test_a_set_used_by_scans_is_named():
    scans = [{"name": "Daily dips", "set_source": {"config": "s1"}}, {"name": "Other", "set_source": {"key": "demo:x"}}]
    assert ld.scans_using("s1", scans) == ["Daily dips"]
    assert "1 of your scans: Daily dips" in ld.blocked_message("set", ["Daily dips"])


def test_its_table_column_is_removed():
    settings = {"table_columns": {"groups": ["starter:trend", "saved:g-1"], "sets": ["saved:s1"]}}
    assert ld.column_settings_without(settings, "saved:g-1") == {"groups": ["starter:trend"], "sets": ["saved:s1"]}
    assert ld.column_settings_without(settings, "saved:zzz") is None
    assert ld.column_settings_without({}, "saved:g-1") is None
