"""Every provided Set is built only from parts a user can find and copy (provided Groups, listed signals), so each
opens in the Set editor and saves back as the same check."""

import copy

import prism
import provided_groups_sql
import lattice_sets as ls
import signal_groups as sg
import table_columns


def _saved_like_the_database():
    """The provided Groups as the database lists them after sql/2026-11-15_provided_groups.sql."""
    out = []
    for n, (alias, (name, body)) in enumerate(prism.provided_groups().items()):
        out.append({"id": f"00000000-0000-0000-0000-00000000000{n}", "kind": "group", "name": name, "owner_id": None,
                    "starter_alias": alias, "current_version": 2,
                    "versions": [{"version": 1, "body": sg.starter(alias) if alias in sg.STARTERS else body},
                                 {"version": 2, "body": copy.deepcopy(body)}]})
    return out


def test_every_provided_set_opens_in_the_editor_and_saves_as_the_same_check():
    choices = ls.group_choices(_saved_like_the_database(), "me")
    for key, doc in table_columns.provided_sets().items():
        model, why = ls.from_document(copy.deepcopy(doc), choices)
        assert why is None, f"{key}: {why}"
        again = ls.to_document(model, choices)
        assert sg.validate_set(again) == [], key
        assert again["decision"] == doc["decision"], key
        for a, b in zip(again["groups"], doc["groups"]):
            assert sg.content_sha256(a["snapshot"]) == sg.content_sha256(b["snapshot"]), key
            assert a.get("subject") == b.get("subject"), key
        assert [(m["ref"], m.get("subject")) for m in again["standalone"]] == \
               [(m["ref"], m.get("subject")) for m in doc["standalone"]], key


def test_the_sql_file_is_up_to_date():
    assert provided_groups_sql.OUT.read_text(encoding="utf-8") == provided_groups_sql.text(), \
        "run python provided_groups_sql.py"


def test_provided_groups_show_once_without_versions():
    choices = ls.group_choices(_saved_like_the_database(), "me")
    names = [g["name"] for g in ls.state_for_screen(ls.empty_model(), choices)["groups"]]
    assert names == ["Trend", "Stretch", "Flow", "Trend (weekly)", "Recent structure break"]
