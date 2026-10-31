"""Tests for research.py. They use made-up data, so they run without pandas_ta or downloads."""

import numpy as np
import pandas as pd

import research as rs


def dates(n, start="2020-01-01"):
    return pd.date_range(start, periods=n, freq="D")


def test_universe_and_classes():
    assert len(rs.UNIVERSE_STOCKS) >= 55 and len(rs.UNIVERSE_CRYPTO) >= 20
    assert len(set(rs.UNIVERSE_STOCKS)) == len(rs.UNIVERSE_STOCKS)
    assert rs.asset_class("BTC-USD") == "crypto" and rs.asset_class("AAPL") == "stock"
    assert "Survivor bias" in rs.SURVIVOR_NOTE


def test_completed_bars_drop_the_last_bar():
    frame = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=dates(3))
    assert list(rs.completed_bars(frame)["close"]) == [1.0, 2.0]


def test_price_cache_round_trip(tmp_path):
    frame = pd.DataFrame({"open": [1.0, 2.0], "high": [1.5, 2.5], "low": [0.5, 1.5],
                          "close": [1.2, 2.2], "volume": [10.0, 20.0]}, index=dates(2))
    frame.index.name = "date"
    rs.save_frame(frame, tmp_path / "X.csv.gz")
    back = rs.load_frame(tmp_path / "X.csv.gz")
    assert np.allclose(back.values, frame.values) and list(back.index) == list(frame.index)


def test_development_never_sees_holdout_and_old_four_are_left_out():
    frames = {"AAPL": pd.DataFrame({"close": 1.0}, index=dates(1500)),
              "XOM": pd.DataFrame({"close": 1.0}, index=dates(1500))}
    start = rs.holdout_start(frames)
    assert start == frames["AAPL"].index[-1] - pd.DateOffset(years=2)
    table = frames["XOM"]
    assert rs.development_view(table, start).index.max() < start
    assert rs.holdout_view(table, start, "XOM").index.min() >= start
    assert rs.holdout_view(table, start, "AAPL") is None   # looked at on 29 Oct
    assert rs.holdout_view(table, start, "BTC-USD") is None


def test_families_add_up_factor_points():
    details = pd.DataFrame({"RSI": [8.0], "Stochastic": [5.0], "Bollinger Bands": [0.0],
                            "Moving Averages": [12.0], "ADX Trend": [4.0], "MACD & Hist": [9.0],
                            "Ichimoku Cloud": [8.0], "Performance": [2.0], "Volume": [3.0], "OBV": [-3.0]})
    out = rs.add_families(details)
    assert out["Trend"].iloc[0] == 35 and out["Stretch"].iloc[0] == 13 and out["Flow"].iloc[0] == 0


def test_block_indices_are_runs_of_dates():
    rng = np.random.default_rng(1)
    idx = rs.block_indices(100, 10, rng)
    assert len(idx) == 100
    runs = idx.reshape(10, 10)
    assert all(((row[1:] - row[:-1]) % 100 == 1).all() for row in runs)


def test_joint_dates_give_wider_bands_when_assets_move_together():
    """Point 5: resampling each asset separately understates the noise when assets move together."""
    rng = np.random.default_rng(7)
    common = rng.normal(size=(600, 1))
    sums = common + 0.2 * rng.normal(size=(600, 20))   # 20 assets, mostly one shared move
    counts = np.ones_like(sums)
    _, low_j, high_j = rs.ratio_bootstrap(sums, counts, block=20, runs=300, joint=True)
    _, low_i, high_i = rs.ratio_bootstrap(sums, counts, block=20, runs=300, joint=False)
    assert (high_j - low_j) > 2.5 * (high_i - low_i)


def test_block_bands_are_wider_than_daily_resampling_for_slow_signals():
    rng = np.random.default_rng(3)
    x = np.zeros(1500)
    for i in range(1, 1500):
        x[i] = 0.97 * x[i - 1] + rng.normal()          # a slow-moving series, like a score
    _, lo1, hi1 = rs.ratio_bootstrap(x, np.ones(1500), block=1, runs=300)
    _, lo20, hi20 = rs.ratio_bootstrap(x, np.ones(1500), block=40, runs=300)
    assert (hi20 - lo20) > 2 * (hi1 - lo1)


def make_panel(n_dates=900, n_assets=12, strength=0.0, seed=0, prefix="S"):
    rng = np.random.default_rng(seed)
    idx = dates(n_dates)
    sig = pd.DataFrame(rng.normal(size=(n_dates, n_assets)), index=idx,
                       columns=[f"{prefix}{i}" for i in range(n_assets)])
    fwd = strength * sig + rng.normal(size=sig.shape)
    return sig, pd.DataFrame(fwd, index=idx, columns=sig.columns)


def test_planted_signal_is_found():
    sig, fwd = make_panel(strength=0.3, seed=1)
    est, low, high = rs.pooled_rank_correlation(sig, fwd, horizon=1, runs=200)
    assert rs.verdict(est, low, high) == "positive" and est > 0.2
    classes = {c: "stock" for c in sig.columns}
    cs = rs.cross_sectional(sig, fwd, classes, 1, "stock")
    assert rs.verdict(*cs["ic"]) == "positive" and rs.verdict(*cs["spread"]) == "positive"


def test_pure_noise_rarely_passes():
    passes = 0
    for seed in range(30):
        sig, fwd = make_panel(n_dates=500, n_assets=8, strength=0.0, seed=100 + seed)
        passes += rs.verdict(*rs.pooled_rank_correlation(sig, fwd, horizon=1, runs=150)) != "noise"
    assert passes <= 5          # about 5% expected; allow for chance with 30 tries


def test_ranking_never_mixes_classes():
    """Point 4: coins ranked with coins, stocks with stocks. Crypto's bigger moves must not leak in."""
    rng = np.random.default_rng(5)
    idx = dates(400)
    stocks = [f"S{i}" for i in range(10)]
    coins = [f"C{i}-USD" for i in range(10)]
    # Coins always have higher signals AND higher returns, but inside each class there is no link.
    sig = pd.DataFrame(np.hstack([rng.normal(size=(400, 10)), 10 + rng.normal(size=(400, 10))]),
                       index=idx, columns=stocks + coins)
    fwd = pd.DataFrame(np.hstack([rng.normal(size=(400, 10)), 5 + rng.normal(size=(400, 10))]),
                       index=idx, columns=stocks + coins)
    classes = {c: rs.asset_class(c) for c in sig.columns}
    table = rs.cross_sectional_by_date(sig, fwd, classes)
    assert set(table["class"]) == {"stock", "crypto"}
    assert abs(table["ic"].mean()) < 0.05            # mixed ranking would be strongly positive
    mixed = [sig.loc[d].rank().corr(fwd.loc[d].rank()) for d in idx[:50]]
    assert np.mean(mixed) > 0.5                       # proof the test would catch a mix-up


def test_extremes_compare_with_each_assets_own_average():
    idx = dates(300)
    fwd = pd.DataFrame({"A": np.r_[np.full(30, 5.0), np.zeros(270)], "B": np.ones(300)}, index=idx)
    flags = pd.DataFrame({"A": np.r_[np.ones(30, bool), np.zeros(270, bool)], "B": np.zeros(300, bool)}, index=idx)
    est, low, high, days = rs.extreme_excess(flags, fwd, horizon=1)
    assert days == 30 and abs(est - 4.5) < 1e-9       # 5 against A's own average of 0.5


def test_score_histogram_counts_levels():
    scores = pd.Series([10, 25, 50, 50, 75, 85, 95, np.nan])
    h = rs.score_histogram(scores)
    assert h["days"] == 7 and h["share_at_or_above_80"] == 2 / 7 and h["share_at_or_below_20"] == 1 / 7
    assert sum(h["bins"].values()) == 7 and h["bins"]["90-100"] == 1


def test_report_formats_with_partial_results():
    report = {
        "generated_at": "2026-10-31T10:00:00", "holdout_starts": "2024-10-30",
        "assets": {"stock": ["XOM"], "crypto": ["SOL-USD"]}, "survivor_note": rs.SURVIVOR_NOTE,
        "tests_counted": 40,
        "histogram": {"per_class": {"stock": rs.score_histogram(pd.Series([40, 60, 80])), "crypto": {"days": 0}}},
        "signals": {"stock": {"score": {7: {"time_series_ic": (0.01, -0.02, 0.04), "time_series": "noise",
                                            "cross_section_ic": (None, None, None), "cross_section": "too few",
                                            "top_minus_bottom_pct": (None, None, None), "ranking": "too few"}}}},
        "extremes": {"stock": {"score 80 or more": {h: {"excess_pct": None, "band": [None, None], "days": 0}
                                                    for h in rs.HORIZONS}}},
        "regimes": {}, "volatility": {},
    }
    text = rs.format_report(report, {"window": 200, "checked": 10, "max_difference": 0.0})
    assert "Survivor bias" in text and "NOT used" in text and "about 2 would pass by luck" in text
