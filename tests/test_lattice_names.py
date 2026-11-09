"""Saving a new Group or Set never makes a second one with the same name."""

import lattice_view as lv

SAVED = [{"id": "a", "kind": "set", "name": "My Set", "owner_id": "me", "versions": [{}]},
         {"id": "b", "kind": "set", "name": "Old", "owner_id": "me", "archived": True, "versions": [{}]},
         {"id": "c", "kind": "set", "name": "Shared", "owner_id": "you", "versions": [{}]},
         {"id": "d", "kind": "group", "name": "Trend", "owner_id": "me", "versions": [{}]}]


def test_name_taken_is_per_owner_kind_and_ignores_case_spaces_and_deleted():
    assert lv.name_taken(SAVED, "me", "set", "my  set ")
    assert not lv.name_taken(SAVED, "me", "set", "Old")          # deleted ones free their name
    assert not lv.name_taken(SAVED, "me", "set", "Shared")       # someone else's
    assert not lv.name_taken(SAVED, "me", "set", "Trend")        # a Group, not a Set
    assert lv.name_taken(SAVED, "me", "group", "TREND")


def test_message_offers_the_next_version_when_that_set_is_open():
    text = lv.taken_message("Set", "My Set", {"name": "My Set", "current_version": 1})
    assert "Save as version 2" in text
    assert "Save as version" not in lv.taken_message("Set", "My Set", None)
