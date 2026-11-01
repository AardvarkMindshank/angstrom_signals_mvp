# Research method changes

Development-only research code (`research.py`, `research_stats.py`). The live app does not use either file.

## v2 (31 Oct 2026)

1. **Labels stop at the hold-out boundary.** In v1, forward returns were computed on the full price series and only the signal dates were cut. The last development labels therefore used up to 31 bars of hold-out prices (to 12 Dec 2024 for stocks, 29 Nov 2024 for crypto). From v2, every bar on or after 30 Oct 2024 is removed before scoring, so no label, score or histogram can reach past it. A test changes every hold-out price and checks that the development report is identical.
2. **Score histogram and parity check use development dates only.** In v1 they also covered hold-out dates. They used scores only, with no returns.
3. **New primary statistics** (`research_stats.py`). A calibration study on synthetic markets found that the v1 per-asset time-series rank correlation leans towards "Stretch positive" and "Trend negative" even when there is no effect. Tests on it gave false alarms 35–44% of the time at hold-out length. The new statistics are:
   - Claim A: real-time own-history percentile × within-date return rank.
   - Claim B: unchanged spread, now with a studentised test.
   - Claim C: ATR%'s gain in rank correlation over a benchmark.
   
   All use a studentised joint-date block bootstrap with a t reference and a calibrated inflation factor.
4. **Faster cross-section.** The cross-section code was rewritten in numpy. A test checks it gives identical results to the v1 code.
5. **Parity check.** Now run at 90, 200 and 365 bars of history (the app's slider range).

The v1 report is kept unchanged on the reports branch at `research/2026-10-31_0908_limit0/`. To reproduce it, check out commit `a4e7a41` and run with the same price cache.

## v3 (1 Nov 2026), after the hold-out

**Dates without a valid forward target are no longer observations.** `forecast_gain_rows` (Claims C1 and C2) used to keep every date in the evaluation window as a row, including the last *h*+1 dates, which have no measurable later move. Those rows were empty: they added nothing to the estimate but counted in the reported number of dates and in the degrees of freedom. From v3, only dates with at least one valid triple (candidate, benchmark, target) are rows. The other statistics (spread, relative timing) already worked this way. `tests/test_valid_rows.py` checks the rule for all three statistics, and fails on the v2 code.

### Permanent limitation of the frozen hold-out (tag holdout-spec-v1, method v2)

The hold-out was run once, with the v2 code, and **its results stand as recorded. They will not be recomputed or silently corrected.**

- C1 reported 471 dates and C2 701, where the valid counts are 463 and 693.
- C2 used 35 degrees of freedom where 34 was the valid figure.
- The estimates are unaffected.
- The standard errors include 8 empty rows out of 471 / 701. C1's outcome would have changed only if its standard error had been about 8% larger; the effect of these rows is far smaller.

This is recorded in the hold-out specification (section 13) and in `governance/holdout-spec-v1-signoff.md` on the reports branch.
