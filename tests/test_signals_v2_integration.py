"""Signals v2 on the real indicator output (pandas-ta). Skipped where pandas-ta is not installed; runs in
GitHub Actions (Signals v2 checks)."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pandas_ta")

import signals_v2 as v2  # noqa: E402
from scoring import calculate_indicators  # noqa: E402


def bars(n=400, seed=0, volume=True):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    vol = rng.uniform(1e6, 2e6, n) if volume else np.zeros(n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol}, index=idx)


def test_every_component_is_available_on_real_indicators():
    out = v2.score(calculate_indicators(bars()), "Stock", datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert out["status"] == "ok"
    for cluster in out["clusters"].values():
        assert cluster["coverage"][0] == cluster["coverage"][1], cluster
    assert out["context"]["volatility"]["atr_pct"] > 0


def test_indicator_column_names_the_engine_reads_exist():
    frame = calculate_indicators(bars())
    for prefix in ("MACD_", "MACDh_", "BBU_", "BBL_"):
        assert v2._col(frame, prefix) is not None, prefix
    for column in ("rsi", "stoch_k", "sma_20", "sma_50", "sma_200", "atr", "adx", "obv", "obv_sma_20",
                   "vol_sma_20", "volume_ratio", "change_7d", "ichi_tenkan", "ichi_kijun", "ichi_span_a", "ichi_span_b"):
        assert column in frame.columns, column


def test_coin_without_volume_has_no_flow():
    out = v2.score(calculate_indicators(bars(volume=False)), "Crypto", datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert out["clusters"]["flow"]["value"] is None


def test_score_at_a_date_ignores_later_bars():
    full = bars(420)
    cut = full.index[380]
    a = v2.score(calculate_indicators(full.loc[:cut]), "Stock", datetime(2030, 1, 1, tzinfo=timezone.utc))
    later = full.copy()
    later.loc[later.index > cut, ["open", "high", "low", "close"]] *= 2.5
    ind = calculate_indicators(later)
    b = v2.score(ind.loc[:cut], "Stock", datetime(2030, 1, 1, tzinfo=timezone.utc))
    for key in v2.CLUSTERS:
        assert a["clusters"][key]["value"] == pytest.approx(b["clusters"][key]["value"], abs=1e-12)
