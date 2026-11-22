"""The background worker's saved readings (stored_readings.py): used only when they fit the page's bars exactly."""

import json

import numpy as np
import pandas as pd

import market_store as ms
import signals_view
import stored_readings as sr
from scoring import calculate_indicators


def _bars(n=520, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=pd.Timestamp.now().normalize(), periods=n, freq="D")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    return pd.DataFrame({"open": close * 0.99, "high": close * 1.02, "low": close * 0.98, "close": close,
                         "volume": rng.random(n) * 1e6}, index=idx)


def _as_page_reads(frame):
    """Saved as records, read back as the page does (frame_from_row, then the last 500 bars)."""
    return ms.frame_from_records(json.loads(json.dumps(ms.records_from_frame(frame)))).tail(500)


def test_saved_readings_are_what_the_page_would_work_out():
    page = _as_page_reads(_bars())
    saved = json.loads(json.dumps(sr.build(page, "Crypto")))          # through the database and back
    used = sr.use({"readings": saved}, page)
    assert used == signals_view.row_fields(calculate_indicators(page), "Crypto")


def test_other_bars_another_hour_or_new_definitions_are_not_used(monkeypatch):
    page = _as_page_reads(_bars())
    saved = sr.build(page, "Stock")
    assert sr.use({"readings": saved}, page) is not None
    newer = _as_page_reads(_bars(seed=2))
    assert sr.use({"readings": saved}, newer) is None                  # a different last close
    assert sr.use({"readings": saved}, page.iloc[:-1]) is None         # one bar fewer
    assert sr.use({"readings": {**saved, "hour": "2000-01-01 00"}}, page) is None
    assert sr.use({"readings": {**saved, "version": "old"}}, page) is None
    assert sr.use({}, page) is None and sr.use(None, page) is None
    assert sr.use({"readings": "junk"}, page) is None


def test_the_page_gets_its_own_copy():
    page = _as_page_reads(_bars())
    row = {"readings": sr.build(page, "Crypto")}
    first = sr.use(row, page)
    first["signals"]["changed"] = True
    assert "changed" not in sr.use(row, page)["signals"]


class _Db:
    def __init__(self, refuse_readings):
        self.refuse, self.saved = refuse_readings, []

    def table(self, name):
        return self

    def upsert(self, payload, **kw):
        self.payload = payload
        return self

    def execute(self):
        if self.refuse and "readings" in self.payload:
            raise RuntimeError("column readings does not exist")
        self.saved.append(self.payload)


def test_the_worker_saves_readings_with_the_prices_and_still_saves_prices_without_the_column():
    frame = _bars()
    db = _Db(refuse_readings=False)
    assert ms.save_price_frame(db, "Crypto", "bitcoin", frame, with_readings=True)
    assert len(db.saved) == 1 and db.saved[0]["readings"]["fields"] and db.saved[0]["prices"]
    page = ms.frame_from_records(db.saved[0]["prices"]).tail(500)
    assert sr.use(db.saved[0], page) is not None
    old = _Db(refuse_readings=True)                                   # before the SQL has been run
    assert ms.save_price_frame(old, "Crypto", "bitcoin", frame, with_readings=True)
    assert len(old.saved) == 1 and "readings" not in old.saved[0]
    plain = _Db(refuse_readings=False)                                # a page saving prices: never readings
    assert ms.save_price_frame(plain, "Crypto", "bitcoin", frame)
    assert "readings" not in plain.saved[0]


def test_daily_record_keeps_only_the_headline_readings_once_per_day():
    page = _as_page_reads(_bars())
    readings = json.loads(json.dumps(sr.build(page, "Crypto")))
    row = sr.daily_row("crypto:bitcoin", readings)
    signals = readings["fields"]["signals"]
    assert row["day"] == signals["as_of"] and row["asset_key"] == "crypto:bitcoin"
    assert set(row) == {"asset_key", "day", "trend", "stretch", "flow", "regime", "version"}
    assert row["trend"] == signals["clusters"]["trend"]["percent"]
    assert len(json.dumps(row)) < 250                                  # small enough for ~40 MB a year
    assert sr.daily_row("x:y", None) is None and sr.daily_row("x:y", {"fields": {"signals": {"status": "no"}}}) is None


def test_daily_record_is_one_write_per_pass_and_never_overwrites():
    page = _as_page_reads(_bars())
    readings = sr.build(page, "Crypto")
    calls = []
    sr._daily.clear()                                                  # rows left by earlier tests' saves

    class Db:
        def table(self, name):
            calls.append(name)
            return self

        def upsert(self, rows, **kw):
            calls.append((len(rows), kw.get("ignore_duplicates"), kw.get("on_conflict")))
            return self

        def execute(self):
            return None

    sr.remember_daily("crypto:bitcoin", readings)
    sr.remember_daily("crypto:bitcoin", readings)                      # the same day twice: kept once
    sr.remember_daily("crypto:ether", readings)
    assert sr.flush_daily(Db()) == 2
    assert calls == ["readings_daily", (2, True, "asset_key,day")]
    assert sr.flush_daily(Db()) == 0                                   # nothing left after the pass


def test_daily_record_missing_table_does_not_break_the_worker():
    class Broken:
        def table(self, name):
            raise RuntimeError("relation readings_daily does not exist")

    sr.remember_daily("crypto:bitcoin", sr.build(_as_page_reads(_bars()), "Crypto"))
    assert sr.flush_daily(Broken()) == 0
