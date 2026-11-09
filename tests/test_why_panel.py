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


def test_week_change_and_sentences():
    import why_panel as wp

    scores = [10] * 20 + [12, 20, 25, 30, 35, 40, 42, 44]
    assert wp.week_change(scores) == 44 - 12
    assert wp.week_change([None] * 10) is None
    assert wp.group_sentence("Trend", 44, "Bullish", 32) == \
        "Trend reads bullish (+44); it has risen 32 points over the past week."
    assert "barely changed" in wp.group_sentence("Trend", 44, "Bullish", 2)
    dates = [f"2026-11-{d:02d}" for d in range(1, 11)]
    answers = ["no"] * 3 + ["yes"] * 2 + ["no"] * 5
    assert wp.set_sentence(answers, dates) == "No for 5 days; last Yes on 5 Nov (Yes on 2 of the last 10 days)."
    assert wp.set_sentence(["yes"] * 10, dates) == "Yes for all of the last 10 days."


def test_trend_reads_each_close_and_feeds_the_card(monkeypatch):
    import pandas as pd

    import set_history
    import signal_groups as sg
    import why_panel as wp

    frame = pd.DataFrame({"close": range(40)}, index=pd.date_range("2026-10-01", periods=40, freq="D", tz="UTC"))
    monkeypatch.setattr(set_history, "context_at", lambda f, k, day, a, history=None: (day, day))
    monkeypatch.setattr(sg, "evaluate_group", lambda doc, day: {
        "score": {"value": (day.day % 10) / 10},
        "members": [{"key": "a", "state": "observed", "contribution": 0.1}]})
    spec = {"cluster": None, "doc": {"members": []}, "part": "groups", "key": "k", "name": "Mine"}
    t = wp.trend(spec, frame, "Crypto", "bitcoin")
    assert len(t["dates"]) == 30 and len(t["scores"]) == 30 and t["parts"]["a"] == [10] * 30
    item = {"part": "groups", "name": "Mine", "percent": t["scores"][-1], "label": "Neutral",
            "rows": [{"key": "a", "role": "score", "name": "a", "percent": 10, "text": "", "share": 1}]}
    wp.with_trend(item, t)
    html = wp.block_html(item)
    assert "why-line" in html and "Mine reads neutral" in html and "→ 0 this week" in html
