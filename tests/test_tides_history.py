"""Point-in-time Tides history (tides_history.py): same maths as tides.py, and no peeking."""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tides as td  # noqa: E402
import tides_history as th  # noqa: E402

END = "2021-06-30"


def _raw(seed=3):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2008-01-01", END)
    cal = pd.date_range("2014-09-17", END)
    yahoo, fred = td.symbols_needed()
    raw = {}
    for sym in sorted(yahoo):
        idx = cal if sym.endswith("-USD") else days
        raw[sym] = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.012, len(idx)))), index=idx)
    for sid in fred - {"CPIAUCSL"}:
        raw[f"fred:{sid}"] = pd.Series(2 + np.cumsum(rng.normal(0, 0.03, len(days))), index=days)
    months = pd.date_range("2006-01-01", "2021-05-01", freq="MS")
    cpi = 200 * np.exp(np.cumsum(rng.normal(0.002, 0.002, len(months))))
    released = months + pd.offsets.MonthBegin(1) + pd.Timedelta(days=12)
    raw["cpi"] = pd.DataFrame({"month": months, "released": released, "value": cpi})
    raw["jobs"] = pd.DataFrame({"month": months, "released": months + pd.offsets.MonthBegin(1) + pd.Timedelta(days=4),
                                "value": 1.0})
    return raw


def test_same_maths_as_tides():
    raw = _raw()
    table, _ = th.build(raw, END)
    days = pd.bdate_range(min(s.index.min() for s in raw.values() if isinstance(s, pd.Series)), END)
    readings = {}
    for key in td.CURRENT_KEYS:
        s = th.known_series(key, raw, days).dropna()
        readings[key] = td.read_current(key, s)
        r, row = readings[key], table.iloc[-1]
        assert r["direction"] == row[f"{key}_dir"], key
        assert math.isclose(r["contribution"], row[f"{key}_contrib"], abs_tol=1e-3), key
        assert math.isclose(r["score"], row[f"{key}_score"], abs_tol=0.11), key
    t = td.tide(readings)
    assert math.isclose(t["score"], table["tide_score"].iloc[-1], abs_tol=1e-3)
    assert t["label"] == table["tide"].iloc[-1]
    assert t["since"] == table["tide_since"].iloc[-1]
    winds = td.winds(readings)
    assert math.isclose(winds["crypto"]["score"], table["wind_crypto_score"].iloc[-1], abs_tol=1e-3)


def test_no_peeking():
    """A day's row is the same whether or not the later data exists."""
    raw = _raw(seed=8)
    full, _ = th.build(raw, END)
    cut = "2019-03-15"
    short = {k: (v[v.index <= cut] if isinstance(v, pd.Series) else v[v["released"] <= cut]) for k, v in raw.items()}
    part, _ = th.build(short, cut)
    a, b = full.loc[:cut], part.loc[:cut]
    assert len(a) == len(b)
    pd.testing.assert_frame_equal(a[b.columns], b, check_dtype=False)


def test_inflation_dated_on_release():
    raw = _raw()
    s = th.inflation_known(raw["cpi"])
    assert s.index.min() >= raw["cpi"]["released"].iloc[12]
    assert all(d.day == 13 for d in s.index)
