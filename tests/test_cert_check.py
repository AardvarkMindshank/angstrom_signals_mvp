"""--check ignores the informational slice_reason text but compares everything else (point_in_time.md §13)."""

import copy

import replay_certify as rc


def _record():
    return {"suite_version": 2, "code_sha256": "abc", "generated_by": {"run_id": 1},
            "signals": {"bollinger.position@1": {"15m": {"algorithm": "certified", "slice_equivalent": False,
                                                         "slice_reason": "x: .value.lower: differs by 1.0e-06"}}}}


def test_reason_text_and_run_details_are_not_compared():
    a, b = _record(), _record()
    b["signals"]["bollinger.position@1"]["15m"]["slice_reason"] = "x: .value.standard_score: differs by 3.2e-09"
    b["generated_by"] = {"run_id": 2}
    assert rc._compared(a) == rc._compared(b)


def test_equivalence_and_certification_are_still_compared():
    for field, value in (("slice_equivalent", True), ("algorithm", "not_certified")):
        b = _record()
        b["signals"]["bollinger.position@1"]["15m"][field] = value
        assert rc._compared(_record()) != rc._compared(b)
    b = copy.deepcopy(_record())
    b["code_sha256"] = "other"
    assert rc._compared(_record()) != rc._compared(b)
