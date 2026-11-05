# Lattice stage 1 report: engine extensions E1–E3

Branch `lattice-stage1`, 5 November 2026. Design: `docs/design/lattice_prism.md` revision 2 (§4, §6), approved for
stage 1 by ChatGPT and Grok. Headless only: nothing in the app, the dashboard, Trend/Stretch/Flow, alerts, the Signal
Matrix or saved configurations changes. Tests use synthetic data and the frozen pre-hold-out cache only.

## What was built

| Part | Files | What it does |
|---|---|---|
| E1 Group outcomes | `signal_groups/outcomes.py`, `evaluate.py` | Optional ordered `outcomes`; first true rule wins; an unknown rule stops evaluation; `otherwise` only when all are false. Group status gates the published outcome (`vetoed` → `vetoed`, `insufficient` → `unknown`, `veto_unknown` → raw outcome marked qualified). Stable ids; `unknown` and `vetoed` reserved. |
| E2 Set decisions | `signal_groups/decision.py`, `sets.py` | Optional three-valued `decision` with Group predicates on outcome, score, condition state and status, and standalone `condition` items. Qualified outcomes are evaluated for both the raw outcome and `vetoed`. No predicate can test Unknown. Result: answer, decisive lines (a sufficient reason from the rule tree) and every line. `scannable(doc)`: a Set without a decision is not scannable. |
| E3 Field descriptions | `signal_library/fields.py`, `signal_groups/validate.py` | Field table for 24 signals (all starter and example members, the ten components, sentiment, flows). The backend validator refuses missing field paths, type mismatches and thresholds outside a fixed range, in conditions, outcomes, transforms and decisions. |
| Display units | `signal_groups/units.py` | "+30" on screen ↔ 0.3 stored, exactly. |
| Compatibility | `tests/lattice_compat.py`, `tests/fixtures/lattice_compat.json` | Snapshot of every starter and design example (content hash, validation, evaluation on two synthetic histories), committed **before** any engine change. |

## Fixtures (§6) and results

`tests/test_lattice_stage1.py`: **80 tests, all passing** (the numbered tests are the §6 fixtures; 17 runs once per
fixed-range field, 52 cases).

| § 6 | Covered by | Result |
|---|---|---|
| 1–4 rule order, unknown stop, fall-through, priority | tests 01–04 | pass |
| 5 status gate | test 05 (4 statuses) and 05b (real evaluator, ok and vetoed) | pass |
| 6 reserved/duplicate ids, renamed labels | test 06 | pass |
| 7–9 qualified, vetoed, unknown and `not` | tests 07–09 | pass |
| 10–11 definite No with a gap; Unknown naming the gap | tests 10–11 | pass |
| 12 ANY groups | test 12 | pass |
| 13 context refused, condition accepted | test 13 | pass |
| 14 not scannable | test 14 | pass |
| 15 outcome predicate needs an embedded version with outcomes | tests 15, 15b (also: Unknown untestable, bad states/statuses, score range, counting and `within_candles` refused), 15c end to end | pass |
| 16 every member described; real values inside the stated ranges | test 16 (3 seeds × 2 history lengths, over 200 values) | pass |
| 17 one out-of-range value per fixed field refused | test 17 (52 cases), 17b (70 on a −1..+1 standard score) | pass |
| 18 type mismatches | test 18 (9 cases) | pass |
| 19 +30 stored as 0.30 | test 19 | pass |
| 20 unchanged hashes, validation and results | test 20 against the pre-change snapshot | pass |
| 21 certified calculations unchanged | test 21: certification code hash identical, `fields.py` outside `CODE_FILES` | pass |

Also: results gain the `outcome` key only for Groups that define outcomes, and every other key is identical (test
`live_results_gain_keys_only…`).

**Full local suite: 718 passed, 12 skipped, 0 failed.**

## Differences from the design, for review

1. **Field table outside the definitions.** The design said definitions "gain `fields`" and that the certification
   record would be regenerated. The table is documentation no calculation reads, so it lives in
   `signal_library/fields.py`, outside `CODE_FILES`. The certified code hash is unchanged and no re-certification is
   needed. The design note is updated to say so.
2. **Not yet in decisions:** counting operators and `within_candles` event filters on standalone items. Both are
   refused at save with a plain message rather than evaluated silently as Unknown. The design note says so.
3. **Signals not in the field table** keep today's structural checks only. All starter and example members are in it.

## Not in this stage

Prism (Run now, scheduled scans, alerts), the editor, E4 fixed subjects, History and strategies. No SQL changes.

## CI

Run 41999575146 on commit d5fcfbd (pushed to `v2`): **all four jobs passed** (tests, chart, overlap, replay).
Results are on the reports branch under `ci/v2/…_d5fcfbd_*`.
- Certification `--check`: matches the committed record.
- Trend/Stretch/Flow Groups vs `signals_v2`: 0 differences in 1,143 comparisons.
- Replay shortcuts compared with the exact path: pass.

**Certification record refreshed (not caused by this stage).** The first run (41995436515, commit ac97aaa) failed
the certification check, and so had the run on `main`'s merge commit 8289e4d this morning. The code hash was
unchanged. The committed record (from 10cdf85) differed from today's runs only in the 16th significant digit of a
few slice-equivalence comparisons, which switched one shortcut off: `ma.position` 1W now uses the exact path instead
of certified slicing (the safe direction). No signal's certification status changed (110 of 113). Both of today's
runs agreed with each other exactly; the record from run 41995436515 is committed.

**Recommendation (separate, small item):** compare slice equivalence with a stated tolerance and keep raw float
digits out of the compared record, so differences in the last digit between CI machines cannot fail the check. That
changes the certification method, so it needs its own note and approval; it is not part of this stage.

## For merge approval

Stage 1 is complete on `lattice-stage1`: design revision 2, engine extensions, 80 new tests, unchanged existing
results, refreshed certification record, CI green. Merging changes nothing users see.
