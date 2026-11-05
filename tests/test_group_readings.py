"""Stage 6: Trend, Stretch and Flow across the app come from the starter Groups. Synthetic data only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import group_readings as gr
import signal_groups as sg
import signals_v2 as v2
from signal_library import certify as cf
from signal_library import engine
from tests.replay_helpers import full_indicators

ROOT = Path(__file__).resolve().parent.parent


def setup_function(_):
    engine.clear_cache()


def _frames():
    yield "crypto", full_indicators(cf.synthetic_crypto(days=420, seed=11).histories["1D"].raw)
    yield "stock", full_indicators(cf.synthetic_equity(days=420, seed=23).histories["1D"].raw)


def test_same_numbers_bands_and_coverage_as_before_at_many_cutoffs():
    checked = 0
    for kind, frame in _frames():
        for pos in range(15, len(frame) + 1, 9):
            window = frame.iloc[:pos]
            now = window.index[-1] + pd.Timedelta(days=3)
            old = v2.score(window, kind, now)
            engine.clear_cache()
            new = gr.score(window, kind, now)
            assert new["status"] == old["status"]
            if old["status"] != "ok":
                continue
            assert new["source"] == "groups" and new["version"] == gr.VERSION
            for c in v2.CLUSTERS:
                a, b = old["clusters"][c], new["clusters"][c]
                assert b["percent"] == a["percent"] and b["coverage"] == a["coverage"], (kind, pos, c)
                assert (a["value"] is None) == (b["value"] is None)
                if a["value"] is not None:
                    assert abs(a["value"] - b["value"]) < 1e-9
                    assert gr.WORDS[c].index(b["label"]) == v2.CLUSTER_WORDS[c].index(a["label"]), (kind, pos, c)
                else:
                    assert b["label"] == gr.UNKNOWN_LABEL
                assert {k: v["percent"] for k, v in b["components"].items()} == \
                    {k: v["percent"] for k, v in a["components"].items()}
                assert b["group"]["completeness"] in ("Complete", "Partial", "None")
            assert new["against_trend"] == old["against_trend"]
            assert {k: v["percent"] for k, v in new["lenses"].items()} == {k: v["percent"] for k, v in old["lenses"].items()}
            assert new["context"] == old["context"] and new["readings"] == old["readings"]
            assert gr.flat_fields(new)["trend"] == v2.flat_fields(old)["trend"]
            checked += 1
    assert checked > 50


@pytest.mark.parametrize("value,word", [(0.5, 0), (0.2, 1), (0.19, 2), (-0.19, 2), (-0.2, 3), (-0.49, 3), (-0.5, 4)])
def test_band_edges_match_the_old_wording(value, word):
    doc = gr.dashboard_group("trend")
    assert sg.validate_group(doc) == []
    old = v2._band(value, v2.CLUSTER_WORDS["trend"])
    assert v2.CLUSTER_WORDS["trend"].index(old) == word
    rules = doc["outcomes"]["rules"]
    hit = next((r for r in rules if ("gte" in r["when"]["score"] and value >= r["when"]["score"]["gte"]) or
                ("lte" in r["when"]["score"] and value <= r["when"]["score"]["lte"])), None)
    label = hit["label"] if hit else doc["outcomes"]["otherwise"]["label"]
    assert gr.WORDS["trend"].index(label) == word


def test_every_dashboard_group_is_valid_and_labels_fit():
    for c in gr.STARTERS:
        doc = gr.dashboard_group(c)
        assert sg.validate_group(doc) == [], c
        assert all(len(w) <= 24 for w in gr.WORDS[c])


def test_no_data_and_short_history_keep_the_old_messages():
    assert gr.score(None, "crypto")["status"] == "no_data"
    frame = next(_frames())[1].iloc[:10]
    assert gr.score(frame, "crypto")["status"] == "no_data"


def test_the_app_alerts_matrix_and_evidence_read_the_groups():
    import re

    for name in ("app.py", "run_alerts.py", "signal_matrix.py", "signals_view.py"):
        text = (ROOT / name).read_text()
        assert not re.search(r"signals_v2\.score\(|v2\.score\(", text), name
    assert "group_readings" in (ROOT / "signals_view.py").read_text()
    assert "group_readings" in (ROOT / "run_alerts.py").read_text()


def test_angstrom_lattice_has_four_parts_and_draws_only_the_chosen_one():
    import lattice_panel as lp

    assert lp.TITLE == "Angstrom Lattice"
    assert [lp.SECTIONS[k][1] for k in lp.SECTIONS] == ["Signal Groups", "Signal Sets", "Prism Scan", "Strategies"]
    assert all(lp.SECTIONS[k][0].startswith(":material/") for k in lp.SECTIONS)
    assert lp.label("strategies").endswith("(soon)")
    app = (ROOT / "app.py").read_text()
    assert 'st.expander("Angstrom Lattice", icon=":material/hub:"' in app
    drawn = []

    class St:
        def markdown(self, *a, **k):
            pass

        def caption(self, *a, **k):
            pass

        def segmented_control(self, *a, **k):
            return "strategies"

        def info(self, text, *a, **k):
            drawn.append(text)
    lp.render(St(), None, [], "u")
    assert len(drawn) == 1 and "coming later" in drawn[0]
