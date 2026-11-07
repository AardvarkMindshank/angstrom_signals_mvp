"""What a Group or Set looks at, worked out from its ingredients, and the provided explanations."""

import perspectives as p
import prism
import signal_groups as sg


def test_icons_come_from_the_ingredients():
    sets = prism.demo_sets()
    assert p.of_doc(sets["demo:breakout"]) == ["volume", "structure"]
    assert p.of_doc(sets["demo:pullback"]) == ["trend", "stretch"]
    assert p.of_doc(sets["demo:btc_filter"]) == ["trend", "other"]          # pinned to Bitcoin: 🔭
    assert p.of_doc(sets["demo:entry"]) == ["trend", "stretch", "sentiment"]
    assert p.of_doc(sg.starter("starter:flow")) == ["volume"]
    assert p.icons(sets["demo:squeeze"]) == "🌊"
    assert p.of_doc({}) == [] and p.of_doc(None) == []


def test_every_provided_item_explains_itself():
    for key in list(prism.demo_sets()) + list(sg.STARTERS):
        e = p.explain(key)
        assert e and all(len(e[k]) > 15 for k in ("line", "measures", "why", "not_proven")), key
        assert e["evidence"][0] == "🔬"
    assert p.explain("saved:abc") is None


def test_data_marks():
    assert p.data_mark("Complete")[0] == "●" and p.data_mark("Partial")[0] == "◐"
    assert p.data_mark("None") == ("○", "No data") and p.data_mark(None)[0] == "◐"


def test_library_chips_carry_icons_line_more_and_evidence():
    import prism_board as pb

    choices = pb.set_choices([], "me")
    lib = pb.library(choices, [("crypto", "bitcoin", "Bitcoin")])
    chip = next(s for s in lib["sets"] if s["key"] == "demo:breakout")
    assert [c["icon"] for c in chip["icons"]] == ["🔊", "🧱"] and chip["line"].startswith("An upward break")
    assert set(chip["more"]) == {"measures", "why", "not_proven"} and chip["evidence"]["icon"] == "🔬"
    assert [x["key"] for x in lib["perspectives"]][:3] == ["trend", "stretch", "volume"]
