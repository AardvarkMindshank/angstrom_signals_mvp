# Point-in-time evaluation: Stage 3 report (Groups and Sets)

Branch `feature/replay-groups`, head `861391d`, built on the merged Stages 1–2 (main `f795258`).
**Not merged and not deployed.** Stages 4 and 5 have not been started.

All four CI jobs pass on `861391d`: 666 tests, the certification record still matches, the chart checks and the
overlap checks. Implementation notes are in §12 of the design note.

## What was built

**Point-in-time mode.** `evaluate_group(doc, ctx, data_mode="point_in_time", as_of=T)` and
`evaluate_set(doc, ctx, data_mode="point_in_time", market_context=...)` take a replay context at T.
- These are refused with status `unsupported` and a reason: a live context in point-in-time mode, a replay
  context in live mode, or a context at a different T.
- Market contexts must be replay contexts at the same T, otherwise the item is skipped with the reason.
- Live results are unchanged byte for byte (golden snapshot).

**Members.** Every member row in a replayed result has `replay_availability`: `replayable`, `not_replayable`,
`no_history_at_T`, or the signal's own status. Missing members go through the existing coverage, exclude/neutral
and three-valued condition rules, unchanged.

**Completeness**, on every replayed Group and Set:
- **Label:** complete, partial, limited, or partial and limited.
- **For each missing member:** the reason, whether it is critical and why, whether it affects score coverage, and
  which confirmations and vetoes it actually left unknown.
- **Limitations:** the texts of the sources used.
- **`qualified`:** true for a partial or limited result, or whenever a veto is unknown. A qualified result is never
  to be shown without its qualification.
- **Sets:** each Group's label and the Set's worst case. Missing standalone or applicable market items count;
  non-applicable items (Bitcoin context for a share) do not.

**Critical members:** members any veto depends on, and score members without which the minimum coverage cannot be
reached.

**Coverage profiles.** `group_coverage` and `set_coverage` produce date ranges, each with a level (replayable,
reconstructed with limitations, partially evaluable, live only), the missing and critical-missing members and the
reasons. They are computed from the certification record and the history each source actually has. Flow history
starts come from the first live (not backfilled) sighting.

## Behaviour on the starters and the example Set

- Both starter Groups replay as **complete** on crypto data: every member is certified.
- On adjusted share prices they replay as **limited**, with the limitation text attached.
- The **example Set** replays as **partial**: its Bitcoin ETF item uses non-point-in-time (backfilled) flows and
  is marked live only, so it is skipped and listed as missing. Its two Groups are each complete.
- A Group with a veto on a derivatives signal replays as **veto unknown, partial, qualified**. The derivatives
  member is flagged critical, and the veto is listed as unknown because of it.

## Tests (14 new, `tests/test_replay_groups.py`)

- **Replayed starters equal the live starters on data physically cut at T** (both starters): members, scores,
  conditions and diagnostics are identical apart from administrative and point-in-time-only fields.
- **Missing members:** a not-replayable veto member gives an unknown veto, a partial and qualified result, and a
  critical flag. A missing score member is excluded under the existing coverage rules. Only conditions actually
  left unknown are listed.
- **Limited sources:** limitations are carried into completeness.
- **Critical members:** the rules, including the minimum-coverage case.
- **Mode/context mismatches** are refused.
- **Research-mode Group replays** refuse the hold-out.
- **Sets:** the live-only market item is skipped and the Set is partial; a market context that is not a replay at T
  is refused; a point-in-time flows item is replayed with `available_at <= T`; Bitcoin context does not count as
  missing for a share.
- **Coverage profiles:** periods and levels, live only, critical missing, Set coverage including flow starts, and
  uncertified signals making coverage partial.
- **Live golden snapshot** unchanged.

## Resource measurement (CI, real indicators, exact path)

The example Set (two Groups, standalone timeframe alignment and 4-hour levels) replayed at consecutive daily
cutoffs on synthetic crypto data:

| Steps | Seconds | Per step | Peak Python memory | Process memory growth |
|---|---|---|---|---|
| 30 | 44 | 1.45 s | 6 MB | 0 MB |
| 90 | 131 | 1.45 s | 10 MB | 0 MB |

- Memory is small and flat.
- Time is dominated by recomputing indicators on all five timeframes at every step (the exact path). Timeframe
  alignment reads all of them, including 15-minute data.
- That is acceptable for research jobs in CI. It is too slow for a 90-day replay inside a page.
- Stage 5 (benchmarks and optimisation) can use:
  - the certified slice shortcut, which most of these signals hold;
  - reusing a timeframe's indicator frame when no new candle has closed between two cutoffs (allowed only under
    the same certification).

No speed claims are made beyond these measurements.

## Deviations

None from the accepted design. The clarifications made while building are recorded in §12:
- only conditions actually left unknown are listed;
- non-applicable market items do not count as missing;
- multi-timeframe alignment's history starts when its second timeframe has data.

## Ready for review

Waiting for approval before merging, and before Stages 4 (admin "as of" inspector) and 5 (benchmarks and
optimisation).
