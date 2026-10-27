import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pandas_ta")

from scoring import DEFAULT_WEIGHTS, _label_for, calculate_indicators, compute_score


def bars(n=300, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))
    spread = close * 0.01
    return pd.DataFrame(
        {
            "open": close,
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.uniform(1e5, 2e5, n),
        },
        index=pd.date_range("2022-01-01", periods=n),
    )


@pytest.mark.parametrize(
    "score,label",
    [
        (100, "Strong Bullish"), (70, "Strong Bullish"), (69.9, "Bullish"), (60, "Bullish"),
        (53, "Mildly Bullish"), (50, "Neutral"), (47, "Neutral"), (46.9, "Mildly Bearish"),
        (40, "Mildly Bearish"), (39.9, "Bearish"), (30, "Bearish"), (29.9, "Strong Bearish"),
        (0, "Strong Bearish"),
    ],
)
def test_label_boundaries(score, label):
    assert _label_for(score) == label


def test_short_history_is_insufficient():
    result = compute_score(bars(10))
    assert result["label"] == "Insufficient data" and result["score"] == 50.0


def test_none_and_empty_inputs():
    assert compute_score(None)["label"] == "Insufficient data"
    assert compute_score(pd.DataFrame())["label"] == "Insufficient data"


@pytest.mark.parametrize("seed", range(5))
def test_score_stays_in_range(seed):
    data = calculate_indicators(bars(seed=seed))
    for weights in (None, {key: 3.0 for key in DEFAULT_WEIGHTS}, {key: 0.0 for key in DEFAULT_WEIGHTS}):
        score = compute_score(data, weights)["score"]
        assert 0.0 <= score <= 100.0


def test_no_lookahead_in_indicators():
    """The score for a day must not change when later bars are added."""
    data = bars(300)
    cut = 250
    early = compute_score(calculate_indicators(data.iloc[:cut]))["score"]
    late = compute_score(calculate_indicators(data).iloc[:cut])["score"]
    assert early == pytest.approx(late)
