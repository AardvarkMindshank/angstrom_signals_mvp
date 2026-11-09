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


def test_only_the_newest_provided_group_version_is_offered():
    import lattice_sets as ls
    import prism

    body = prism.labelled_starter("starter:trend")
    saved = [{"id": "s1", "kind": "group", "name": "Trend agreement", "owner_id": None, "starter_alias": "starter:x",
              "current_version": 2, "versions": [{"version": 1, "body": body}, {"version": 2, "body": body}]},
             {"id": "m1", "kind": "group", "name": "Mine", "owner_id": "me", "starter_alias": None,
              "current_version": 2, "versions": [{"version": 1, "body": body}, {"version": 2, "body": body}]}]
    choices = ls.group_choices(saved, "me")
    shown = [g["source"] for g in ls.state_for_screen(ls.empty_model(), choices)["groups"]]
    assert shown == ["saved:s1:2", "saved:m1:1", "saved:m1:2"]
    assert "saved:s1:1" in choices                      # still readable for Sets that embed it
