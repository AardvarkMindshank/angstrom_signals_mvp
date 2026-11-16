import market_store as ms


class Table:
    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.asked = []

    def table(self, name):
        return self

    def select(self, columns):
        self.columns = columns
        return self

    def in_(self, col, keys):
        return self

    def execute(self):
        self.asked.append(self.columns)
        if self.fail_on and self.fail_on in self.columns:
            raise RuntimeError("column does not exist")

        class R:
            data = [{"asset_key": "Stock|AAPL", "logo_url": "https://x/y.png"}]
        return R()


def test_falls_back_then_tries_the_full_set_again():
    ms._COLUMN_TIER = 0
    ms._COLUMN_TIER_SINCE = 0.0
    db = Table("next_earnings")
    out = ms.load_shared_market(db, ["Stock|AAPL"])
    assert out["Stock|AAPL"]["logo_url"] == "https://x/y.png"
    assert ms._COLUMN_TIER == 2                # past the readings and market-stats sets
    # soon after: stays on the smaller set, one ask only
    db.asked.clear()
    ms.load_shared_market(db, ["Stock|AAPL"])
    assert len(db.asked) == 1 and "next_earnings" not in db.asked[0]
    # after the retry time: the full set is tried again
    ms._COLUMN_TIER_SINCE -= ms._COLUMN_TIER_RETRY_SECONDS + 1
    healthy = Table(None)
    ms.load_shared_market(healthy, ["Stock|AAPL"])
    assert "next_earnings" in healthy.asked[0]
    assert ms._COLUMN_TIER == 0


def test_without_the_readings_column_the_market_stats_still_load():
    """Until sql/2026-12-01_stored_readings.sql is run, reading the readings column fails: market caps and earnings
    dates must still come through."""
    ms._COLUMN_TIER = 0
    ms._COLUMN_TIER_SINCE = 0.0
    db = Table("readings")
    ms.load_shared_market(db, ["Stock|AAPL"])
    assert ms._COLUMN_TIER == 1 and "next_earnings" in db.asked[-1] and "readings" not in db.asked[-1]
    ms._COLUMN_TIER = 0
