"""🔍 Why these readings: one block per table column, agreeing with the table."""

import pandas as pd

import group_readings as gr
import signals_v2 as v2
import table_columns as tc
import why_panel as wp
from signal_library import certify as cf
from signal_library import engine
from tests.replay_helpers import full_indicators


def _saved():
    import sys
    sys.path.insert(0, "video")
    import seed

    return seed.configs({"pullback"})


def _ctx():
    frame = full_indicators(cf.synthetic_crypto(days=420, seed=11).histories["1D"].raw)
    engine.clear_cache()
    later = frame.index[-1] + pd.Timedelta(days=3)
    ctx, _ = gr.stored_context(frame, "crypto", later, asset_id="x")
    return ctx, gr.score(frame, "crypto", later)


def test_blocks_follow_the_columns_and_agree_with_the_readings():
    ctx, result = _ctx()
    specs = tc.resolve({"groups": ["starter:trend", "starter:stretch", "starter:flow", "saved:cfg-my-trend"],
                        "sets": ["saved:cfg-pullback"]}, _saved())
    items = wp.items(specs, ctx, result["readings"])
    assert [i["key"] for i in items] == [s["key"] for s in specs]
    for item, cluster in zip(items, ("trend", "stretch", "flow")):
        c = result["clusters"][cluster]
        assert item["percent"] == c["percent"] and item["label"] == c["label"]
        # every part, with the dashboard's plain words
        assert [r["percent"] for r in item["rows"]] == [x["percent"] for x in c["components"].values()]
        names = list(c["components"])
        assert item["rows"][0]["text"] == v2.component_reading(names[0], result["readings"])
        assert item["lattice"] == f"lattice|groups|starter:{cluster}"
    assert items[3]["lattice"] == "lattice|groups|cfg-my-trend" and items[3]["rows"]
    s = items[4]
    assert s["answer"] in ("yes", "no", "unknown") and len(s["rows"]) == 2 and s["note"]
    html = "".join(wp.block_html(i) for i in items)
    assert "Named views" not in html and "Moving averages" in html


def test_background_columns_show_their_stored_answer():
    spec = {"key": "saved:f", "part": "sets", "name": "Fast", "config": "f", "version": 1, "cluster": None,
            "doc": {"members": [{"ref": {"timeframe": "1h"}}]}}
    waiting = wp.background_item(spec, None)
    assert "no answer yet" in waiting["title"] and "background" in waiting["note"]
    got = wp.background_item(spec, {"answer": "yes", "why": "all lines hold", "as_of": "2026-11-04T08:00:00+00:00"})
    assert got["title"].startswith("✓ Fast · Yes") and "all lines hold" in got["note"]
