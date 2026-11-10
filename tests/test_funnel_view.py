"""The funnel on the page (funnel_view.py): picker counts, the coins each choice shows, and the stage hover."""

import pandas as pd

import funnel as fn
import funnel_templates as ft
import funnel_view as fv
from funnel import NO, YES

F = {**ft.trend_funnel("long"), "id": "f", "stages_version": 1}


def _coin(answers):
    st = fn.CoinState.new(4)
    for k, a in answers:
        fn.record(st, k, a, "2026-11-10T00:00:00+00:00", "EMA 20 vs 50: fast_below")
    return st


STATES = {"btc": _coin([(0, YES), (1, YES), (2, YES), (3, YES)]), "sol": _coin([(0, YES), (1, YES), (2, YES)]),
          "eth": _coin([(0, YES), (1, NO), (1, NO)]), "doge": _coin([(0, NO)])}


def test_picker_and_choices():
    labels = dict(fv.picks(F, STATES, 4))
    assert labels["stage:0"].endswith("· 3") and labels["stage:2"].endswith("· 2")
    assert labels["flagged"] == "🚩 Flagged · 1" and labels["candidate"] == "✅ Candidates · 1"
    assert fv.coins_for("stage:0", STATES) == ["btc", "sol", "eth"]
    assert fv.coins_for("candidate", STATES) == ["btc"] and fv.coins_for("flagged", STATES) == ["sol"]
    assert fv.counts_line(F, STATES, 4) == "4 → 3 → 2 → 2 → 1 ✅ / 1 🚩"


def test_stage_hover_explains():
    icon, hover, _ = fv.stage_cell(F, STATES["sol"])
    assert icon == "▲🚩" and "waiting for the 1-hour entry conditions" in hover
    icon, hover, _ = fv.stage_cell(F, STATES["eth"])
    assert icon == "▲👁" and "12-hour: No" in hover and "fast_below" in hover
    _, hover, _ = fv.stage_cell(F, STATES["doge"])
    assert hover.startswith("In the pool")


def test_health_warns_on_failed_or_late_runs():
    now = pd.Timestamp("2026-11-10 12:00", tz="UTC")
    ok = [{"cutoff": "2026-11-10T00:00:00+00:00", "status": "ok"}, None, None, None]
    assert fv.health(ok, F, now) is None
    bad = [{"cutoff": "2026-11-10T00:00:00+00:00", "status": "failed", "error": "Binance down"}, None, None, None]
    assert "failed" in fv.health(bad, F, now)
    late = [{"cutoff": "2026-11-07T00:00:00+00:00", "status": "ok"}, None, None, None]
    assert "has not been checked" in fv.health(late, F, now)
