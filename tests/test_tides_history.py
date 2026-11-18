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


class _Table:
    def __init__(self, db):
        self.db, self.rows = db, None

    def select(self, *a):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a):
        return self

    def upsert(self, rows, **k):
        self.rows = rows
        return self

    def execute(self):
        if self.rows is not None:
            self.db.saved += self.rows
            return type("R", (), {"data": self.rows})()
        days = sorted(r["day"] for r in self.db.saved)
        return type("R", (), {"data": [{"day": days[-1]}] if days else []})()


class _Db:
    def __init__(self):
        self.saved = []

    def table(self, name):
        assert name == "tides_daily"
        return _Table(self)


def test_daily_record_adds_only_finished_days(monkeypatch):
    raw = _raw()
    monkeypatch.setenv("FRED_API_KEY", "test")
    monkeypatch.setattr(th, "fetch_yahoo", lambda sym, a, b: raw[sym])
    monkeypatch.setattr(td, "fetch_fred", lambda sid: raw[f"fred:{sid}"])
    monkeypatch.setattr(th, "fetch_first_releases", lambda sid, key: raw["cpi"] if sid == "CPIAUCNS" else raw["jobs"])
    monkeypatch.setattr(th, "LIVE_FROM", pd.Timestamp("2021-06-01"))
    db = _Db()
    now = pd.Timestamp("2021-06-29 21:00", tz="UTC")      # the 29th's US close is not final yet
    assert th.refresh_daily(db, now=now) > 0
    days = [r["day"] for r in db.saved]
    assert days[0] == "2021-06-01" and days[-1] == "2021-06-28"
    assert th.refresh_daily(db, now=now) == 0                # nothing new until the next day is final
    assert db.saved[-1]["body"]["tide"] in ("in", "slack", "out")
