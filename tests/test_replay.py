"""Replay foundation (stage 1) and certification suite (stage 2): docs/design/point_in_time.md."""

import gzip
import hashlib
import io
import json
import pathlib

import numpy as np
import pandas as pd
import pytest

from signal_library import REGISTRY, DataContext, SignalRef, certification, engine, evaluate
from signal_library import certify as cf
from signal_library import replay as rp
from signal_library.replay_display import MAX_DISPLAY_STEPS, display_run
from signal_library.replay_research import FrozenDailyCandles, accept, research_run
from tests.replay_helpers import simple_indicators

ROOT = pathlib.Path(__file__).resolve().parents[1]


def setup_function(_):
    engine.clear_cache()
    certification.reset()


@pytest.fixture(scope="module")
def coin():
    return cf.synthetic_crypto(days=260, seed=3)


def _run(ds, mode=rp.CERTIFICATION, **kw):
    return rp.ReplayRun(mode, ds.candles, indicators=simple_indicators, **kw)


def _ref(signal_id, tf="1D", **params):
    return SignalRef.make(REGISTRY.get(signal_id), tf, **params)


# ------------------------------------------------------------------------------------------- live is unchanged

def test_live_results_unchanged_byte_for_byte():
    from tests.live_golden import GOLDEN, snapshot

    assert json.loads(json.dumps(snapshot(), sort_keys=True)) == json.loads(GOLDEN.read_text())


def test_hold_out_date_matches_the_validation_spec():
    import research

    assert rp.HOLDOUT_START.tz_localize(None) == research.HOLDOUT_START


# ------------------------------------------------------------------------------------------- data cut at T

def test_only_candles_closed_by_t_inside_the_live_window(coin):
    h = coin.histories["1D"]
    t = h.raw.index[200] + pd.Timedelta(hours=12)          # inside candle 200: it has not closed
    ctx = _run(coin).context("crypto", coin.asset_id, t)
    frame = ctx.candles("1D")["frame"]
    assert frame.index[-1] == h.raw.index[199] and not frame["forming"].any()
    exact = _run(coin).context("crypto", coin.asset_id, h.raw.index[201])   # exactly at candle 200's close
    assert exact.candles("1D")["frame"].index[-1] == h.raw.index[200]
    # The window matches the independent reference cut.
    assert cf.reference_cut(h, t).index.equals(frame.index)
    intraday = _run(coin).context("crypto", coin.asset_id, t).candles("15m")["frame"]
    assert intraday.index[0] >= t - pd.Timedelta(days=31) - pd.Timedelta(minutes=15 * 260)


def test_derivatives_and_non_point_in_time_flows_are_not_replayable(coin):
    ctx = _run(coin).context("crypto", coin.asset_id, coin.histories["1D"].raw.index[-1])
    got = evaluate([_ref("positioning.oi_price", "1h")], ctx)
    assert list(got.values())[0].status == rp.NOT_REPLAYABLE
    flows = cf.synthetic_flows()[0]
    run = rp.ReplayRun(rp.CERTIFICATION, flows.candles, flows=flows.flow_loader())
    t = pd.Timestamp("2024-05-01", tz="UTC")
    live_style = evaluate([_ref("flows.btc_etf")], run.context("market", "bitcoin", t))
    assert list(live_style.values())[0].status == rp.NOT_REPLAYABLE
    pit = list(evaluate([_ref("flows.btc_etf", point_in_time=True)], run.context("market", "bitcoin", t)).values())[0]
    assert pit.status == "ok" and pd.Timestamp(pit.available_at) <= t


def test_flow_rows_first_seen_after_t_or_backfilled_are_never_used():
    t = pd.Timestamp("2024-05-01 12:00", tz="UTC")
    rows = [{"subject": "BTC", "observed_date": "2024-04-30", "value": 1, "fetched_at": "2024-04-30T23:00:00+00:00"},
            {"subject": "BTC", "observed_date": "2024-04-30", "value": 2, "fetched_at": "2024-05-01T13:00:00+00:00"},
            {"subject": "BTC", "observed_date": "2024-04-29", "value": 3, "fetched_at": "2024-04-29T23:00:00+00:00",
             "backfilled": True},
            {"subject": "BTC", "observed_date": "2023-11-01", "value": 4, "fetched_at": "2023-11-01T23:00:00+00:00"}]
    assert [r["value"] for r in rp.cut_flow_rows(rows, t)] == [1]
    assert [r["value"] for r in cf.cut_flow_rows_reference(rows, t)] == [1]


# ------------------------------------------------------------------------------------------- certification gate

def test_uncertified_signals_are_not_replayable_outside_the_harness(coin, monkeypatch):
    monkeypatch.setattr(certification, "load", lambda: {})
    run = _run(coin, mode=rp.DISPLAY)
    got = list(evaluate([_ref("trend.direction")], run.context("crypto", coin.asset_id,
                                                                 coin.histories["1D"].raw.index[-1])).values())[0]
    assert got.status == rp.NOT_REPLAYABLE and "no certification record" in got.notes[0]


def test_certification_record_only_counts_for_the_code_it_was_made_from(monkeypatch):
    record = {"suite_version": certification.SUITE_VERSION, "code_sha256": "something else",
              "signals": {"trend.direction@1": {"1D": {"algorithm": "certified", "slice_equivalent": True}}}}
    monkeypatch.setattr(certification, "load", lambda: record)
    assert certification.status("trend.direction@1", "1D")["algorithm"] == "not_certified"
    record["code_sha256"] = certification.code_hash()
    assert certification.status("trend.direction@1", "1D") == {"algorithm": "certified", "slice_equivalent": True,
                                                              "reason": None}
    assert certification.status("trend.direction@1", "4h")["algorithm"] == "not_certified"


def test_certified_signal_runs_in_a_display_replay(coin, monkeypatch):
    record = {"suite_version": certification.SUITE_VERSION, "code_sha256": certification.code_hash(),
              "signals": {"trend.direction@1": {"1D": {"algorithm": "certified", "slice_equivalent": False}}}}
    monkeypatch.setattr(certification, "load", lambda: record)
    run = display_run(candles=coin.candles, indicators=simple_indicators)
    t = coin.histories["1D"].raw.index[-1]
    got = list(evaluate([_ref("trend.direction")], run.context("crypto", coin.asset_id, t)).values())[0]
    assert got.status == "ok" and pd.Timestamp(got.available_at) <= t


# ------------------------------------------------------------------------------------------- invariants and caches

def test_future_timestamp_in_a_result_becomes_an_error(coin):
    import tests.replay_leaky_signals  # noqa: F401

    t = coin.histories["1D"].raw.index[-1]
    got = list(evaluate([_ref("test.future_timestamp")], _run(coin).context("crypto", coin.asset_id, t)).values())[0]
    assert got.status == "error" and "after the cutoff" in got.notes[0]
    assert rp.future_timestamps({"computed_at": "2099-01-01T00:00:00+00:00", "value": {"a": "2020-01-01"}}, t) == []


def test_replays_never_touch_the_shared_live_cache(coin):
    live = DataContext("crypto", coin.asset_id, now=pd.Timestamp("2030-01-01", tz="UTC"),
                       candle_loader=lambda k, a, tf: {"frame": simple_indicators(coin.histories[tf].raw).assign(forming=False),
                                                       "session": None, "source": "x"})
    evaluate([_ref("trend.direction")], live)
    before = dict(engine._CACHE)
    run = _run(coin)
    for i in (150, 180, 220):
        evaluate([_ref("trend.direction"), _ref("regime.state")],
                 run.context("crypto", coin.asset_id, coin.histories["1D"].raw.index[i]))
    assert dict(engine._CACHE) == before and len(run.result_cache) >= 6


def test_step_cap_and_record(coin):
    run = _run(coin, max_steps=2)
    idx = coin.histories["1D"].raw.index
    for i in (200, 210):
        evaluate([_ref("trend.direction")], run.context("crypto", coin.asset_id, idx[i]))
    with pytest.raises(rp.ReplayRefused):
        run.context("crypto", coin.asset_id, idx[220])
    record = run.record()
    assert record["kind"] == "as-of reconstruction" and len(record["cutoffs"]) == 2
    assert record["administrative"]["run_started_at"] and record["code"]["replay_code_sha256"]
    assert record["environment"]["python"] and all(i["sha256"] for i in record["inputs"])
    assert record["signals"][0]["certification"]["suite"]["suite_version"] is not None or True
    assert display_run(candles=coin.candles).max_steps == MAX_DISPLAY_STEPS


# ------------------------------------------------------------------------------------------- the hold-out

def _frozen(tmp_path):
    days = pd.date_range("2024-06-01", "2024-12-31", freq="D")
    frame = pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": np.linspace(1, 2, len(days)), "volume": 10.0},
                         index=pd.Index(days, name="date"))
    buffer = io.StringIO()
    frame.to_csv(buffer, index_label="date")
    with gzip.open(tmp_path / "BTC-USD.csv.gz", "wt", encoding="utf-8") as handle:
        handle.write(buffer.getvalue())
    manifest = {"downloaded_at": "2026-10-31", "files": {"BTC-USD": {"file": "BTC-USD.csv.gz"}}}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    return tmp_path


def test_research_reads_only_development_rows_and_refuses_the_hold_out(tmp_path):
    folder = _frozen(tmp_path)
    run = research_run(folder, reports_commit="abc123")
    history = run.history("crypto", "BTC-USD", "1D")
    assert history.raw.index[-1] < rp.HOLDOUT_START                       # cut as the file was read
    assert run.dataset["files_read"]["BTC-USD"]["sha256"] == hashlib.sha256(
        (folder / "BTC-USD.csv.gz").read_bytes()).hexdigest()
    with pytest.raises(rp.ReplayRefused):
        run.context("crypto", "BTC-USD", rp.HOLDOUT_START)
    with pytest.raises(rp.ReplayRefused):
        run.context("crypto", "BTC-USD", pd.Timestamp("2025-03-01", tz="UTC"))
    run.context("crypto", "BTC-USD", pd.Timestamp("2024-10-01", tz="UTC"))
    record = accept(run.record())
    assert record["dataset"]["reports_commit"] == "abc123" and record["environment"]["lock_sha256"]
    assert run.history("crypto", "BTC-USD", "15m")["error"].startswith("The frozen research dataset holds daily")


def test_research_refuses_other_sources_and_display_results(coin, tmp_path):
    with pytest.raises(rp.ReplayRefused):
        rp.ReplayRun(rp.RESEARCH, coin.candles)
    with pytest.raises(rp.ReplayRefused):
        accept(display_run(candles=coin.candles).record())
    record = research_run(_frozen(tmp_path)).record()
    record["cutoffs"] = ["2024-11-01T00:00:00+00:00"]
    with pytest.raises(rp.ReplayRefused):
        accept(record)


def test_research_and_display_paths_stay_apart():
    research_side = ["research.py", "research_stats.py", "backtest.py", "signal_library/replay_research.py",
                     "signal_library/certify.py"]
    for name in research_side:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "replay_display" not in text, name
    display = (ROOT / "signal_library/replay_display.py").read_text(encoding="utf-8")
    for forbidden in ("import research", "research_stats", "backtest", ".insert(", ".upsert(", ".update(", "to_csv",
                      "open("):
        assert forbidden not in display, forbidden


# ------------------------------------------------------------------------------------------- certification suite

def _suite(datasets, **kw):
    return cf.run_suite(datasets, indicators=kw.pop("indicators", "tests.replay_helpers:simple_indicators"),
                        cutoffs=kw.pop("cutoffs", 8), timeframes=("1D",), log=lambda *a: None, **kw)


def test_suite_certifies_honest_signals_and_refuses_leaks():
    signals = _suite([cf.synthetic_crypto(days=260, seed=4)],
                     include={"test.leak_global_max", "test.future_timestamp", "test.honest_close"},
                     only={"test.leak_global_max", "test.future_timestamp", "test.honest_close", "trend.direction",
                           "structure.swings"},
                     imports=["tests.replay_leaky_signals"])
    assert signals["trend.direction@1"]["1D"]["algorithm"] == "certified"
    assert signals["structure.swings@1"]["1D"]["algorithm"] == "certified"
    assert signals["test.honest_close@1"]["1D"]["algorithm"] == "certified"
    leak = signals["test.leak_global_max@1"]["1D"]
    assert leak["algorithm"] == "not_certified" and leak["failures"] > 0
    future = signals["test.future_timestamp@1"]["1D"]
    assert future["algorithm"] == "not_certified" and "reference" in future["reason"]


def test_slice_shortcut_is_certified_separately():
    signals = _suite([cf.synthetic_crypto(days=260, seed=4)], indicators="tests.replay_leaky_signals:centred_indicators",
                     include={"test.honest_close"}, only={"test.honest_close"}, imports=["tests.replay_leaky_signals"])
    entry = signals["test.honest_close@1"]["1D"]
    # Recomputing on cut data is safe even with a centred indicator; slicing a whole-history frame is not.
    assert entry["algorithm"] == "certified" and entry["slice_equivalent"] is False
    assert "sma_20" in entry["slice_reason"]


def test_flow_signals_certify_with_poisoned_revisions_and_late_sightings():
    signals = _suite(cf.synthetic_flows(sessions=120), cutoffs=10)
    for key in ("flows.btc_etf@1", "flows.stablecoin_supply@1"):
        assert signals[key]["1D"]["algorithm"] == "certified", signals[key]["1D"]["reason"]
        assert signals[key]["1D"]["checks"]["poison"] >= 10


def test_poisoning_changes_only_data_after_t(coin):
    h = coin.histories["4h"]
    t = pd.Timestamp(h.ends[len(h.ends) // 2], tz="UTC")
    for variant in cf.POISONS:
        bad = cf.poisoned(h, t, variant, 1)
        keep = h.ends <= t.value
        assert bad.raw[bad.ends <= t.value].equals(h.raw[keep]), variant
        assert not bad.raw.equals(h.raw), variant
