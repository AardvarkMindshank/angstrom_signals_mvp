"""A Study finished note opens its Set (study_link.py)."""

import prism
import study_link as sl
import what_followed as wf


def test_finds_the_set_by_fingerprint_then_by_name():
    a, b = prism.demo_sets()["demo:breakout"], prism.demo_sets()["demo:squeeze"]
    configs = [{"id": "c1", "kind": "set", "name": "Mine", "current_version": 2,
                "versions": [{"version": 1, "body": a}, {"version": 2, "body": b}]},
               {"id": "g1", "kind": "group", "name": "Mine", "versions": []}]
    assert sl.find_set(configs, wf.logic_hash(a)) == ("c1", 1)
    assert sl.find_set(configs, "", "Mine") == ("c1", 2)
    assert sl.find_set(configs, "nope", "Other") is None
    assert sl.pick_value({"asset_symbol": "study:abc", "asset_name": "My|Set"}) == "study|abc|My Set"
