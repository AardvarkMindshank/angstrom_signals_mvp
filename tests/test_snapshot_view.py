"""Quick Snapshot's Tides line and funnel tiles (snapshot_view.py)."""

from datetime import datetime, timezone

import snapshot_view as sv

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)


def test_tides_line_says_the_tide_in_both_words_and_links_to_tides():
    snap = {"tide": {"status": "ok", "label": "out", "held_days": 7},
            "sea": {"status": "ok", "state": "moderate", "plain": "normal volatility"}}
    line = sv.tides_line(snap, NOW)
    assert "data-pick='tides'" in line
    assert "Tide going out" in line and "risk-defensive" in line
    assert "Sea moderate" in line and "normal volatility" in line


def test_tides_line_is_empty_without_a_reading():
    assert sv.tides_line(None, NOW) == ""
    assert sv.tides_line({"tide": {"status": "no data"}}, NOW) == ""


def test_next_event_is_ahead_and_prefers_a_major_one():
    e = sv.next_event(NOW)
    assert e is None or (e["at"] >= NOW)


def test_candidate_changes_against_the_last_visit():
    assert sv.candidate_changes(None, ["a", "b"]) == ([], [])       # first visit: nothing is new
    assert sv.candidate_changes(["a", "b"], ["b", "c"]) == (["c"], ["a"])
    assert sv.candidate_changes(["a"], ["a"]) == ([], [])


def test_funnel_tiles_open_their_funnel_and_show_changes():
    tiles = [{"id": "f1", "name": "Trend crypto longs ▲", "market": "crypto", "direction": "long", "paused": False,
              "line": "120 → 41 → 9 ✅ / 7 🚩", "candidates": 9, "flagged": 7, "candidate_names": ["BTC"],
              "new": ["SOL", "ETH"], "gone": [], "seen": True},
             {"id": "f2", "name": "Equity <shorts>", "market": "equity", "direction": "short", "paused": True,
              "line": "", "candidates": 0, "flagged": 0, "candidate_names": [], "new": [], "gone": [], "seen": True}]
    out = sv.funnel_tiles(tiles)
    assert "data-pick='funnel|f1|Trend crypto longs ▲'" in out
    assert "＋2 new" in out and "SOL, ETH" in out
    assert "no change" in out and "paused" in out
    assert "Equity &lt;shorts&gt;" in out           # names are escaped
    assert sv.funnel_tiles([]) == ""


def test_no_funnels_tile_opens_the_table_in_dynamic_funnel():
    out = sv.no_funnels_tile("equity")
    assert "data-pick='funnel_new|equity'" in out and "Make one" in out
