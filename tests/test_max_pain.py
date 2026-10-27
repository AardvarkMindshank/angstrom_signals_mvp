from max_pain import pain_strike, window_strikes


def test_empty_book_has_no_pain_strike():
    assert pain_strike({}, {}) is None


def test_single_strike():
    assert pain_strike({100.0: 5.0}, {}) == 100.0


def test_symmetric_book_settles_in_the_middle():
    calls = {90.0: 10.0, 100.0: 10.0, 110.0: 10.0}
    puts = {90.0: 10.0, 100.0: 10.0, 110.0: 10.0}
    assert pain_strike(calls, puts) == 100.0


def test_heavy_puts_pull_the_strike_up():
    calls = {100.0: 1.0, 110.0: 1.0}
    puts = {100.0: 1.0, 110.0: 50.0}
    assert pain_strike(calls, puts) == 110.0


def test_heavy_calls_pull_the_strike_down():
    calls = {100.0: 50.0, 110.0: 1.0}
    puts = {100.0: 1.0, 110.0: 1.0}
    assert pain_strike(calls, puts) == 100.0


def test_known_hand_calculation():
    calls = {100.0: 10.0}
    puts = {110.0: 10.0}
    # at 100 puts pay (110-100)*10 = 100; at 110 calls pay (110-100)*10 = 100; tie keeps the first
    assert pain_strike(calls, puts) == 100.0


def test_window_returns_all_when_small():
    assert window_strikes([3.0, 1.0, 2.0], 2.0, 2.0, limit=10) == [1.0, 2.0, 3.0]


def test_window_keeps_the_pain_level_and_limits_size():
    strikes = [float(n) for n in range(1, 101)]
    kept = window_strikes(strikes, 50.0, 95.0, limit=10)
    assert len(kept) <= 11
    assert 95.0 in kept  # the pain level is always drawn
    assert kept == sorted(kept)
