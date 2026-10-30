from alerts import BEARISH, BULLISH, canonical_alert, latch_symbol, plan_alert_actions, stored_types


def row(score, key="Crypto|btc", symbol="BTC"):
    return {"key": key, "symbol": symbol, "score": score}


def kinds(actions):
    return [(a[0], a[3] if a[0] == "open" else a[2]) for a in actions]


def test_opens_bullish_when_score_reaches_threshold():
    actions = plan_alert_actions([row(72)], set(), 70, 30)
    assert kinds(actions) == [("open", BULLISH)]
    assert "72.0" in actions[0][4]
    assert "positive reading" in actions[0][4] and "bullish" not in actions[0][4].lower()


def test_opens_bearish_at_or_below_threshold():
    actions = plan_alert_actions([row(30)], set(), 70, 30)
    assert kinds(actions) == [("open", BEARISH)]


def test_no_alert_between_thresholds():
    assert plan_alert_actions([row(50)], set(), 70, 30) == []


def test_latched_alert_does_not_open_again():
    latched = {(latch_symbol("Crypto|btc"), BULLISH)}
    assert plan_alert_actions([row(80)], latched, 70, 30) == []


def test_small_bounce_does_not_release_latch():
    latched = {(latch_symbol("Crypto|btc"), BULLISH)}
    # 61 is below 70 but not 10 points back through the line (60)
    assert plan_alert_actions([row(66)], latched, 70, 30) == []
    assert plan_alert_actions([row(61)], latched, 70, 30) == []


def test_releases_latch_ten_points_back():
    latched = {(latch_symbol("Crypto|btc"), BULLISH)}
    actions = plan_alert_actions([row(60)], latched, 70, 30)
    assert actions == [("resolve", latch_symbol("Crypto|btc"), BULLISH)]


def test_bearish_latch_releases_ten_points_above_line():
    latched = {(latch_symbol("Crypto|btc"), BEARISH)}
    assert plan_alert_actions([row(35)], latched, 70, 30) == []
    assert plan_alert_actions([row(39)], latched, 70, 30) == []
    actions = plan_alert_actions([row(40)], latched, 70, 30)
    assert actions == [("resolve", latch_symbol("Crypto|btc"), BEARISH)]


def test_close_thresholds_clamp_rearm_point():
    # thresholds only 4 apart: the re-arm line (46) is clamped up to the bearish line (52)
    latched = {(latch_symbol("Crypto|btc"), BULLISH)}
    assert plan_alert_actions([row(53)], latched, 56, 52) == []
    actions = plan_alert_actions([row(52)], latched, 56, 52)
    assert ("resolve", latch_symbol("Crypto|btc"), BULLISH) in actions


def test_missing_or_bad_scores_are_skipped():
    rows = [row(None), row("n/a"), row(float("nan")), row(75, key="")]
    assert plan_alert_actions(rows, set(), 70, 30) == []


def test_latch_identity_ignores_case_and_spacing():
    assert latch_symbol("  Crypto|BTC ") == latch_symbol("crypto|btc")
    latched = {(latch_symbol("crypto|btc"), BULLISH)}
    assert plan_alert_actions([row(90, key="Crypto|BTC")], latched, 70, 30) == []


def test_two_assets_are_independent():
    rows = [row(80, key="Crypto|btc"), row(20, key="Crypto|eth", symbol="ETH")]
    result = kinds(plan_alert_actions(rows, set(), 70, 30))
    assert result == [("open", BULLISH), ("open", BEARISH)]


def test_alert_type_helpers():
    assert canonical_alert("BULLISH_THRESHOLD_HELD") == BULLISH
    assert canonical_alert(BEARISH) == BEARISH
    assert stored_types(BULLISH) == [BULLISH, "BULLISH_THRESHOLD_HELD"]


def test_market_rows_follow_the_markets_switched_on():
    from alerts import market_rows
    rows = market_rows({"crypto": 66.0, "stock": None}, ["crypto", "stock"])
    assert [r["key"] for r in rows] == ["market:crypto"]
    assert market_rows({"crypto": 66.0, "stock": 20.0}, ["stock"])[0]["key"] == "market:stock"
    assert market_rows({"crypto": 66.0}, []) == []


def test_market_alerts_use_their_own_lines_and_wording():
    from alerts import market_message, market_rows
    rows = market_rows({"crypto": 66.0, "stock": 50.0}, ["crypto", "stock"])
    actions = plan_alert_actions(rows, set(), 65, 35, describe=market_message)
    assert kinds(actions) == [("open", BULLISH)]
    assert actions[0][1] == "market:crypto"
    assert "Market sentiment reached 66/100" in actions[0][4]
    # The same 10-point reset applies: 56 does not release a 65 alert, 55 does.
    latched = {("market:crypto", BULLISH)}
    assert plan_alert_actions(market_rows({"crypto": 56.0}, ["crypto"]), latched, 65, 35, describe=market_message) == []
    released = plan_alert_actions(market_rows({"crypto": 55.0}, ["crypto"]), latched, 65, 35, describe=market_message)
    assert released == [("resolve", "market:crypto", BULLISH)]


class _Recorder:
    def __init__(self, existing=()):
        self.existing, self.inserted = list(existing), []

    def table(self, name):
        db = self

        class Query:
            def __init__(self):
                self.mode = "select"
            def select(self, *a, **k):
                return self
            def insert(self, row):
                db.inserted.append(row)
                self.mode = "insert"
                return self
            def update(self, *a, **k):
                self.mode = "update"
                return self
            def __getattr__(self, name):
                return lambda *a, **k: self
            def execute(self):
                data = db.existing if self.mode == "select" else []
                return type("R", (), {"data": data})()
        return Query()


def test_evaluate_runs_market_alerts_even_with_asset_alerts_off():
    from alerts import evaluate_alerts, market_rows
    db = _Recorder()
    config = {"enabled": False, "market_alerts_enabled": True, "market_high_alert": 65, "market_low_alert": 35}
    opened = evaluate_alerts(db, "u", [row(90)], config, markets=market_rows({"stock": 30.0}, ["stock"]))
    assert [o["asset_symbol"] for o in opened] == ["market:stock"]


def test_evaluate_skips_markets_when_switched_off():
    from alerts import evaluate_alerts, market_rows
    db = _Recorder()
    config = {"enabled": True, "market_alerts_enabled": False}
    opened = evaluate_alerts(db, "u", [row(50)], config, markets=market_rows({"stock": 30.0}, ["stock"]))
    assert opened == []
