from datetime import datetime, timedelta, timezone

import digest
from alerts import BEARISH, BULLISH


def utc(*parts):
    return datetime(*parts, tzinfo=timezone.utc)


def cfg(**extra):
    base = {"digest_enabled": True, "digest_hour": 8, "digest_tz": "Asia/Bangkok"}
    base.update(extra)
    return base


# Bangkok is UTC+7, so 08:00 there is 01:00 UTC.
def test_off_when_not_enabled():
    assert digest.digest_due({"digest_enabled": False}, utc(2026, 10, 30, 5)) == "off"
    assert digest.digest_due({}, utc(2026, 10, 30, 5)) == "off"


def test_never_sent_starts_the_clock_instead_of_sending():
    assert digest.digest_due(cfg(last_digest_at=None), utc(2026, 10, 30, 5)) == "start"


def test_waits_before_the_chosen_hour():
    last = utc(2026, 10, 29, 2).isoformat()  # yesterday 09:00 Bangkok
    assert digest.digest_due(cfg(last_digest_at=last), utc(2026, 10, 29, 23)) == "wait"  # 06:00 Bangkok


def test_sends_after_the_chosen_hour_once():
    last = utc(2026, 10, 29, 2).isoformat()
    now = utc(2026, 10, 30, 2)  # 09:00 Bangkok
    assert digest.digest_due(cfg(last_digest_at=last), now) == "send"
    assert digest.digest_due(cfg(last_digest_at=now.isoformat()), now + timedelta(hours=3)) == "wait"


def test_switched_on_after_the_hour_waits_for_tomorrow_but_before_it_sends_today():
    # Switched on at 15:00 Bangkok: today's 08:00 is already past.
    on_afternoon = utc(2026, 10, 30, 8).isoformat()
    assert digest.digest_due(cfg(last_digest_at=on_afternoon), utc(2026, 10, 30, 9)) == "wait"
    # Switched on at 05:00 Bangkok: 08:00 today still to come.
    on_early = utc(2026, 10, 29, 22).isoformat()
    assert digest.digest_due(cfg(last_digest_at=on_early), utc(2026, 10, 30, 2)) == "send"


def test_bad_zone_and_hour_fall_back():
    assert str(digest.safe_zone("Not/AZone")) == "UTC"
    assert digest.digest_hour({"digest_hour": 99}) == 8
    assert digest.digest_hour({"digest_hour": None}) == 8
    assert digest.digest_hour({"digest_hour": 0}) == 0


def note(name, kind, message, created="2026-10-30T01:30:00+00:00", ident=1):
    return {"id": ident, "asset_name": name, "alert_type": kind, "message": message, "created_at": created}


def test_split_groups_by_direction_and_includes_resolved():
    notes = [
        note("BTC", BULLISH, "BTC reached 72", ident=1),
        note("ETH", BEARISH + "_resolved", "ETH fell to 28", ident=2),
        note("SOL", "OTHER", "x", ident=3),
    ]
    up, down = digest.split_crossings(notes)
    assert [n["asset_name"] for n in up] == ["BTC"]
    assert [n["asset_name"] for n in down] == ["ETH"]


def test_strongest_and_weakest_skip_bad_scores_and_do_not_repeat():
    rows = [
        {"symbol": "A", "score": 90}, {"symbol": "B", "score": 10},
        {"symbol": "C", "score": None}, {"symbol": "D", "score": float("nan")},
    ]
    strongest, weakest = digest.strongest_and_weakest(rows)
    assert strongest == [(90.0, "A"), (10.0, "B")] or strongest[0] == (90.0, "A")
    assert not set(strongest) & set(weakest)


def test_render_has_sections_times_and_escaping():
    notes = [
        note("BTC <b>", BULLISH, "Score reached 72 & rising"),
        note("ETH", BEARISH, "Score fell to 28"),
    ]
    subject, page, plain = digest.render_digest(
        notes, [{"symbol": "BTC", "score": 72}], cfg(), "https://app.example.com"
    )
    assert subject == "Angstrom daily digest: 2 alerts"
    assert "Turned positive (1)" in page and "Turned negative (1)" in page
    assert "BTC &lt;b&gt;" in page and "&amp; rising" in page
    assert "08:30" in page  # 01:30 UTC shown in Bangkok time
    assert "https://app.example.com" in page and "Asia/Bangkok" in page
    assert "Turned positive (1)" in plain and "- ETH: Score fell to 28" in plain
    one = digest.render_digest(notes[:1], [], cfg(), "u")[0]
    assert one == "Angstrom daily digest: 1 alert"


class FakeTable:
    def __init__(self, db, name):
        self.db, self.name, self.op, self.payload = db, name, None, None

    def select(self, *a):
        self.op = "select"
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def __getattr__(self, name):  # eq, in_, is_, gte
        def chain(*args):
            return self
        return chain

    def execute(self):
        self.db.calls.append((self.name, self.op, self.payload))
        if self.op == "select":
            return type("R", (), {"data": self.db.notes})()
        return type("R", (), {"data": []})()


class FakeDB:
    def __init__(self, notes):
        self.notes, self.calls = notes, []

    def table(self, name):
        return FakeTable(self, name)


def run(config, notes, sender, now):
    db = FakeDB(notes)
    state = digest.send_due_digest(db, "u1", config, [], "me@x.com", sender, "https://app", now=now)
    return state, db


def test_quiet_day_sends_nothing_but_records_the_day():
    sent = []
    config = cfg(last_digest_at=utc(2026, 10, 29, 2).isoformat())
    state, db = run(config, [], lambda *a: sent.append(a) or True, utc(2026, 10, 30, 2))
    assert state == "quiet" and not sent
    assert any(c[0] == "alert_preferences" and "last_digest_at" in c[2] for c in db.calls)


def test_sent_digest_marks_notes_and_day():
    sent = []
    config = cfg(last_digest_at=utc(2026, 10, 29, 2).isoformat())
    state, db = run(config, [note("BTC", BULLISH, "up")], lambda *a: sent.append(a) or True, utc(2026, 10, 30, 2))
    assert state == "sent" and len(sent) == 1
    assert sent[0][0] == "me@x.com" and "BTC" in sent[0][2]
    updates = [c for c in db.calls if c[1] == "update"]
    assert any(c[0] == "user_notifications" and "digested_at" in c[2] for c in updates)
    assert any(c[0] == "alert_preferences" for c in updates)


def test_failed_send_marks_nothing_so_it_retries():
    config = cfg(last_digest_at=utc(2026, 10, 29, 2).isoformat())
    state, db = run(config, [note("BTC", BULLISH, "up")], lambda *a: False, utc(2026, 10, 30, 2))
    assert state == "error"
    assert not [c for c in db.calls if c[1] == "update"]


def test_start_records_now_without_email():
    sent = []
    state, db = run(cfg(last_digest_at=None), [note("BTC", BULLISH, "up")], lambda *a: sent.append(a) or True, utc(2026, 10, 30, 2))
    assert state == "start" and not sent


def test_instant_switch_is_respected_by_the_alert_worker():
    import inspect
    import alerts
    source = inspect.getsource(alerts.evaluate_alerts)
    assert 'alerts_config.get("instant_email") is not False' in source


def test_digest_shows_logos_before_names():
    notes = [{"id": 1, "asset_symbol": "solana", "asset_name": "Solana (SOL)", "alert_type": BEARISH,
              "message": "Score dropped to 27.5/100", "created_at": "2026-10-29T09:00:00+00:00"}]
    results = [
        {"key": "solana", "symbol": "Solana (SOL)", "score": 27.5, "logo": "https://img.example/sol.png"},
        {"key": "AAPL", "symbol": "Apple (AAPL)", "score": 72, "logo": "https://img.example/aapl.png"},
        {"key": "MSFT", "symbol": "Microsoft (MSFT)", "score": 50, "logo": ""},
    ]
    _, page, plain = digest.render_digest(notes, results, cfg(), "https://app")
    assert page.count('src="https://img.example/sol.png"') >= 1
    assert page.index('src="https://img.example/sol.png"') < page.index("Solana (SOL)")
    assert 'src="https://img.example/aapl.png"' in page
    assert "<img" not in plain


def test_logo_helper_rejects_unsafe_addresses():
    from email_brand import asset_logo
    assert asset_logo("") == ""
    assert asset_logo("http://plain.example/x.png") == ""
    assert asset_logo('https://x.example/a.png" onerror="x') == ""
    assert 'src="https://x.example/a.png"' in asset_logo("https://x.example/a.png")


def test_instant_email_passes_the_logo():
    import alerts

    class Table:
        def __init__(self, rows):
            self.rows = rows
        def __getattr__(self, name):
            return lambda *a, **k: self
        def execute(self):
            return type("R", (), {"data": self.rows})()

    class DB:
        def table(self, name):
            return Table([{"id": 7, "asset_symbol": "solana", "asset_name": "Solana (SOL)", "message": "down"}])

    calls = []
    alerts._email_open_crossings(DB(), "u", "me@x.com",
                                 lambda *a, **k: calls.append((a, k)) or True,
                                 {"solana": "https://img.example/sol.png"})
    assert calls and calls[0][1].get("logo_url") == "https://img.example/sol.png"


def test_digest_puts_market_sentiment_first():
    notes = [
        {"id": 1, "asset_symbol": "market:crypto", "asset_name": "🪙 Crypto market sentiment", "alert_type": BEARISH,
         "message": "Market sentiment dropped to 33/100 (strongly negative mood)", "created_at": "2026-10-29T09:00:00+00:00"},
        {"id": 2, "asset_symbol": "solana", "asset_name": "Solana (SOL)", "alert_type": BEARISH,
         "message": "Score dropped to 27.5/100", "created_at": "2026-10-29T10:00:00+00:00"},
    ]
    markets = [
        {"key": "market:crypto", "symbol": "🪙 Crypto market sentiment", "score": 33.0},
        {"key": "market:stock", "symbol": "📈 Stock market sentiment", "score": 58.0},
    ]
    subject, page, plain = digest.render_digest(notes, [], cfg(market_alerts_enabled=True), "https://app", markets=markets)
    assert "2 alerts" in subject
    assert page.index("Market sentiment") < page.index("Solana (SOL)")
    assert "Now 58/100, no alert" in page
    # A market already listed as a crossing is not listed again as a plain reading.
    assert "Now 33/100" not in page
    assert plain.index("Crypto market sentiment") < plain.index("Solana")


def test_digest_hides_market_readings_when_market_alerts_are_off():
    markets = [{"key": "market:stock", "symbol": "📈 Stock market sentiment", "score": 58.0}]
    notes = [{"id": 2, "asset_symbol": "solana", "asset_name": "Solana (SOL)", "alert_type": BEARISH,
              "message": "Score dropped to 27.5/100", "created_at": "2026-10-29T10:00:00+00:00"}]
    _, page, _ = digest.render_digest(notes, [], cfg(), "https://app", markets=markets)
    assert "Market sentiment" not in page
