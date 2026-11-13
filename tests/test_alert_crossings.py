"""Border-crossing alerts: the colour zones, which crossing a move sends, and the settings board's data."""

import alert_bands_component as ab
import alerts as al


def test_zones_match_the_table_colours():
    assert [al.zone(v) for v in (-80, -50, -21, -20, 0, 19.9, 20, 49, 50, None)] == [-2, -2, -1, -1, 0, 0, 1, 1, 2, None]


def test_one_alert_per_move_the_furthest_ticked_border():
    every = list(al.CROSSINGS)
    assert al.crossing_for(0, 1, every) == "up_p20"
    assert al.crossing_for(0, 2, every) == "up_p50"                  # two borders at once: the furthest
    assert al.crossing_for(0, 2, ["up_p20"]) == "up_p20"
    assert al.crossing_for(-1, 1, every) == "flip_up"                # one side straight to the other
    assert al.crossing_for(-1, 1, ["up_p20"]) == "up_p20"            # flips unticked: the border speaks for it
    assert al.crossing_for(2, 1, every) == "dn_p50" and al.crossing_for(1, 0, every) == "dn_p20"
    assert al.crossing_for(-2, -1, every) == "up_m50" and al.crossing_for(-1, 0, every) == "up_m20"
    assert al.crossing_for(1, 1, every) is None and al.crossing_for(None, 1, every) is None
    assert al.crossing_for(1, 2, []) is None


def test_defaults_and_saved_ticks():
    assert al.reading_crossings({}, "trend") == list(al.DEFAULT_CROSSINGS["trend"])
    assert al.reading_crossings({"flow_crossings": ["up_p20", "nonsense"]}, "flow") == ["up_p20"]
    assert al.reading_crossings({"stretch_crossings": []}, "stretch") == []          # all unticked stays unticked


def test_messages_say_what_happened_in_plain_words():
    text = al.crossing_message("stretch", "dn_p50", 41, 2, 1)
    assert text.startswith("Stretch fades back from strongly bullish: +41 (Stretched up), was very stretched up.")
    assert "not forecasts" in text


def test_the_board_has_five_boxes_four_borders_and_two_flips():
    data = ab.board_data("trend", ["up_p20", "flip_dn", "junk"])
    assert [z["name"] for z in data["zones"]] == ["Strong downtrend", "Downtrend", "No clear trend", "Uptrend",
                                                    "Strong uptrend"]
    assert [b["label"] for b in data["borders"]] == ["−50", "−20", "+20", "+50"]
    assert data["borders"][2]["up"]["key"] == "up_p20" and "from no clear trend into uptrend" in data["borders"][2]["up"]["tip"]
    assert data["ticks"] == ["up_p20", "flip_dn"] and [f["key"] for f in data["flips"]] == ["flip_up", "flip_dn"]
