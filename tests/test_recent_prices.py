"""The app keeps each asset's price history and, when the worker refreshes prices, fetches only the newest bars
(sql/2026-12-03_recent_prices.sql) instead of every whole history again (17 Nov 2026: the database's data out)."""

import market_store as ms


def _bars(days, close=1.0):
    return [{"t": f"2026-11-{d:02d}", "o": close, "h": close, "l": close, "c": close + d, "v": 1.0} for d in days]


class Db:
    def __init__(self):
        self.prices = {"Crypto|bitcoin": _bars(range(1, 16))}
        self.stamp = "2026-11-15T10:00:00+00:00"
        self.asked = []
        self.rpc_ok = True

    # postgrest-style chain
    def table(self, name):
        self._cols = None
        return self

    def select(self, cols):
        self._cols = cols
        return self

    def in_(self, col, keys):
        self._keys = keys
        return self

    def rpc(self, name, args):
        self._rpc = (name, args)
        self._cols = None
        return self

    def execute(self):
        if self._cols is None:
            name, args = self._rpc
            self.asked.append(("rpc", name))
            if not self.rpc_ok:
                raise RuntimeError("function asset_recent_prices does not exist")

            class R:
                data = [{"asset_key": k, "prices_updated_at": self.stamp, "recent": self.prices[k][-args["bars"]:]}
                        for k in args["wanted"] if k in self.prices]
            return R()
        self.asked.append(("select", self._cols))
        cols = [c.strip() for c in self._cols.split(",")]
        rows = []
        for k in self._keys:
            row = {"asset_key": k}
            for c in cols:
                if c == "prices":
                    row[c] = list(self.prices[k])
                elif c == "prices_updated_at":
                    row[c] = self.stamp
                elif c != "asset_key":
                    row[c] = None
            rows.append(row)

        class R:
            data = rows
        return R()


def _fresh(monkeypatch):
    monkeypatch.setattr(ms, "_ROW_CACHE", {})
    monkeypatch.setattr(ms, "_FULL_AT", {})
    monkeypatch.setattr(ms, "_COLUMN_TIER", 0)
    ms._RECENT_DOWN_UNTIL[0] = 0.0


def test_a_price_refresh_reads_only_the_newest_bars(monkeypatch):
    _fresh(monkeypatch)
    db = Db()
    first = ms.load_shared_market(db, ["Crypto|bitcoin"])
    assert len(first["Crypto|bitcoin"]["prices"]) == 15
    assert any(kind == "select" and "prices," in cols for kind, cols in db.asked)        # a whole row the first time
    # the worker refreshes: today's bar changes and a new day starts
    db.prices["Crypto|bitcoin"] = _bars(range(1, 15)) + _bars([15], close=9.0) + _bars([16], close=9.0)
    db.stamp = "2026-11-16T00:05:00+00:00"
    db.asked.clear()
    second = ms.load_shared_market(db, ["Crypto|bitcoin"])["Crypto|bitcoin"]["prices"]
    assert second == db.prices["Crypto|bitcoin"]
    whole = [cols for kind, cols in db.asked if kind == "select" and "prices," in cols.replace("prices_updated_at", "")]
    assert not whole and ("rpc", "asset_recent_prices") in db.asked


def test_without_the_function_or_when_bars_dont_join_it_reads_whole_rows(monkeypatch):
    _fresh(monkeypatch)
    db = Db()
    ms.load_shared_market(db, ["Crypto|bitcoin"])
    db.rpc_ok = False                                                 # the SQL not run yet
    db.prices["Crypto|bitcoin"] = _bars(range(1, 17))
    db.stamp = "later"
    assert len(ms.load_shared_market(db, ["Crypto|bitcoin"])["Crypto|bitcoin"]["prices"]) == 16
    assert ms._join_recent(_bars(range(1, 10)), _bars(range(20, 25))) is None     # a gap: no day may go missing
    assert ms._join_recent(_bars(range(1, 10)), []) is None
    joined = ms._join_recent(_bars(range(1, 10)), _bars(range(8, 12), close=5.0))
    assert [b["t"] for b in joined][-4:] == ["2026-11-08", "2026-11-09", "2026-11-10", "2026-11-11"]
    assert joined[-1]["c"] == 16.0 and len(joined) == 11


def test_light_rows_leave_out_only_the_price_history():
    for tier in (ms._SHARED_COLUMNS_STATS + ", readings", ms._SHARED_COLUMNS_STATS, ms._SHARED_COLUMNS):
        light = tier.replace(", prices,", ",")
        cols = [c.strip() for c in light.split(",")]
        assert "prices" not in cols and "prices_updated_at" in cols and "closes" in cols
