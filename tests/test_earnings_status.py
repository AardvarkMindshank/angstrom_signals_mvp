from market_store import earnings_status


def test_summary_counts_and_ages():
    now = 1_800_000_000.0
    rows = [
        {"asset_id": "aapl", "next_earnings": "2026-10-30", "earnings_checked_at": "2027-01-15T07:55:00+00:00"},
        {"asset_id": "SPY", "next_earnings": None, "earnings_checked_at": "2027-01-15T07:00:00+00:00"},
        {"asset_id": "NEW", "next_earnings": None, "earnings_checked_at": None},
        {"asset_id": "", "next_earnings": None},
        "junk",
    ]
    out = earnings_status(rows, now=1_800_000_000.0 + 0)
    assert out["stocks"] == 3
    assert (out["with_date"], out["none_known"], out["never_checked"]) == (1, 1, 1)
    assert out["lines"][0]["ticker"] == "NEW"          # never checked first
    assert out["lines"][1]["ticker"] == "AAPL"
    assert out["newest_check_ago"] is not None and out["oldest_check_ago"] >= out["newest_check_ago"]


def test_empty_input():
    out = earnings_status([])
    assert out["stocks"] == 0 and out["newest_check_ago"] is None and out["lines"] == []
