from market_store import held_report_dates, load_earnings_history


def row(day, seen):
    return {"report_date": day, "last_seen_at": seen + "T12:00:00+00:00"}


def test_only_past_dates_that_held_are_kept():
    rows = [
        row("2026-07-30", "2026-07-30"),   # held until the day
        row("2026-08-05", "2026-07-20"),   # replaced early: the company moved it
        row("2026-04-30", "2026-05-01"),   # seen the day after: still real
        row("2026-11-02", "2026-10-29"),   # upcoming, not past
    ]
    assert held_report_dates(rows, today="2026-10-29") == ["2026-04-30", "2026-07-30"]


def test_bad_rows_are_skipped_and_repeats_collapse():
    rows = [{"report_date": None, "last_seen_at": None}, row("2026-07-30", "2026-07-30"), row("2026-07-30", "2026-07-31"), {}]
    assert held_report_dates(rows, today="2026-10-29") == ["2026-07-30"]
    assert held_report_dates(None, today="2026-10-29") == []


class Boom:
    def table(self, name):
        raise RuntimeError("down")


class Fake:
    def __init__(self):
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return self

    def select(self, cols):
        return self

    def eq(self, col, value):
        self.calls.append((col, value))
        return self

    def order(self, col):
        return self

    def execute(self):
        class R:
            data = [{"report_date": "2026-07-30"}]
        return R()


def test_load_uses_uppercase_ticker_and_survives_failure():
    fake = Fake()
    assert load_earnings_history(fake, " aapl ") == [{"report_date": "2026-07-30"}]
    assert ("ticker", "AAPL") in fake.calls
    assert load_earnings_history(Boom(), "AAPL") == []
    assert load_earnings_history(fake, "") == []
