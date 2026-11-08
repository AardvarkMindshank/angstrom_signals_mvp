import numpy as np
import pandas as pd
import pytest

import what_followed as wf


def _series(values, start="2020-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"))


def _prices(n=900, seed=1, drift=0.0, start="2016-01-01"):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(drift + rng.normal(0, 0.02, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, n)))
    return pd.DataFrame({"high": high, "low": low, "close": close},
                        index=pd.date_range(start, periods=n, freq="D"))


def test_fresh_yes_needs_a_gap_of_no_candles():
    a = _series(["no"] * 6 + ["yes", "yes", "no", "no", "yes"] + ["no"] * 5 + ["yes"])
    assert list(wf.episodes(a)) == [a.index[6], a.index[16]]


def test_unknown_does_not_count_towards_the_gap_and_needs_a_no_before():
    a = _series(["no"] * 5 + ["yes"] + ["no", "unknown", "no", "no", "no", "yes"])
    assert list(wf.episodes(a)) == [a.index[5]]                  # only 4 No candles before the second Yes
    b = _series(["no"] * 6 + ["unknown", "yes"])
    assert list(wf.episodes(b)) == []                            # Unknown, then Yes: not seen turning from No


def test_gain_first_walks_from_the_next_close():
    n = 40
    close = np.full(n, 100.0)
    high, low = close + 0.5, close - 0.5                      # true range 1 => typical move 1
    f = pd.DataFrame({"high": high, "low": low, "close": close}, index=pd.date_range("2020-01-01", periods=n))
    f.iloc[25, f.columns.get_loc("high")] = 101.2             # day 25 touches entry + 1
    t = wf.outcomes(f, horizon=10, lag=1)
    assert t["first"].iloc[20] == 1.0                         # entry at day 21; day 25 is inside the window
    assert t["first"].iloc[26] == 0.0                         # nothing touched after day 25
    assert np.isnan(t["first"].iloc[10])                      # no typical move yet (20 candles needed)
    f.iloc[25, f.columns.get_loc("low")] = 98.8               # both in one candle: ambiguous
    assert wf.outcomes(f, horizon=10, lag=1)["first"].iloc[20] == 0.0


def test_windows_stop_before_the_hold_out():
    f = _prices(n=400, start="2023-10-01")
    t = wf.outcomes(f)
    last = t["move"].dropna().index.max()
    assert last + pd.Timedelta(days=wf.HORIZON + wf.LAG) < wf.HOLDOUT
    assert t.index.max() < wf.HOLDOUT


def test_comparable_days_are_same_year_and_same_side_of_the_average():
    f = _prices(n=1200, seed=3, drift=0.001)
    t = wf.outcomes(f)
    answers = pd.Series("no", index=t.index)
    answers.iloc[600] = "yes"
    rows = wf.differences(answers, t)
    assert len(rows) == 1
    day = rows["date"].iloc[0]
    same = t[(t["year"] == t.loc[day, "year"]) & (t["above"] == t.loc[day, "above"]) & (answers == "no")]
    assert rows["move_usual"].iloc[0] == pytest.approx(same["move"].dropna().mean())


def test_too_few_weeks_says_too_few_to_judge():
    rows = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=12, freq="D"), "asset": "A", "kind": "crypto",
                         **{f"{m}{s}": 0.1 for m in wf.ALL_MEASURES for s in ("", "_usual", "_diff")}})
    out = wf.study({"k": rows}, {"k": "directional"}, runs=200)
    assert out["sets"]["k"]["verdict"] == "Too few to judge"


def test_filter_sets_get_no_verdict():
    out = wf.study({"demo:btc_filter": pd.DataFrame()}, {"demo:btc_filter": "filter"}, runs=200)
    assert out["sets"]["demo:btc_filter"]["verdict"] is None


def _random_study(seed, n_assets=12, rate=0.03):
    """Random-walk prices and Yes answers that are pure chance."""
    rng = np.random.default_rng(seed)
    per_set = {}
    for k in range(3):
        parts = []
        for a in range(n_assets):
            f = _prices(n=2200, seed=seed * 100 + a, drift=0.0004, start="2017-01-01")
            t = wf.outcomes(f)
            yes = rng.random(len(t)) < rate / 3
            yes = pd.Series(yes).rolling(3, min_periods=1).max().astype(bool).to_numpy()   # short runs of Yes
            answers = pd.Series(np.where(yes, "yes", "no"), index=t.index)
            rows = wf.differences(answers, t)
            rows["asset"], rows["kind"] = f"A{a}", "crypto" if a % 2 else "equity"
            parts.append(rows)
        per_set[f"s{k}"] = pd.concat(parts, ignore_index=True)
    return wf.study(per_set, {k: "directional" for k in per_set}, runs=400, seed=seed)


def test_pure_chance_rarely_shows_a_difference():
    claims = total = 0
    for seed in range(6):
        out = _random_study(seed)
        for s in out["sets"].values():
            total += 1
            claims += s["verdict"] == "Consistent difference"
            assert s["verdict"] != "Too few to judge"
    assert claims <= 1, f"{claims} of {total} chance-only Sets showed a consistent difference"


def test_a_real_effect_is_found():
    """Yes on days before a known rise: the study should notice."""
    per_set = {}
    parts = []
    for a in range(12):
        f = _prices(n=2200, seed=500 + a, drift=0.0, start="2017-01-01")
        rng = np.random.default_rng(a)
        yes_days = np.sort(rng.choice(np.arange(250, 2150), 70, replace=False))
        close = f["close"].to_numpy().copy()
        for d in yes_days:                                    # a lift after each Yes
            close[d + 2:] *= 1.04
        f["close"], f["high"], f["low"] = close, close * 1.01, close * 0.99
        t = wf.outcomes(f)
        answers = pd.Series("no", index=t.index)
        answers.iloc[yes_days] = "yes"
        rows = wf.differences(answers, t)
        rows["asset"], rows["kind"] = f"A{a}", "crypto" if a % 2 else "equity"
        parts.append(rows)
    per_set["s"] = pd.concat(parts, ignore_index=True)
    out = wf.study(per_set, {"s": "directional"}, runs=400)
    assert out["sets"]["s"]["verdict"] == "Consistent difference", out["sets"]["s"]
    assert out["sets"]["s"]["plain"]["gain_first"] > out["sets"]["s"]["plain"]["gain_first_usual"]


def test_card_belongs_to_the_exact_set(monkeypatch):
    import perspectives
    import prism

    doc = prism.demo_sets()["demo:pullback"]
    fake = {"start": "2014-09-17", "through": "2024-10-29", "sets": {"demo:pullback": {
        "type": "directional", "verdict": "No clear difference", "rests_on": None, "episodes": 212, "weeks": 180,
        "assets": 80, "coins": 70, "shares": 142, "top_assets": [["BTC-USD", 0.05]], "first": "2014-10-01",
        "last": "2024-10-01", "hash": wf.logic_hash(doc),
        "plain": {"gain_first": 0.56, "gain_first_usual": 0.52, "loss_first": 0.4, "loss_first_usual": 0.42,
                  "move": 0.31, "move_usual": 0.22, "higher": 0.55, "higher_usual": 0.53},
        "tests": {"first": {"consistency": {"checked": ["before 2019", "2019 to 2021", "2022 to Oct 2024", "coins",
                                                        "shares"], "same_way": ["before 2019", "coins", "shares"]}}}}}}
    monkeypatch.setitem(perspectives._results, "data", fake)
    card = perspectives.followed_card(doc, "demo:pullback")
    text = " ".join(card["lines"])
    assert "212 separate times" in text and "56%" in text and "comparable days 52%" in text
    assert "1 of 3 periods" in text and "BTC 5%" in text and card["verdict"] == "No clear difference"
    assert perspectives.evidence(doc, "demo:pullback")[0] == "⚖️"
    renamed = dict(doc, name="My pullback")
    assert perspectives.followed_card(renamed) is not None              # a renamed copy keeps its study
    changed = json_copy(doc)
    changed["rules"] = [{"changed": True}]
    assert perspectives.followed_card(changed) is None                  # any change to its logic does not
    assert perspectives.evidence(changed)[0] == "🔬"


def json_copy(d):
    import json

    return json.loads(json.dumps(d))
