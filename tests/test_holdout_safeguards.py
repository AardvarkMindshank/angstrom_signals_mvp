"""Once-only guard, crash recovery, concurrent runs, preflight isolation and time invariance.
Synthetic data and local git repositories only."""

import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import research as rs
import research_stats as st

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("holdout_attempts", ROOT / ".github/scripts/holdout_attempts.py")
ha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ha)


# ----------------------------------------------------------------------------- recovery policy

def test_policy_first_attempt_and_completed():
    assert ha.decide([], None)[0]
    assert not ha.decide([], "123")[0]                                         # nothing to recover
    done = [{"run_id": "1", "final_stage": "outputs_written"}]
    assert not ha.decide(done, None)[0] and not ha.decide(done, "1")[0]       # never again


@pytest.mark.parametrize("stage", [None, "guards_passed", "data_loaded", "scored", "checks_passed",
                                   "statistics_computed"])
def test_policy_unfinished_attempt_needs_explicit_recovery(stage):
    attempts = [{"run_id": "7", "final_stage": stage}]
    assert not ha.decide(attempts, None)[0]            # crash after data access is NOT a free re-run
    assert not ha.decide(attempts, "6")[0]             # must name the latest attempt
    assert ha.decide(attempts, "7")[0]


def test_policy_caps_attempts():
    attempts = [{"run_id": str(i), "final_stage": "scored"} for i in range(ha.MAX_ATTEMPTS)]
    assert not ha.decide(attempts, str(ha.MAX_ATTEMPTS - 1))[0]


# ----------------------------------------------------------------------------- atomic claim on a real git remote

def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def remote_and_clones(tmp_path):
    remote = tmp_path / "remote.git"
    git("init", "-q", "--bare", str(remote), cwd=tmp_path)
    seed = tmp_path / "seed"
    git("init", "-q", str(seed), cwd=tmp_path)
    (seed / "README").write_text("reports\n")
    git("add", "README", cwd=seed)
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "seed", cwd=seed)
    git("push", "-q", str(remote), "HEAD:reports", cwd=seed)
    clones = []
    for name in ("a", "b"):
        c = tmp_path / name
        git("clone", "-q", str(remote), str(c), cwd=tmp_path)
        clones.append(c)
    return remote, clones


def test_concurrent_claims_only_one_wins(remote_and_clones):
    remote, (a, b) = remote_and_clones
    results = {}

    def a_wins_the_race():                              # A claims while B is between reading and pushing
        results["a"] = ha.claim(str(a), "100", "1", "sha", "h", None)

    results["b"] = ha.claim(str(b), "200", "1", "sha", "h", None, before_push=a_wins_the_race)
    assert results["a"][0] is True
    assert results["b"][0] is False and "100" in results["b"][1]
    record = json.loads(git("show", "reports:holdout/attempts.json", cwd=remote))
    assert [r["run_id"] for r in record] == ["100"]


def test_crash_then_recovery_then_never_again(remote_and_clones, tmp_path):
    remote, (a, b) = remote_and_clones
    assert ha.claim(str(a), "100", "1", "sha", "h", None)[0]
    log = tmp_path / "stage.log"
    log.write_text("t guards_passed\nt data_loaded\nt scored\n")             # crashed after reading data
    assert ha.finish(str(a), "100", str(log))[0]
    assert not ha.claim(str(b), "200", "1", "sha", "h", None)[0]             # plain re-run refused
    assert ha.claim(str(b), "200", "1", "sha", "h", "100")[0]                # explicit recovery allowed
    log.write_text("t guards_passed\nt data_loaded\nt scored\nt checks_passed\nt statistics_computed\n"
                   "t outputs_written\n")
    assert ha.finish(str(b), "200", str(log))[0]
    assert not ha.claim(str(a), "300", "1", "sha", "h", "200")[0]            # completed: never again
    record = json.loads(git("show", "reports:holdout/attempts.json", cwd=remote))
    assert [(r["run_id"], r["kind"], r["final_stage"]) for r in record] == [
        ("100", "first", "scored"), ("200", "recovery", "outputs_written")]


# ----------------------------------------------------------------------------- stage markers on a crash

def test_crash_after_data_access_leaves_the_stage_on_disk(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", rs.HOLDOUT_TAG)
    monkeypatch.setattr(rs, "checked_start_from_manifest", lambda *_: rs.HOLDOUT_START)
    monkeypatch.setattr(rs, "load_cache", lambda *a, **k: {})

    def boom(*_):
        raise RuntimeError("runner died while scoring")

    monkeypatch.setattr(rs, "score_all", boom)
    with pytest.raises(RuntimeError):
        rs.run_holdout("p", str(tmp_path), rs.HOLDOUT_TAG, rs.HOLDOUT_SPEC_HASH)
    stages = [line.split()[-1] for line in (tmp_path / "stage.log").read_text().splitlines()]
    assert stages == ["guards_passed", "data_loaded"]
    assert not (tmp_path / "holdout.json").exists()


# ----------------------------------------------------------------------------- preflight isolation

def fake_scores(frames):
    """Deterministic stand-in for the live scoring, computed only from each frame's own rows."""
    out = {}
    for t, f in frames.items():
        if t == "^GSPC":
            continue
        c = f["close"]
        d = pd.DataFrame(index=f.index)
        for name in rs.FACTORS:
            d[name] = 0.0
        d["Moving Averages"] = 4 * np.sign(c - c.rolling(20).mean())
        d["Performance"] = (c.pct_change(7) * 40).clip(-4, 4)
        d["RSI"] = -np.sign(c.pct_change(3))
        d["score"] = 50 + d[list(rs.FACTORS)].sum(axis=1)
        d["x_adx"] = 20.0
        d["x_atr_pct"] = (f["high"] - f["low"]).div(c).rolling(14).mean() * 100
        out[t] = rs.add_families(d.iloc[30:])
    return out


def write_cache(folder: Path, frames):
    files = {}
    for t, f in frames.items():
        name = rs.ticker_file(t)
        f.index.name = "date"
        rs.save_frame(f, folder / name)
        files[t] = {"file": name, "bars": len(f), "first": str(f.index[0])[:10], "last": str(f.index[-1])[:10]}
    (folder / "manifest.json").write_text(json.dumps({"files": files, "failed": {}}))


def make_universe(seed, poison_holdout=False):
    rng = np.random.default_rng(seed)
    poison_rng = np.random.default_rng(seed + 1000)        # separate stream: development prices stay identical
    frames = {}
    tickers = [s for s in rs.UNIVERSE_STOCKS[2:14]] + [c for c in rs.UNIVERSE_CRYPTO[:12]] + ["^GSPC"]
    for t in tickers:
        idx = (pd.date_range("2021-01-01", "2026-10-30", freq="D") if t.endswith("-USD")
               else pd.bdate_range("2021-01-01", "2026-10-29"))
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, len(idx))))
        f = pd.DataFrame({"open": close, "high": close * 1.02, "low": close * 0.98, "close": close,
                          "volume": 1e6}, index=idx)
        if poison_holdout:
            later = f.index >= rs.HOLDOUT_START
            f.loc[later, ["open", "high", "low", "close"]] *= poison_rng.uniform(0.1, 10, (later.sum(), 1))
        frames[t] = f
    return frames


def test_preflight_never_holds_a_holdout_row_and_ignores_holdout_values(monkeypatch, tmp_path):
    quick = copy.deepcopy(rs.HOLDOUT_SPEC)
    quick["bootstrap_runs"] = 150
    monkeypatch.setattr(rs, "HOLDOUT_SPEC", quick)
    seen_max = []

    def guarded_scores(frames):
        seen_max.append(max(f.index.max() for f in frames.values()))
        return fake_scores(frames)

    monkeypatch.setattr(rs, "score_all", guarded_scores)
    monkeypatch.setattr(rs, "parity_check", lambda *a, **k: {"window": k.get("window"), "checked": 0,
                                                             "max_difference": 0.0})
    monkeypatch.setattr(rs, "time_invariance", lambda *a, **k: {"checked": 0, "max_difference": {}, "passed": True})
    outputs = []
    for poison in (False, True):
        cache, out = tmp_path / f"cache{poison}", tmp_path / f"out{poison}"
        write_cache(cache, make_universe(3, poison_holdout=poison))
        rs.run_preflight(str(cache), str(out))
        outputs.append((out / "preflight.json").read_text())
    assert all(m < rs.HOLDOUT_START for m in seen_max)       # no hold-out row ever reached scoring
    assert outputs[0] == outputs[1]                          # hold-out values change nothing at all


def test_load_cache_drops_holdout_rows_at_read_time(tmp_path):
    write_cache(tmp_path, make_universe(4))
    frames = rs.load_cache(str(tmp_path), before=rs.HOLDOUT_START)
    assert all(f.index.max() < rs.HOLDOUT_START for f in frames.values())
    assert rs.checked_start_from_manifest(str(tmp_path)) == rs.HOLDOUT_START


# ----------------------------------------------------------------------------- time invariance

def causal_calc(df):
    out = df.copy()
    out["ma"] = df["close"].rolling(5).mean()
    out["atr"] = (df["high"] - df["low"]).rolling(14).mean()
    return out


def leaky_calc(df):
    out = causal_calc(df)
    out["ma"] = df["close"].rolling(5, center=True).mean()     # uses two future bars
    return out


def comp(df):
    last = df.iloc[-1]
    ma_pts = 4.0 if last["close"] > last["ma"] else -4.0
    return {"score": 50 + ma_pts, "atr_pct": float(last["atr"] / last["close"] * 100),
            "contributions": {"Moving Averages": ma_pts, "Performance": 0.0}}


def stored_details(frames, calc):
    out = {}
    for t, f in frames.items():
        src = calc(f)
        rows = {}
        for pos in range(30, len(f)):
            r = comp(src.iloc[: pos + 1])
            rows[f.index[pos]] = {"score": r["score"], "x_atr_pct": r["atr_pct"], **r["contributions"]}
        out[t] = rs.add_families(pd.DataFrame.from_dict(rows, orient="index"))
    return out


def test_time_invariance_passes_a_causal_pipeline_and_catches_a_leaky_one():
    rng = np.random.default_rng(5)
    idx = pd.date_range("2024-01-01", periods=160, freq="D")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, 160)))
    frames = {"SOL-USD": pd.DataFrame({"open": close, "high": close * 1.03, "low": close * 0.97, "close": close,
                                       "volume": 1.0}, index=idx)}
    good = rs.time_invariance(frames, stored_details(frames, causal_calc), idx[60], samples=6,
                              scorer=(causal_calc, comp))
    assert good["passed"] and good["checked"] == 6
    bad = rs.time_invariance(frames, stored_details(frames, leaky_calc), idx[60], samples=6,
                             scorer=(leaky_calc, comp))
    assert not bad["passed"]


def test_availability_audit_separates_end_of_window_from_internal_gaps():
    idx = pd.date_range("2024-01-01", periods=80, freq="D")
    frames, details = {}, {}
    for i, t in enumerate(["SOL-USD", "ADA-USD", "XRP-USD"]):
        close = pd.Series(100 + np.arange(80.0) + i, index=idx)
        if t == "ADA-USD":
            close.iloc[40] = np.nan                               # one missing day inside the window
        frames[t] = pd.DataFrame({"close": close})
        details[t] = pd.DataFrame({"Trend": 1.0}, index=idx)
    cls = {t: "crypto" for t in frames}
    a = rs.availability_audit(frames, details, cls, "crypto", 14, "Trend")
    assert a["end_of_window"] == 3 * 15
    # ADA drops on the days whose entry (t+1) or exit (t+15) is the missing day and that still have a price
    assert a["internal"] == 2 and all(c == "ADA-USD" for _, c in a["internal_cases"])
