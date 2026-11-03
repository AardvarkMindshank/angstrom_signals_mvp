import json

import numpy as np
import pandas as pd
import pytest

from signal_library import REGISTRY, DataContext, SignalRef, evaluate
from signal_library import engine
from signal_library.core import INSUFFICIENT, MISSING, OK, STALE, UNSUPPORTED
from signal_library.signals_market import daily_values

NOW = pd.Timestamp("2026-11-03 10:00", tz="UTC")


def setup_function(_):
    engine.clear_cache()


def _sessions(n=30, end="2026-11-02"):
    return [d.date().isoformat() for d in pd.bdate_range(end=end, periods=n)]


def _etf_rows(backfill_until="2026-10-20"):
    rows = []
    for i, day in enumerate(_sessions()):
        backfilled = day <= backfill_until
        seen = "2026-11-01T00:00:00+00:00" if backfilled else f"{day}T23:00:00+00:00"
        rows.append({"subject": "BTC", "observed_date": day, "value": 100.0 * (i + 1), "fetched_at": seen,
                     "backfilled": backfilled})
        rows.append({"subject": "BTC:IBIT", "observed_date": day, "value": 60.0 * (i + 1), "fetched_at": seen,
                     "backfilled": backfilled})
        rows.append({"subject": "BTC:FBTC", "observed_date": day, "value": 40.0 * (i + 1), "fetched_at": seen,
                     "backfilled": backfilled})
    # The newest day was revised the next morning.
    rows.append({"subject": "BTC", "observed_date": "2026-11-02", "value": 2900.0,
                 "fetched_at": "2026-11-03T08:00:00+00:00", "backfilled": False})
    return rows


def _flows_ctx(rows, subject="bitcoin"):
    def loader(source, series, subj):
        if subj.endswith("*"):
            picked = [r for r in rows if r["subject"].startswith(subj[:-1])]
        else:
            picked = [r for r in rows if r["subject"] == subj]
        return {"rows": picked} if picked else {"error": "none"}
    return DataContext("market", subject, flows_loader=loader, now=NOW)


def test_daily_values_keep_revisions_first_seen_and_backfill():
    table = daily_values(_etf_rows(), as_of=NOW)
    last = table[(table["subject"] == "BTC")].iloc[-1]
    assert last["value"] == 2900.0 and last["revisions"] == 1
    assert last["first_seen"] == pd.Timestamp("2026-11-02T23:00:00Z")
    before = daily_values(_etf_rows(), as_of="2026-11-03T07:00:00Z")
    assert before[before["subject"] == "BTC"].iloc[-1]["value"] == 3000.0  # the revision was not known yet
    strict = daily_values(_etf_rows(), point_in_time=True)
    assert strict["date"].min() > "2026-10-20"


def test_etf_signal_sums_sessions_and_reports_timing():
    ref = SignalRef.make(REGISTRY.get("flows.btc_etf"), "1D")
    result = evaluate([ref], _flows_ctx(_etf_rows()))[ref.instance_key]
    assert result.status == OK
    v = result.value
    assert v["latest_net_flow_usd"] == 2900.0
    assert v["sum_5_sessions_usd"] == 2600 + 2700 + 2800 + 2900 + 2900
    assert v["sum_20_sessions_usd"] == sum(100.0 * i for i in range(11, 30)) + 2900
    assert v["per_fund_latest_usd"] == {"IBIT": 1800.0, "FBTC": 1200.0}
    assert result.backfilled is False and result.available_at.startswith("2026-11-02T23:00")
    assert "TFTC" in result.provenance[0] and "2026-11-02" in result.provenance[0]
    json.dumps(result.as_dict())


def test_etf_backfilled_latest_day_is_flagged():
    rows = _etf_rows(backfill_until="2026-11-30")
    rows = [r for r in rows if r["fetched_at"] != "2026-11-03T08:00:00+00:00"]
    ref = SignalRef.make(REGISTRY.get("flows.btc_etf"), "1D")
    result = evaluate([ref], _flows_ctx(rows))[ref.instance_key]
    assert result.backfilled is True and any("history" in n for n in result.notes)
    strict = SignalRef.make(REGISTRY.get("flows.btc_etf"), "1D", point_in_time=True)
    assert evaluate([strict], _flows_ctx(rows))[strict.instance_key].status == INSUFFICIENT


def test_etf_stale_when_old():
    rows = [dict(r, observed_date=(pd.Timestamp(r["observed_date"]) - pd.Timedelta(days=20)).date().isoformat())
            for r in _etf_rows()]
    ref = SignalRef.make(REGISTRY.get("flows.btc_etf"), "1D")
    assert evaluate([ref], _flows_ctx(rows))[ref.instance_key].status == STALE


def test_stablecoin_changes_and_caveat():
    days = pd.date_range(end="2026-11-02", periods=40, freq="D")
    rows = [{"subject": "ALL", "observed_date": d.date().isoformat(), "value": 1000.0 + 10 * i,
             "fetched_at": f"{d.date()}T12:00:00+00:00", "backfilled": False} for i, d in enumerate(days)]
    ref = SignalRef.make(REGISTRY.get("flows.stablecoin_supply"), "1D")
    result = evaluate([ref], _flows_ctx(rows, subject="crypto"))[ref.instance_key]
    v = result.value
    assert result.status == OK
    assert v["change_7d_usd"] == 70.0 and v["change_30d_usd"] == 300.0
    assert v["previous_7d_change_usd"] == 70.0 and v["acceleration_7d_usd"] == 0.0
    assert any("not a measure of money entering" in n for n in result.notes)


def test_flow_signals_only_apply_to_their_market():
    ref = SignalRef.make(REGISTRY.get("flows.btc_etf"), "1D")
    asset = DataContext("crypto", "bitcoin", now=NOW)
    assert evaluate([ref], asset)[ref.instance_key].status == UNSUPPORTED


# ----------------------------------------------------------------------------- derivatives

def _record(hours=60, updated="2026-11-03T09:30:00+00:00"):
    t0 = int(pd.Timestamp("2026-11-03 09:00", tz="UTC").timestamp()) - (hours - 1) * 3600
    t = [t0 + 3600 * i for i in range(hours)]
    price = list(np.linspace(100, 110, hours))
    oi = list(np.linspace(1e9, 1.2e9, hours))
    return {"status": "ok", "updated_at": updated, "markets": ["BTCUSDT_PERP.A"],
            "longs": [{"price": 95, "usd": 5e7}, {"price": 105, "usd": 9e7}, {"price": 90, "usd": 2e8}],
            "shorts": [{"price": 115, "usd": 3e7}, {"price": 125, "usd": 1e8}],
            "series": {"t": t, "price": price, "oi": oi, "ls": [1.2] * (hours - 1) + [1.5],
                       "funding": [0.01] * hours, "liq_long": [1000.0] * hours, "liq_short": [3000.0] * hours}}


def _deriv_ctx(record):
    return DataContext("crypto", "bitcoin", derivatives_loader=lambda k, a: record, now=NOW)


def test_oi_price_reading_is_labelled_inferred():
    ref = SignalRef.make(REGISTRY.get("positioning.oi_price"), "1h")
    result = evaluate([ref], _deriv_ctx(_record()))[ref.instance_key]
    v = result.value
    assert result.status == OK
    assert v["open_interest_change_pct"] > 0 and v["price_change_pct"] > 0
    assert v["positioning_reading"] == "long build-up (inferred)"
    assert v["long_short_ratio_change"] == pytest.approx(0.3)
    assert any("inferred" in n for n in result.notes)


def test_liquidation_sums():
    ref = SignalRef.make(REGISTRY.get("positioning.liquidations"), "1h")
    v = evaluate([ref], _deriv_ctx(_record()))[ref.instance_key].value
    assert v["longs_usd"] == 24000.0 and v["shorts_usd"] == 72000.0 and v["longs_share_pct"] == 25.0


def test_liquidation_levels_split_by_side_of_price():
    ref = SignalRef.make(REGISTRY.get("positioning.liquidation_levels"), "1h")
    result = evaluate([ref], _deriv_ctx(_record()))[ref.instance_key]
    v = result.value
    assert v["nearest_long_level"]["price"] == 105 and v["largest_long_level"]["price"] == 90
    assert v["nearest_short_level"]["price"] == 115 and v["largest_short_level"]["price"] == 125
    assert any("Estimated" in n for n in result.notes)


def test_stale_and_missing_derivatives():
    ref = SignalRef.make(REGISTRY.get("positioning.oi_price"), "1h")
    old = evaluate([ref], _deriv_ctx(_record(updated="2026-11-02T09:00:00+00:00")))[ref.instance_key]
    assert old.status == STALE
    engine.clear_cache()
    gone = evaluate([ref], _deriv_ctx({"error": "none"}))[ref.instance_key]
    assert gone.status == MISSING
    stock = DataContext("equity", "AAPL", derivatives_loader=lambda k, a: _record(), now=NOW)
    assert evaluate([ref], stock)[ref.instance_key].status == UNSUPPORTED
