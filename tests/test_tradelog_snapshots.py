"""Trade Log snapshots (tradelog_snapshots.py): only what was known at the moment, observed when it was saved."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import tradelog_snapshots as ts


def _bars(n=400, seed=3, end="2026-11-20"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=pd.Timestamp(end), periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    return pd.DataFrame({"open": close * 0.99, "high": close * 1.02, "low": close * 0.98, "close": close,
                         "volume": rng.random(n) * 1e6}, index=idx)


TRIP = {"asset_key": "Stock|NVDA", "asset_class": "stocks",
        "opened_at": "2026-10-10T15:00:00+00:00", "closed_at": "2026-10-20T15:00:00+00:00"}


def test_rebuilt_readings_use_only_bars_finished_before_the_trade_day():
    snap = ts.snapshot(TRIP, "entry", bars=_bars(), kind="Stock")
    assert snap["source"] == "reconstructed"
    assert snap["readings"]["bar"] < "2026-10-10"
    assert snap["readings"]["regime"] is None or isinstance(snap["readings"]["regime"], str)
    assert snap["readings"]["use"] == "logbook"


def test_later_prices_cannot_change_the_snapshot():
    bars = _bars()
    poisoned = bars.copy()
    poisoned.loc[poisoned.index >= "2026-10-10", ["open", "high", "low", "close"]] *= 3      # a wild future
    a = ts.snapshot(TRIP, "entry", bars=bars, kind="Stock")
    b = ts.snapshot(TRIP, "entry", bars=poisoned, kind="Stock")
    assert a == b


def test_observed_only_when_saved_before_the_trade():
    bars = _bars()
    rebuilt = ts.snapshot(TRIP, "entry", bars=bars, kind="Stock")
    day = rebuilt["readings"]["bar"]
    row = {"day": day, "trend": 11.0, "stretch": 22.0, "flow": 33.0, "regime": "ranging"}
    early = {day: {**row, "first_seen_at": "2026-10-09T23:00:00+00:00"}}
    late = {day: {**row, "first_seen_at": "2026-10-11T00:00:00+00:00"}}
    seen = ts.snapshot(TRIP, "entry", bars=bars, kind="Stock", record=early)
    assert seen["source"] == "observed" and seen["readings"]["trend"] == 11.0
    assert ts.snapshot(TRIP, "entry", bars=bars, kind="Stock", record=late)["source"] == "reconstructed"


def test_no_asset_key_or_too_little_history_is_unavailable():
    assert ts.snapshot({**TRIP, "asset_key": None}, "entry", bars=_bars())["source"] == "unavailable"
    assert ts.snapshot(TRIP, "entry", bars=_bars(n=30, end="2026-10-09"))["source"] == "unavailable"


def test_sentiment_must_be_recent_and_never_from_later():
    moment = datetime(2026, 10, 10, 15, tzinfo=timezone.utc)
    series = [((moment - timedelta(days=5)).isoformat(), 40), ((moment - timedelta(hours=6)).isoformat(), 61),
              ((moment + timedelta(hours=1)).isoformat(), 90)]
    snap = ts.snapshot(TRIP, "entry", asset_sentiment=series, market_sentiment=series[:1])
    assert snap["readings"]["asset_sentiment"]["value"] == 61.0
    assert snap["readings"]["market_sentiment"] == {"value": None}            # older than 3 days: not recorded


def test_fear_index_is_the_vix_for_stocks_and_fear_greed_for_crypto_from_earlier_days():
    vix = [("2026-10-08", 15.0), ("2026-10-09", 16.5), ("2026-10-10", 30.0)]
    snap = ts.snapshot(TRIP, "entry", vix=vix)
    assert snap["readings"]["fear"] == {"name": "VIX", "value": 16.5, "day": "2026-10-09"}
    crypto = ts.snapshot({**TRIP, "asset_class": "crypto"}, "exit", fear_greed=[("2026-10-19", 22)])
    assert crypto["readings"]["fear"]["name"] == "Fear & Greed" and crypto["readings"]["fear"]["value"] == 22
