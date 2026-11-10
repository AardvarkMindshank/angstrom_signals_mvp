"""The funnel's bookkeeping (funnel.py): the rules decided on 10 Nov 2026."""

import funnel as fn
from funnel import NO, UNKNOWN, YES


def _run(answers, flicker=True, n=4):
    st = fn.CoinState.new(n)
    for i, (k, a) in enumerate(answers):
        fn.record(st, k, a, f"t{i}", flicker=flicker)
    return st


def test_a_coin_climbs_only_through_the_stages_it_holds():
    st = _run([(0, YES), (2, YES)])                           # stage 3 is not reachable yet: ignored
    assert fn.place(st)["depth"] == 1 and st.stages[2].answer is None
    st = _run([(0, YES), (1, YES), (2, YES)])
    assert fn.place(st)["status"] == fn.FLAGGED and fn.icon(st) == "🚩"
    fn.record(st, 3, YES, "t9")
    assert fn.place(st)["status"] == fn.CANDIDATE and fn.icon(st) == "✅"


def test_flicker_two_nos_to_leave_and_a_drop_takes_the_later_stages_at_once():
    st = _run([(0, YES), (1, YES), (2, YES), (3, YES)])
    fn.record(st, 1, NO, "a")
    p = fn.place(st)
    assert p["status"] == fn.CANDIDATE and p["leaving"]       # one No: still holds, shown as leaving
    fn.record(st, 1, NO, "b")
    assert fn.place(st)["depth"] == 1 and all(s.answer is None for s in st.stages[2:])
    off = _run([(0, YES), (1, YES), (1, NO)], flicker=False)
    assert fn.place(off)["depth"] == 1
    back = _run([(0, YES), (1, YES), (1, NO), (1, YES), (1, NO)])   # the Nos must be in a row
    assert fn.place(back)["depth"] == 2


def test_unknown_never_promotes_and_pending_leaves_after_three():
    st = _run([(0, UNKNOWN)])
    assert fn.place(st)["status"] == fn.POOL
    st = _run([(0, YES), (1, YES), (2, YES), (3, YES), (0, UNKNOWN)])
    assert fn.place(st)["pending"] and fn.icon(st) == "❔" and not fn.alert_due(st)
    fn.record(st, 0, UNKNOWN, "x"); fn.record(st, 0, UNKNOWN, "y")
    assert fn.place(st)["status"] == fn.POOL


def test_candidate_alerts_once_until_it_leaves():
    st = _run([(0, YES), (1, YES), (2, YES), (3, YES)])
    assert fn.alert_due(st) is True and fn.alert_due(st) is False
    fn.record(st, 3, NO, "a"); fn.record(st, 3, NO, "b")
    assert fn.alert_due(st) is False and not st.latched
    fn.record(st, 3, YES, "c")
    assert fn.alert_due(st) is True


def test_counts_reconcile_and_state_round_trips():
    a = _run([(0, YES), (1, YES), (2, YES), (3, YES)])
    b = _run([(0, YES), (1, YES), (2, YES)])
    c = _run([(0, YES)])
    d = _run([(0, NO)])
    c2 = fn.CoinState.from_dict(c.to_dict(), 4)
    assert fn.place(c2) == fn.place(c)
    k = fn.counts({"a": a, "b": b, "c": c2, "d": d}, 4)
    assert k["pool"] == 4 and k["reached"] == [3, 2, 2, 1] and k["candidate"] == 1 and k["flagged"] == 1
