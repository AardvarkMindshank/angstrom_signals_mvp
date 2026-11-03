"""Capital-flow collection: parsing, the source register, first-run backfill, revisions and the refresh clock."""

from datetime import datetime, timezone

import pytest

import capital_flows as cf

TFTC = {
    "license": "https://creativecommons.org/licenses/by/4.0/",
    "days": [
        {"date": "2024-01-11", "netFlowUsd": 655300000, "totalNetAssetsUsd": None, "btcCloseUsd": 46269,
         "perEtfUsd": {"IBIT": 111700000, "GBTC": -95100000}},
        {"date": "2024-01-15", "netFlowUsd": 0, "totalNetAssetsUsd": None, "btcCloseUsd": 42500, "perEtfUsd": {}},
        {"date": "2024-01-16", "netFlowUsd": -12.5e6, "totalNetAssetsUsd": 2.8e10, "perEtfUsd": {"ibit": "5000000"}},
        {"date": "bad", "netFlowUsd": 1},
        "junk",
    ],
}
LLAMA = [
    {"date": "1704067200", "totalCirculatingUSD": {"peggedUSD": 1.30e11, "peggedEUR": 2.0e8}},
    {"date": 1704153600, "totalCirculatingUSD": {"peggedUSD": 1.31e11}},
    {"date": "1704240000", "totalCirculating": {"peggedUSD": 1}},
]


def test_tftc_rows_total_per_fund_and_holidays_skipped():
    rows = cf.parse_tftc(TFTC)
    keys = {(r["series"], r["subject"], r["observed_date"]) for r in rows}
    assert ("etf_net_flow", "BTC", "2024-01-11") in keys and ("etf_net_flow", "BTC:IBIT", "2024-01-11") in keys
    assert ("etf_net_flow", "BTC:GBTC", "2024-01-11") in keys
    assert not any(r["observed_date"] == "2024-01-15" for r in rows)            # holiday
    assert ("etf_total_net_assets", "BTC", "2024-01-16") in keys
    assert ("etf_net_flow", "BTC:IBIT", "2024-01-16") in keys                   # ticker upper-cased
    gbtc = next(r for r in rows if r["subject"] == "BTC:GBTC")
    assert gbtc["value"] == -95100000 and gbtc["unit"] == "USD" and gbtc["kind"] == "observed"


def test_defillama_total_sums_every_peg_per_day():
    rows = cf.parse_defillama_total(LLAMA)
    assert [(r["observed_date"], r["value"]) for r in rows] == [("2024-01-01", 1.302e11), ("2024-01-02", 1.31e11)]
    assert cf.parse_defillama_total({"unexpected": "shape"}) == []


def test_register_records_licence_terms_for_every_source():
    for key, spec in cf.SOURCES.items():
        for field in ("licence", "commercial_use", "redistribution", "cost", "upgrade_path", "before_launch", "status"):
            assert spec.get(field), (key, field)
    assert cf.active_sources() == ["tftc_btc_etf", "defillama_stablecoins"]
    assert not cf.user_visible("coinmetrics_community") and cf.user_visible("tftc_btc_etf")


def test_inactive_sources_are_never_fetched():
    with pytest.raises(PermissionError):
        cf.fetch("coinmetrics_community", getter=lambda url: (_ for _ in ()).throw(AssertionError("fetched")))
    with pytest.raises(PermissionError):
        cf.fetch("farside", getter=lambda url: (_ for _ in ()).throw(AssertionError("fetched")))


class _Resp:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _DB:
    """Two tables: observations (keyed like the real primary key) and the fetch log."""

    def __init__(self):
        self.obs, self.fetches = {}, []

    def table(self, name):
        db = self

        class Q:
            def __init__(self):
                self.mode, self.filters, self.payload = "select", {}, None

            def select(self, *_):
                return self

            def eq(self, col, val):
                self.filters[col] = val
                return self

            def order(self, *_a, **_k):
                return self

            def limit(self, *_):
                return self

            def insert(self, row):
                self.mode, self.payload = "insert", row
                return self

            def upsert(self, rows, on_conflict=None, ignore_duplicates=False):
                assert ignore_duplicates and on_conflict == "source,series,subject,observed_date,value"
                self.mode, self.payload = "upsert", rows
                return self

            def execute(self):
                data = []
                if name == "capital_flow_fetches":
                    if self.mode == "insert":
                        db.fetches.append(dict(self.payload, fetched_at=db.clock))
                    else:
                        data = sorted((f for f in db.fetches if f["source"] == self.filters.get("source")),
                                      key=lambda f: f["fetched_at"], reverse=True)[:1]
                else:
                    if self.mode == "upsert":
                        for r in self.payload:
                            key = (r["source"], r["series"], r["subject"], r["observed_date"], r["value"])
                            db.obs.setdefault(key, r)            # ignore duplicates
                    else:
                        data = [r for r in db.obs.values() if r["source"] == self.filters.get("source")][:1]
                return type("R", (), {"data": data})()

        return Q()


def _getter(payloads):
    return lambda url: _Resp(payloads[url])


URLS = {cf.SOURCES["tftc_btc_etf"]["url"]: TFTC, cf.SOURCES["defillama_stablecoins"]["url"]: LLAMA}


def test_first_run_backfills_then_revisions_add_rows_and_the_clock_waits(monkeypatch):
    db = _DB()
    db.clock = "2026-11-03T00:00:00+00:00"
    t0 = datetime(2026, 11, 3, tzinfo=timezone.utc).timestamp()
    cf.refresh_due_flows(db, now=t0, getter=_getter(URLS))
    assert all(r["backfilled"] for r in db.obs.values()) and len(db.obs) == 8
    assert {f["source"] for f in db.fetches} == {"tftc_btc_etf", "defillama_stablecoins"}

    # Within the refresh window nothing is fetched again.
    cf.refresh_due_flows(db, now=t0 + 3600, getter=lambda url: (_ for _ in ()).throw(AssertionError("refetched")))

    # Later: the newest TFTC day is revised; the first value stays, the revision is a new, live row.
    revised = {"days": [dict(TFTC["days"][2], netFlowUsd=-10e6)]}
    db.clock = "2026-11-03T07:00:00+00:00"
    cf.refresh_due_flows(db, now=t0 + cf.REFRESH_SECONDS + 1,
                         getter=_getter({**URLS, cf.SOURCES["tftc_btc_etf"]["url"]: revised}))
    totals = sorted(r["value"] for r in db.obs.values() if r["subject"] == "BTC" and r["observed_date"] == "2024-01-16"
                    and r["series"] == "etf_net_flow")
    assert totals == [-12.5e6, -10e6]
    live = [r for r in db.obs.values() if r["value"] == -10e6]
    assert live and not live[0]["backfilled"] and cf.is_point_in_time(live[0])


def test_a_broken_feed_is_logged_and_does_not_stop_the_other(monkeypatch):
    db = _DB()
    db.clock = "2026-11-03T00:00:00+00:00"

    def getter(url):
        if "tftc" in url:
            raise RuntimeError("feed down")
        return _Resp(LLAMA)
    cf.refresh_due_flows(db, now=0, getter=getter)
    oks = {f["source"]: f["ok"] for f in db.fetches}
    assert oks == {"tftc_btc_etf": False, "defillama_stablecoins": True}
    assert any(r["source"] == "defillama_stablecoins" for r in db.obs.values())


def test_a_format_change_is_flagged_not_stored():
    db = _DB()
    db.clock = "2026-11-03T00:00:00+00:00"
    cf.refresh_due_flows(db, now=0, getter=lambda url: _Resp({"something": "else"}))
    assert db.obs == {} and all(not f["ok"] and "format" in f["note"] for f in db.fetches)
