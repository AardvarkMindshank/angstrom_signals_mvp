"""Sequences in Set decisions: "A, then B within N closed daily candles" (docs/design/sequences.md)."""

import copy

import pytest

import prism
import set_history as sh
import signal_groups as sg
from signal_groups import sequence
from signal_groups.transforms import UNKNOWN
from signal_library import certify as cf
from tests.replay_helpers import full_indicators

T, F, U = True, False, UNKNOWN
SPEC = {"within": 3}


def judge(a, b, c=None, n=3):
    return sequence.judge({"within": n}, a, b, c)


# ----------------------------------------------------------------------------------------------- the truth table

def test_b_decides_first():
    assert judge([F, T, F, F], F)["value"] is F
    assert judge([F, T, F, F], U)["value"] is U
    assert judge([F, F, F, F], U)["value"] is F          # no A anywhere: No even while B is unknown
    assert judge([F, T, F, F], T)["value"] is T


def test_a_must_come_on_an_earlier_close_within_n():
    assert judge([T, F, F, F], T)["value"] is F           # same candle is not a sequence
    assert judge([F, F, F, T], T)["value"] is T           # exactly N closes ago counts
    assert judge([F, F, F, F, T], T)["value"] is F        # N+1 does not
    assert judge([F, F, T], T)["value"] is T              # a short history (new listing) is fine


def test_unknown_is_never_met():
    assert judge([F, U, F, F], T)["value"] is U           # an unreadable A could have counted
    assert judge([F, U, T, F], T)["value"] is T           # another A counts anyway
    assert judge([F, F, F, F, U], T)["value"] is F        # beyond N: cannot matter


def test_cancel():
    assert judge([F, F, T, F], T, [F, T, F, F])["value"] is F       # cancelled after A
    assert judge([F, F, T, F], T, [F, F, F, T])["value"] is T       # a cancel before A does not count
    assert judge([F, F, T, F], T, [F, F, T, F])["value"] is T       # nor on A's own close
    assert judge([F, F, T, F], T, [U, F, F, F])["value"] is U       # an unknown cancel leaves it undecided
    assert judge([F, F, T, F], T, [F, T, F, F])["state"] == "cancelled"


def test_states():
    assert judge([F, T, F, F], T) == {"value": T, "state": "met", "since": 1, "left": None}
    armed = judge([F, T, F, F], F)
    assert armed["state"] == "armed" and armed["since"] == 1 and armed["left"] == 2
    assert judge([T, F, F, F], F)["state"] == "armed"                 # just seen; B must come later
    assert judge([F, F, F, T], F)["state"] == "expired"
    assert judge([F, F, F, F], F)["state"] == "waiting"
    assert judge([F, U, F, F], T)["state"] == "unknown"


# ----------------------------------------------------------------------------------------------- the document

def _doc(within=3, **extra):
    doc = copy.deepcopy(prism.demo_sets()["demo:pullback"])
    first, then = doc["decision"]["rule"]["all"]
    doc["decision"]["rule"] = {"sequence": {"first": first, "then": then, "within": within, **extra}}
    return doc


def test_validation():
    assert sg.validate_set(_doc()) == []
    assert any("within" in e for e in sg.validate_set(_doc(within=0)))
    assert any("within" in e for e in sg.validate_set(_doc(within=21)))
    assert any("within" in e for e in sg.validate_set(_doc(within=True)))
    bad = _doc()
    del bad["decision"]["rule"]["sequence"]["then"]
    assert any("needs then" in e for e in sg.validate_set(bad))
    nested = _doc()
    nested["decision"]["rule"]["sequence"]["first"] = copy.deepcopy(_doc()["decision"]["rule"])
    assert any("inside another sequence" in e for e in sg.validate_set(nested))
    three = _doc()
    three["decision"]["rule"] = {"all": [copy.deepcopy(_doc()["decision"]["rule"]) for _ in range(3)]}
    assert any("at most 2 sequences" in e for e in sg.validate_set(three))
    unknown_key = _doc(until=3)
    assert any("unknown keys" in e for e in sg.validate_set(unknown_key))


def test_a_set_without_a_sequence_is_unchanged():
    doc = prism.demo_sets()["demo:pullback"]
    assert sequence.longest(doc["decision"]) == 0 and prism.steps_needed(doc) == 1
    assert prism.steps_needed(_doc(5)) == 13


def test_no_earlier_closes_means_undecided_not_no():
    f = full_indicators(cf.synthetic_crypto(days=300, seed=5).histories["1D"].raw)
    ctx, _ = sh.context_at(f, "crypto", f.index[-1], "x")
    result = sg.evaluate_set(_doc(), ctx)                  # no `earlier`: nothing about earlier closes is known
    seq = result["decision"]["sequences"][0]
    assert result["decision"]["answer"] in ("no", "unknown")
    if result["decision"]["answer"] == "unknown":
        assert seq["state"] == "unknown"


# ----------------------------------------------------------------------------------------------- end to end

@pytest.fixture(scope="module")
def frame():
    return full_indicators(cf.synthetic_crypto(days=330, seed=11).histories["1D"].raw)


def _only(rule):
    doc = copy.deepcopy(prism.demo_sets()["demo:pullback"])
    doc["decision"]["rule"] = rule
    return doc


def test_daily_answers_match_an_independent_count(frame):
    """The engine against a count from the two parts' own daily answers."""
    n = 4
    doc = _doc(n)
    q = doc["decision"]["rule"]["sequence"]
    got = sh.daily_answers(doc, frame, "crypto", "x")
    a = dict(sh.daily_answers(_only(q["first"]), frame, "crypto", "x", warmup=0))
    b = dict(sh.daily_answers(_only(q["then"]), frame, "crypto", "x"))
    days = sorted(a)
    word = {"yes": T, "no": F, "unknown": U}
    checked = 0
    for day, answer in got:
        i = days.index(day)
        window = [word[a[days[i - k]]] for k in range(0, min(n, i) + 1)]
        expected = judge(window, word[b[day]], n=n)["value"]
        assert answer == {T: "yes", F: "no", U: "unknown"}[expected], day
        checked += 1
    assert checked > 200 and any(x == "yes" for _, x in got)


def test_no_look_ahead(frame):
    doc = _doc(4)
    full = dict(sh.daily_answers(doc, frame, "crypto", "x"))
    early = dict(sh.daily_answers(doc, frame.iloc[:250], "crypto", "x"))
    assert early and all(full[d] == x for d, x in early.items())


def test_the_answer_at_a_close_does_not_depend_on_when_it_is_worked_out(frame):
    """A late check (from the stored frame a week on) gives the same answer at that close: no state is kept."""
    doc = _doc(3)
    day = frame.index[200]
    on_time, _ = sh.context_at(frame.iloc[:201], "crypto", day, "x")
    late, _ = sh.context_at(frame.iloc[:208], "crypto", day, "x")

    def earlier_for(f):
        return lambda d: (sh.context_at(f, "crypto", d, "x")[0], None)

    a = sg.evaluate_set(doc, on_time, earlier=earlier_for(frame.iloc[:201]))["decision"]
    b = sg.evaluate_set(doc, late, earlier=earlier_for(frame.iloc[:208]))["decision"]
    assert a["answer"] == b["answer"] and a["sequences"] == b["sequences"]


def test_prism_row_and_columns(frame):
    doc = _doc(3)
    cols = prism.columns(doc)
    assert len(cols) == 1 and "then" in cols[0][1] and "within 3 closes" in cols[0][1]
    ctx, _ = sh.context_at(frame, "crypto", frame.index[-1], "x")
    result = sg.evaluate_set(doc, ctx, earlier=lambda d: (sh.context_at(frame, "crypto", d, "x")[0], None))
    row = prism.row("X", result, "")
    assert row["answer"] in ("yes", "no", "unknown") and cols[0][0] in row["lines"]
    assert result["decision"]["sequences"][0]["state"] in sequence.STATES


def test_prism_reconstruction_reads_earlier_closes_like_the_history():
    """Scheduled scans reconstruct each earlier close; the answers match the daily history at the same closes."""
    from signal_library import replay as rp

    ds = cf.synthetic_crypto(days=330, seed=11)
    doc = _doc(3)
    history = ds.histories["1D"]
    picks = [history.raw.index[i] for i in (250, 290, 320)]
    frame = full_indicators(history.raw)
    daily = dict(sh.daily_answers(doc, frame, "crypto", "x"))
    for start in picks:
        run = rp.ReplayRun(rp.DISPLAY, ds.candles, max_steps=prism.steps_needed(doc), reuse_frames=True,
                           indicators=full_indicators)
        cutoff = prism._cutoff(run, "crypto", "x", start)
        rows = prism.run_now(doc, [("crypto", "x", "X")], live_context=None, replay=(run, cutoff))
        assert rows[0]["answer"] == daily[start.strftime("%Y-%m-%d")], start
        assert len(run.steps) <= prism.steps_needed(doc)


def test_editor_round_trip_and_words():
    import lattice_component_check as c
    import lattice_sets as ls

    model, choices = c.harness_set()
    first = dict(model["lines"][0])
    then = {"target": "outcome", "group": "trend_with_labels", "op": "is_not", "value": "bearish"}
    model["lines"].append({"seq": {"first": [first], "then": [then], "within": "99", "cancel": [dict(first)]}})
    model = ls.clean_model(model, choices)
    assert model["lines"][1]["seq"]["within"] == sequence.MAX_WITHIN       # kept within the limit
    doc = ls.to_document(model, choices)
    assert sg.validate_set(doc) == []
    assert "sequence" in doc["decision"]["rule"]["all"][1]
    back, err = ls.from_document(doc, choices)
    assert err is None and back["lines"] == model["lines"]
    words = ls.describe(model, choices)
    assert "earlier close, then" in words and "within 20 closed daily candles" in words and "unless" in words
    # An unfinished THEN box blocks saving and is never saved half-made.
    model["lines"][1]["seq"]["then"] = []
    assert any("needs at least one Then line" in b for b in ls.checks(model, choices)["blocks"])
    assert "sequence" not in str(ls.to_document(model, choices).get("decision"))
    # At most two THEN boxes survive cleaning.
    many = {**model, "lines": [{"seq": {"first": [first], "then": [then], "within": 3}}] * 3}
    assert sum("seq" in l for l in ls.clean_model(many, choices)["lines"]) == 2


def test_armed_shows_beside_no():
    result = {"status": "ok", "groups": [], "standalone": [],
              "decision": {"answer": "no", "decisive": [], "lines": [],
                           "sequences": [{"state": "armed", "since": 1, "left": 2, "within": 3, "path": "p",
                                          "text": "A 1 close ago; B not yet (2 closes left)"}]}}
    row = prism.row("X", result, "")
    assert row["armed"] == {"left": 2, "text": "A 1 close ago; B not yet (2 closes left)"}
    result["decision"]["sequences"][0]["state"] = "waiting"
    assert "armed" not in prism.row("X", result, "")

