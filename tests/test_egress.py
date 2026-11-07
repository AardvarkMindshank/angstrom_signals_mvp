"""Database egress: whole price histories are read only when needed, and writes send nothing back."""

import market_store as ms
import shared_refresh as sr


class Fake:
    def __init__(self, rows):
        self.rows, self.selects, self.upserts = rows, [], []

    def table(self, name):
        return Query(self, name)


class Query:
    def __init__(self, db, name):
        self.db, self.name, self.cols, self.keys = db, name, "*", None

    def select(self, cols):
        self.cols = cols
        self.db.selects.append(cols)
        return self

    def in_(self, col, keys):
        self.keys = keys
        return self

    def upsert(self, payload, **kw):
        self.db.upserts.append(kw)
        return self

    def execute(self):
        class R:
            pass
        r = R()
        cols = [c.strip() for c in self.cols.split(",")]
        r.data = [{c: row.get(c) for c in cols} for k, row in self.db.rows.items() if not self.keys or k in self.keys]
        return r


ROW = {"asset_key": "Crypto|bitcoin", "prices_updated_at": "2026-11-07T00:00:00+00:00", "sentiment_updated_at": None,
       "closes_updated_at": None, "market_stats_updated_at": None, "earnings_checked_at": None,
       "prices": [{"t": 1}], "closes": [1, 2], "logo_url": "", "sentiment_report": None}


def test_the_app_rereads_a_row_only_when_it_changed(monkeypatch):
    monkeypatch.setattr(ms, "_ROW_CACHE", {})
    db = Fake({"Crypto|bitcoin": dict(ROW)})
    ms.load_shared_market(db, ["Crypto|bitcoin"])
    full = sum("sentiment_report" in c for c in db.selects)
    assert full == 1
    ms.load_shared_market(db, ["Crypto|bitcoin"])
    assert sum("sentiment_report" in c for c in db.selects) == full               # second load: times only
    db.rows["Crypto|bitcoin"]["prices_updated_at"] = "2026-11-07T00:05:00+00:00"
    ms.load_shared_market(db, ["Crypto|bitcoin"])
    assert sum("sentiment_report" in c for c in db.selects) == full + 1


def test_without_the_cache_rows_are_read_directly(monkeypatch):
    monkeypatch.setattr(ms, "_ROW_CACHE", None)
    db = Fake({"Crypto|bitcoin": dict(ROW)})
    assert "Crypto|bitcoin" in ms.load_shared_market(db, ["Crypto|bitcoin"])


def test_the_worker_reads_only_save_times_when_prices_are_fresh(monkeypatch):
    monkeypatch.setattr(sr, "technical_refresh_due", lambda stamp: False)
    db = Fake({"Crypto|bitcoin": dict(ROW)})
    frames = sr.refresh_price_catalog(db, {("Crypto", "bitcoin"): "Bitcoin"}, 200)
    assert db.selects == ["asset_key, prices_updated_at"]
    assert ("Crypto", "bitcoin") in frames.pending                 # read later, only if something asks


def test_price_saves_send_nothing_back():
    import pandas as pd

    db = Fake({})
    idx = pd.date_range("2026-01-01", periods=30, freq="D", tz="UTC")
    frame = pd.DataFrame({"open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0}, index=idx)
    ms.save_price_frame(db, "Crypto", "bitcoin", frame)
    assert db.upserts and all(kw.get("returning") is ms.MINIMAL for kw in db.upserts)
