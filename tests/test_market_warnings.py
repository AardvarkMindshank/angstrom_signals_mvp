import market_store as ms


def capture(fn):
    import builtins
    lines = []
    original = builtins.print
    builtins.print = lambda *a, **k: lines.append(" ".join(str(x) for x in a))
    try:
        fn()
    finally:
        builtins.print = original
    return lines


def test_reasons_are_named():
    assert ms._warn_reason(RuntimeError("JWT expired"))[0] == "sign-in expired"
    assert ms._warn_reason(RuntimeError("permission denied for table x"))[0] == "not allowed"
    assert ms._warn_reason(RuntimeError('column "x" does not exist'))[0] == "table or column missing"
    assert ms._warn_reason(RuntimeError("read timed out"))[0] == "connection"
    assert ms._warn_reason(RuntimeError("odd"))[0] == "other"


def test_each_kind_warns_once_per_ten_minutes_and_shows_the_reason():
    ms._LAST_WARNED.clear()
    first = capture(lambda: [ms._warn(RuntimeError("JWT expired")) for _ in range(3)])
    assert len(first) == 1 and "JWT expired" in first[0] and "sign-in expired" in first[0]
    other = capture(lambda: ms._warn(RuntimeError("permission denied")))
    assert len(other) == 1
    ms._LAST_WARNED["sign-in expired"] -= ms._WARN_EVERY_SECONDS + 1
    again = capture(lambda: ms._warn(RuntimeError("JWT expired")))
    assert len(again) == 1
