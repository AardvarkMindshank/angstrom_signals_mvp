"""Library completion (docs/design/library_completion.md): the ten component signals, the Trend/Stretch/Flow starter
Groups (same-input parity with signals_v2) and the sentiment signals."""

import json

import numpy as np
import pandas as pd
import pytest

import signal_groups as sg
import signals_v2 as v2
from signal_groups import lineage
from signal_library import REGISTRY, DataContext, SignalRef, certification, engine, evaluate
from signal_library import certify as cf
from signal_library import replay as rp
from signal_library.signals_components import COMPONENT_SIGNALS
from tests.replay_helpers import full_indicators

STARTER_OF = {"trend": "starter:trend", "stretch": "starter:stretch", "flow": "starter:flow"}


def setup_function(_):
    engine.clear_cache()


def _frames():
    """(label, frame) cases: normal histories, short ones (no SMA 200 or Ichimoku), no volume, no ATR, gaps."""
    out = []
    for seed in range(4):
        daily = full_indicators(cf.synthetic_crypto(days=420, seed=seed).histories["1D"].raw)
        for cut in (16, 40, 90, 199, 260, 420):
            out.append((f"s{seed}-{cut}", daily.iloc[:cut]))
        f = daily.copy()
        f["vol_sma_20"] = 0.0
        out.append((f"s{seed}-novolume", f))
        f = daily.copy()
        f["atr"] = np.nan
        out.append((f"s{seed}-noatr", f))
        f = daily.copy()
        f.loc[f.index[-1], ["ichi_span_a", "ichi_span_b", "stoch_k"]] = np.nan
        out.append((f"s{seed}-gaps", f))
    return out


def _group_values(frame, kind="crypto"):
    engine.clear_cache()   # the live cache keys on the last candle; the test varies other columns of the same frame
    data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
    ctx = DataContext(kind, "x", candle_loader=lambda k, a, tf: data, now=frame.index[-1] + pd.Timedelta(days=3))
    out = {}
    for cluster, alias in STARTER_OF.items():
        r = sg.evaluate_group(sg.starter(alias), ctx)
        observed = sum(1 for m in r["members"] if m.get("state") == "observed")
        out[cluster] = ((r["score"] or {}).get("value"), observed, len(r["members"]))
    return out


# ------------------------------------------------------------------------------------------- legacy authority

def test_signals_v2_split_into_component_functions_without_changing_results():
    """Every component and reading equals what the pre-split _components returned (frozen expectations)."""
    for label, frame in _frames()[:12]:
        row = frame.iloc[-1]
        comps, readings = v2._components(row, frame)
        for name, fn in v2.COMPONENT_FUNCTIONS.items():
            assert fn(row, frame)[0] == comps[name], (label, name)
        assert list(comps) == list(v2.CLUSTERS["trend"]["components"][:2]) + ["macd", "macd_acceleration", "momentum",
                                                                             "rsi", "stochastic", "bollinger", "obv",
                                                                             "heavy_volume"]
        assert "volume_ratio" in readings and "adx" in readings and "close" in readings


def test_existing_readings_and_their_consumers_are_untouched():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    for name in ("scoring.py", "signals_v2.py", "alerts.py", "run_alerts.py", "evidence.py", "digest.py",
                 "signal_matrix.py"):
        path = root / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            assert "signal_library" not in text and "signal_groups" not in text, name


# ------------------------------------------------------------------------------------------- the ten signals

def test_ten_component_signals_report_native_values_and_the_v2_standard_score():
    frame = full_indicators(cf.synthetic_crypto(days=300, seed=5).histories["1D"].raw)
    data = {"frame": frame.assign(forming=False), "session": None, "source": "test"}
    ctx = DataContext("crypto", "x", candle_loader=lambda k, a, tf: data)
    row = frame.iloc[-1]
    assert len(COMPONENT_SIGNALS) == 10 and set(COMPONENT_SIGNALS) == set(v2.COMPONENT_FUNCTIONS)
    for component, signal_id in COMPONENT_SIGNALS.items():
        ref = SignalRef.make(REGISTRY.get(signal_id), "1D")
        r = evaluate([ref], ctx)[ref.instance_key]
        assert r.status == "ok", signal_id
        assert r.value["standard_score"] == v2.COMPONENT_FUNCTIONS[component](row, frame)[0], signal_id
        assert len(r.value) > 1, f"{signal_id} reports a native value besides the standard score"
        assert r.evidence["definitions_fingerprint"] == v2.FINGERPRINT
        assert not r.notes
    ref = SignalRef.make(REGISTRY.get("rsi.level"), "4h")
    four = evaluate([ref], ctx)[ref.instance_key]
    assert "daily-derived scaling" in four.notes[0]


def test_existing_signal_contracts_unchanged_and_lineage_versions_coexist():
    assert lineage.CURRENT == 3
    v2_table, v3_table = lineage.table(2), lineage.table(3)
    assert all(v3_table[k] == v for k, v in v2_table.items())
    for sid in list(COMPONENT_SIGNALS.values()) + ["sentiment.market", "sentiment.asset"]:
        assert sid in v3_table and sid not in v2_table
    # Groups pinned to lineage 2 still validate and evaluate.
    for alias in ("starter:trend-confirmation", "starter:reversal-evidence"):
        assert sg.starter(alias)["lineage_version"] == 2 and sg.validate_group(sg.starter(alias)) == []


# ------------------------------------------------------------------------------------------- parity

def test_trend_stretch_flow_groups_equal_signals_v2_on_the_same_inputs():
    checked = 0
    for label, frame in _frames():
        now = frame.index[-1] + pd.Timedelta(days=3)
        legacy = v2.score(frame, "crypto", now)
        groups = _group_values(frame)
        for cluster in STARTER_OF:
            value, observed, total = groups[cluster]
            if legacy["status"] != "ok":
                assert value is None, (label, cluster)
                continue
            c = legacy["clusters"][cluster]
            assert [observed, total] == c["coverage"], (label, cluster)
            if c["value"] is None:
                assert value is None, (label, cluster)
            else:
                assert abs(value - c["value"]) < 1e-9, (label, cluster, value, c["value"])
                assert v2.percent(value) == c["percent"], (label, cluster)
            checked += 1
    assert checked > 60


def test_parity_at_rounding_boundaries():
    """Means that land exactly on a half-percent give the same displayed number."""
    cases = [[0.25, 0.0], [0.125, -0.125, 0.375], [0.005, 0.005], [-0.015, -0.015, -0.015, -0.015, -0.015],
             [0.99, 1.0], [-1.0, -0.99]]
    for values in cases:
        legacy = sum(values) / len(values)
        from fractions import Fraction
        group = float(sum(Fraction(str(v)) for v in values) / len(values))
        assert v2.percent(group) == v2.percent(legacy), values
    rng = np.random.default_rng(1)
    flips = 0
    for _ in range(20000):
        values = list(np.round(rng.uniform(-1, 1, rng.integers(1, 6)), 6))
        legacy = sum(values) / len(values)
        from fractions import Fraction
        group = float(sum(Fraction(str(v)) for v in values) / len(values))
        flips += v2.percent(group) != v2.percent(legacy)
    assert flips == 0


@pytest.mark.skipif(pytest.importorskip("importlib").util.find_spec("pandas_ta") is None,
                    reason="real indicators need pandas_ta (CI)")
def test_parity_with_the_real_indicator_library():
    from scoring import calculate_indicators

    for seed in range(3):
        raw = cf.synthetic_crypto(days=420, seed=seed).histories["1D"].raw
        frame = calculate_indicators(raw.copy())
        for cut in (60, 210, 420):
            f = frame.iloc[:cut]
            legacy = v2.score(f, "crypto", f.index[-1] + pd.Timedelta(days=3))
            groups = _group_values(f)
            for cluster in STARTER_OF:
                c = legacy["clusters"][cluster]
                value = groups[cluster][0]
                assert (value is None) == (c["value"] is None)
                if value is not None:
                    assert abs(value - c["value"]) < 1e-9 and v2.percent(value) == c["percent"]


def test_starters_describe_the_dashboard_readings():
    for cluster, alias in STARTER_OF.items():
        doc = sg.starter(alias)
        assert doc["question"] == v2.CLUSTERS[cluster]["question"]
        assert [m["key"] for m in doc["members"]] == v2.CLUSTERS[cluster]["components"]
        assert doc["score"]["min_coverage"] == {"num": 1, "den": len(doc["members"])}
        assert all(m["transform"]["field"] == "standard_score" for m in doc["members"])


# ------------------------------------------------------------------------------------------- sentiment

def _sentiment_ctx(rows, kind="market", asset="crypto", now="2024-06-28 12:00"):
    return DataContext(kind, asset, sentiment_loader=lambda key: {"rows": rows} if rows else {"error": "none"},
                       now=pd.Timestamp(now, tz="UTC"))


def _row(when, score, coverage="ok", first_seen=None):
    return {"score": score, "recorded_at": when, "first_seen_at": first_seen or when, "model": "m",
            "coverage": coverage, "events": 5, "sources": 4}


def test_sentiment_reports_score_change_coverage_and_staleness_from_the_evaluation_time():
    rows = [_row("2024-06-20T10:00:00+00:00", 40.0), _row("2024-06-21T10:00:00+00:00", 55.0),
            _row("2024-06-28T09:00:00+00:00", 75.0, coverage="thin")]
    ref = SignalRef.make(REGISTRY.get("sentiment.market"), "1D")
    r = evaluate([ref], _sentiment_ctx(rows))[ref.instance_key]
    assert r.status == "ok" and r.value["score"] == 50.0 and r.value["shown"] == 50
    assert r.value["change_7d"] == 50.0 - 10.0            # vs the newest score at least 7 days before now
    assert r.value["thin_news"] and "thin news" in r.notes[0]
    engine.clear_cache()
    later = evaluate([ref], _sentiment_ctx(rows, now="2024-06-30 12:00"))[ref.instance_key]
    assert later.status == "stale"
    engine.clear_cache()
    early = evaluate([ref], _sentiment_ctx(rows, now="2024-06-21 12:00"))[ref.instance_key]
    assert early.value["score"] == 10.0 and early.value["change_7d"] is None


def test_missing_sentiment_is_missing_not_neutral():
    ref = SignalRef.make(REGISTRY.get("sentiment.asset"), "1D")
    r = evaluate([ref], _sentiment_ctx([], kind="crypto", asset="sui"))[ref.instance_key]
    assert r.status == "missing_data" and r.value is None
    from signal_library.signals_sentiment import subject_key

    assert subject_key(DataContext("crypto", "SUI")) == "Crypto|sui"
    assert subject_key(DataContext("equity", "aapl")) == "Stock|AAPL"
    assert subject_key(DataContext("market", "stocks")) == "stock"


def test_sentiment_replay_uses_database_receipt_time_not_recorded_at(monkeypatch):
    record = {"suite_version": certification.SUITE_VERSION, "code_sha256": certification.code_hash(),
              "signals": {"sentiment.market@1": {"1D": {"algorithm": "certified"}}}}
    monkeypatch.setattr(certification, "load", lambda: record)
    rows = [_row("2024-06-26T10:00:00+00:00", 60.0),
            # Recorded before T but only received after T: a backfill, must not count.
            _row("2024-06-27T10:00:00+00:00", 95.0, first_seen="2024-06-29T00:00:00+00:00")]
    run = rp.ReplayRun(rp.DISPLAY, lambda *a: {"error": "none"},
                       sentiment=lambda key, as_of: {"rows": rows})
    t = pd.Timestamp("2024-06-28 00:00", tz="UTC")
    ref = SignalRef.make(REGISTRY.get("sentiment.market"), "1D")
    got = evaluate([ref], run.context("market", "crypto", t))[ref.instance_key]
    assert got.value["score"] == 20.0 and pd.Timestamp(got.available_at) <= t
    no_column = rp.ReplayRun(rp.DISPLAY, lambda *a: {"error": "none"},
                             sentiment=lambda key, as_of: {"rows": [{"score": 50, "recorded_at": "2024-06-26"}]})
    blocked = evaluate([ref], no_column.context("market", "crypto", t))[ref.instance_key]
    assert blocked.status == "missing_data" and "first_seen_at" in blocked.notes[0]


def test_suite_certifies_sentiment_with_backfill_poisoning():
    signals = cf.run_suite(cf.synthetic_sentiment(days=90), indicators="tests.replay_helpers:simple_indicators",
                           cutoffs=10, timeframes=("1D",), log=lambda *a: None)
    for key in ("sentiment.market@1", "sentiment.asset@1"):
        entry = signals[key]["1D"]
        assert entry["algorithm"] == "certified", entry["reason"]
        assert entry["checks"]["poison"] >= 10


def test_sentiment_signals_are_documented_and_in_the_catalogue():
    import pathlib

    text = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "signal_library_catalogue.md").read_text()
    for sid in list(COMPONENT_SIGNALS.values()) + ["sentiment.market", "sentiment.asset"]:
        assert f"`{sid}@1`" in text
    d = REGISTRY.get("sentiment.market")
    assert "first reached the database" in d.limitations and d.scope == "market:crypto|stocks"


def test_sql_adds_first_seen_without_letting_callers_set_it():
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    sql = (root / "sql" / "2026-11-05_sentiment_first_seen.sql").read_text()
    assert "add column if not exists first_seen_at timestamptz not null default now()" in sql
    writer = (root / "sql" / "2026-11-03_sentiment_history.sql").read_text()
    assert "first_seen_at" not in writer         # the writing function never supplies it
    json.dumps({})
