# Hold-out validation specification

Draft for sign-off · Oct 31, 2026 · @Aardvark Mindshank

**Revision 2. Not ready to freeze yet.** The statistics for Claim A and Claim C have been replaced because the revision 1 versions were not valid tests (section 3). The corrected development run, which uses development data only, has not been run yet, and its numbers feed two of the decisions in section 11. Revision 1 is kept in the doc's version history (rev 9). Nothing has been run on the hold-out, and the live app has not changed.

## 0. What changed in revision 2

| # | Change | Why | Section |
| --- | --- | --- | --- |
| 1 | **Claim A's statistic replaced.** Each stock's signal is now placed against its own *past* values, and its forward return is ranked against other stocks on the same date. | The revision 1 statistic leans towards both A claims even when there is no effect (+0.040 and +0.051 at hold-out length), giving false alarms 35–44% of the time instead of 5%. | 2, 3 |
| 2 | **Claim A is narrowed** to how a stock does *against other stocks*, not against cash. | Market-wide timing cannot be tested in two years (about 33 independent 14-day windows of one market). The new statistic removes the market's move. | 1, 2 |
| 3 | **Claim C's statistic replaced.** ATR%'s rank correlation with later move size, minus the trailing-volatility benchmark's. | The partial correlation leans positive with no effect (+0.017) and gave false alarms about 35% of the time. | 2, 7 |
| 4 | **Tests are studentised:** a t reference with blocks − 1 degrees of freedom, and the bootstrap spread inflated by a factor calibrated on synthetic markets. P-values and confidence intervals are now separate. | The block bootstrap underestimates the spread by about 15% at hold-out length. | 3 |
| 5 | **Exact embargo dates for each class:** stocks from 12 Dec 2024, crypto from 29 Nov 2024. This replaces the single date of 16 Dec. | Worked out from the calendar of the frozen cache (dates only, no prices). | 8 |
| 6 | **Development code fixed.** Every bar from the hold-out start onwards is removed before scoring. A test changes every hold-out price and confirms the development output is identical. The revision 1 report is kept unchanged. | This corrects the leak disclosed in revision 1. | 8 |
| 7 | **Crypto portfolio accounting specified and tested.** The 14 staggered tranches count as one portfolio. The survivor-bias wording is corrected. | Point 3 of the review. | 6 |
| 8 | **New section on significance versus minimum effects**, and a fourth outcome label. | Point 4 of the review. | 4 |
| 9 | **Forward monitoring:** descriptive only, plus one confirmatory analysis on a fixed date. | Point 5 of the review. | 10 |
| 10 | **Development-stage gate for Claim A.** A1 and A2 go to the hold-out only if the new statistic supports them on development data. | The new statistic has not yet been measured on development data. | 5 |

**Where I disagree with the review.** Switching to a null-centred bootstrap, as the review suggested, would not have fixed the problem. The synthetic study shows the percentile and null-centred versions are equally wrong for Claim A (35% against 37% false alarms) because the problem is the statistic's bias, not how the p-value is read off. Bias-correcting with a rotation null still left 15% false alarms. The fix had to be a statistic that is centred on zero by construction.

## 1. Claims, assets and outcomes

Three claims are tested. A and C are reworded in revision 2 (marked **changed**):

| Claim | In plain words |
| --- | --- |
| **A. Stocks, relative timing** (changed) | When a large US stock's Stretch ("oversold") points are high *for that stock*, it goes on to beat other large stocks. When its Trend points are high for that stock, it goes on to lag them. |
| **B. Crypto, ranking** | On any day, coins with more Trend points go on to beat coins with fewer Trend points. |
| **C. Volatility** (changed) | ATR% ranks the size of later moves better than recent close-to-close volatility does. It says nothing about direction. |

**Assets:** 59 stocks and 23 coins. AAPL, MSFT, BTC-USD and ETH-USD are left out because they were looked at on 29 Oct.

**Outcomes** (one new label; definitions in section 4):

- **Confirmed**
- **Confirmed, clearly above the minimum** (new)
- **Inconclusive**
- **Contradicted**

No outcome changes the app automatically.

**Settings shared by every test** (unchanged except where marked):

- **Scoring:** production `scoring.py` at default weights, with adaptive weighting off.
- **Prices:** frozen, adjusted Yahoo daily bars, completed bars only.
- **Trade timing:** the signal is read at the close of *t*. Entry is at the close of *t*+1 and exit at the close of *t*+1+*h*.
- **Horizons:** counted in bars, which are trading days for stocks and calendar days for crypto.
- **Hold-out dates** (changed): stock signals from 12 Dec 2024 to the last bar, 29 Oct 2026. Crypto signals from 29 Nov 2024 to 30 Oct 2026. In both cases only signals whose exit falls by the last bar count.

## 2. The primary tests

There are five primary tests. Each is one-sided in the direction stated in advance. The statistic for A and C is **changed**; B is unchanged.

| ID | Primary statistic | Horizon | Assets | Direction | Minimum meaningful effect | Dates | t degrees of freedom |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Relative timing of Stretch points (changed) | 14 trading days | 59 stocks | positive | +0.02 | 456 | 16 |
| A2 | Relative timing of Trend points (changed) | 14 trading days | 59 stocks | negative | −0.02 | 456 | 16 |
| B | Top third minus bottom third by Trend points, mean % forward return | 14 days | 23 coins | positive | +0.50% per 14 days | 686 | 24 |
| C1 | ATR% forecast gain over trailing volatility (changed) | 7 trading days | 59 stocks | positive | +0.02 (new) | 463 | 23 |
| C2 | Same | 7 days | 23 coins | positive | +0.02 (new) | 693 | 34 |

**Relative timing (A1, A2).** For stock *j* on date *t*:

- *u* is where today's Trend or Stretch points sit among **all of that stock's earlier values**, as a percentile minus 0.5, with ties counting half. It needs at least 250 earlier bars. Development years are used as history, which is allowed because they were known at the time.
- *v* is the stock's forward return ranked against the other stocks on that date, centred and scaled to a spread of 1.
- The statistic is the mean of √12 × *u* × *v* over all stock-dates. This reads like a rank correlation.

Neither *u* nor *v* uses an average taken over the hold-out, so the statistic is zero in expectation when there is no effect (section 3).

**Spread (B).** On each date with at least 8 coins, take the mean forward return of the top third by Trend points minus the bottom third. Ties are broken by ticker. The statistic is the mean over dates.

**Forecast gain (C1, C2).** For each asset, over its hold-out dates, take the Spearman correlation of ATR% with later move size, minus the Spearman correlation of trailing move size with later move size. Average over assets.

- *Later move size:* the mean absolute daily % move from *t*+1 to *t*+8.
- *Trailing move size:* the mean absolute daily move over the 14 days up to *t*.

**Development estimates** for the new A and C statistics come from the corrected development run, which has not been run yet. B's development estimate is +1.46% \[+0.54, +2.46\] (revision 1 method). The revision 1 development numbers for A carry the bias described in section 3, so they no longer support A on their own.

## 3. How p-values and intervals are calculated (changed)

Every primary statistic is a sum over dates divided by a sum over dates. That lets one resampling scheme serve all five tests.

1. **Standard error.** Draw 10,000 joint-date circular block bootstrap samples (seed 20261031). All assets are resampled on the same dates. The block is max(20, 2*h*) bars: 28 for A and B, 20 for C. The standard error is κ × the spread of the resampled statistic.
2. **Inflation factor κ,** fixed from the study below: **1.2 for A and C, 1.0 for B**.
3. **p-value** (a test): one-sided, against Student's t with (number of blocks − 1) degrees of freedom. It answers "if there were no effect, how surprising is this estimate?"
4. **95% confidence interval** (not a test): the estimate ± t(0.975) × standard error. It describes the range of effect sizes consistent with the data. It is reported for every test but plays no part in Holm.

**Calibration study.** Synthetic markets were built to the hold-out's sizes:

- 59 stocks over 456 dates, or 23 coins over 686 dates.
- Fat-tailed returns with volatility clustering and a common market factor.
- Trend and Stretch points built with the live rules' windows and point sizes, so the signals are as persistent as the real ones and are computed from the same prices.
- Overlapping 14-day forward returns.
- **No real effect anywhere.**

The table shows how often each method declared an effect. A valid test should be at or below the nominal rate.

| Statistic and method | A1 at 5% / 1% | A2 at 5% / 1% | B at 5% / 1% |
| --- | --- | --- | --- |
| Revision 1 statistic, percentile p-value (revision 1 spec) | 35% / 21% | 42% / 23% | 8% / 1.6% |
| Revision 1 statistic, null-centred bootstrap | 37% / 20% | 44% / 25% | 6% / 1.8% |
| Revision 1 statistic, bias-corrected by rotation | 15–18% / 6–8% | 14–19% / 7–9% | – |
| **New statistic, studentised, κ as fixed** | **4.7% / 0.8%** | **4.7% / 0.7%** | **5.0% / 1.0%** |
| Same, harsher market (stronger clustering, heavier tails, more co-movement) | 5.2% / 0.8% | 5.2% / 1.2% | 5.2% / 1.2% |

There were 500–1,000 synthetic datasets per row, so each rate is ± about 1.5 points. For C, checked on a market where ATR% and the benchmark are equally good by construction, the new test gave 3.8% at 5% and 1.0% at 1%. The revision 1 partial correlation gave about 35% at 5%.

**Why the revision 1 statistic failed.** It ranked each stock's signal and forward return over the stock's own sample. Persistent signals and overlapping returns then share that sample's average. Over 456 dates this makes "high Trend, then weaker returns" and "oversold, then stronger returns" appear even when returns are pure chance. The effect is smaller over the development period's 2,200 dates (about +0.01), but it still pushed development false alarms to 14–16%. **The development results for Claim A in audit section 8 were partly overstated for this reason.**

**What κ corrects.** With few blocks, the block bootstrap underestimates the true spread by about 15%, and longer blocks did not help (tested at 28, 42, 60 and 90). κ depends on synthetic markets, which is a limitation. The harsher-market check suggests it is not fragile. The code is `research_stats.studentised_test`, with tests in `tests/test_research_stats.py`.

## 4. Significance versus minimum meaningful effects (new)

Three different statements can be made about an estimate, and they should not be confused:

| Statement | What it requires | What it means |
| --- | --- | --- |
| **Statistically significant** | The one-sided p-value passes Holm (section 5) | Evidence that the effect points in the claimed direction. It says nothing about size. |
| **Point estimate at or above the minimum** | Estimate ≥ the threshold in section 2 | The best single guess is big enough to matter. It is *not* evidence that the true effect is that big. |
| **Evidence the true effect exceeds the minimum** | One-sided 95% lower bound ≥ the threshold, which is the same as p (against the threshold) ≤ 0.05 | The data rule out effects smaller than the threshold. |

**The outcome labels:**

- **Confirmed:** significant **and** the point estimate is at or above the minimum.
- **Confirmed, clearly above the minimum:** the above **plus** evidence that the true effect exceeds the minimum. This second check is not adjusted for multiple testing, so it is descriptive.
- **Contradicted:** the one-sided 95% bound in the claimed direction is below zero. This is not adjusted either, so each claim has about a 5% chance of a false "Contradicted".
- **Inconclusive:** anything else.

**The thresholds are unchanged** (±0.02, +0.50% per 14 days), and C's +0.02 is new because its statistic is new. They remain judgement calls:

- *A, ±0.02:* at the low end of what is usually treated as a useful rank correlation for one signal.
- *B, +0.50%:* about the round-trip cost of a long-short version at base costs. A long-only user must also clear the gate in section 6.
- *C, +0.02:* a gain in rank correlation over the benchmark small enough to be plausible and large enough to justify showing ATR% instead of a simpler measure.

**Limitations to keep in mind:**

- **Estimates that pass are inflated.** When power is low, as here (section 9), the estimates that pass a significance test are on average larger than the true effect. A Confirmed estimate of 0.03 may well reflect a true 0.015.
- **Lower bounds are wide.** With two years of data, "clearly above the minimum" is reachable only for large effects. In practice that means ATR%.
- **No economic link for A and C.** A rank-correlation threshold is not tied to money made. Only B has an investable check (section 6).

## 5. Primary versus exploratory, multiple testing, and the development-stage gate

**Holm across the primary tests.** The family false-alarm rate is 5%, using the one-sided p-values from section 3. With five tests the ordered cut-offs are 0.010, 0.0125, 0.0167, 0.025 and 0.050. If the gate below removes a test, the family shrinks: with *m* tests, the cut-offs are 0.05/*m*, 0.05/(*m*−1), and so on up to 0.05.

**Development-stage gate (new).** Claim A was chosen using the biased revision 1 statistic. Before the freeze, A1 and A2 are measured on development data with the new statistic. Each goes to the hold-out only if its 14-day development estimate is in the claimed direction **with a one-sided p of 0.05 or less**; otherwise it is dropped. This decision uses development data only, is made before the hold-out is opened, and is recorded in section 11 with the numbers. B and C are not gated: their development evidence did not come from the biased statistic.

**Exploratory, unchanged from revision 1 (reported, never able to confirm anything):**

- other horizons;
- the overall score, single factors and Flow;
- the old statistics, shown for continuity;
- regimes and extremes;
- the long-only results (a practical gate for B, not a test);
- ATR% against the stronger benchmarks, and its calibration;
- the four assets already seen;
- each half of the hold-out.

Exploratory cells carry plain 95% intervals with no p-values, so they cannot be read as tests. The report states how many there are.

## 6. Crypto long-only portfolio (accounting specified and tested)

B is called **useful for the product** only if it is Confirmed **and** passes a practical gate. The gate is unchanged: the long-only top third, after base costs, earns at least as much a year as all coins held equally. The report also splits the 14-day spread into *top third minus all coins* (what a long-only user can capture) and *all coins minus bottom third* (needs shorting).

**Accounting.** It is implemented in `research_stats.long_only_portfolio`, and each rule is covered by a test:

| Rule | Detail | Test |
| --- | --- | --- |
| Timing | Signal read at the close of *t*; trades at the close of *t*+1. The move from *t* to *t*+1 is not earned. | `test_entry_is_at_the_next_close` |
| Holdings between trades | Real holdings. Weights drift with prices every day and are only reset at a trade. | `test_weights_drift_and_turnover_and_costs` |
| Selection | A third of the coins with a signal and a price that day (7 of 23), equal weight, ties broken by ticker. | `test_spread_breaks_ties_by_column_order_and_needs_enough_assets` |
| Turnover | Traded value = sum of \|target weight − drifted weight\| (one-way turnover is half of this). Buying from cash counts. | `test_weights_drift_and_turnover_and_costs` |
| Costs | Traded value × cost per side: base 0.20%, stress 0.50%. Charged on the day of the trade. | same |
| Benchmark | All eligible coins at equal weight, run **through the same code** with the same schedule, drift and costs. A strategy holding every coin matches it exactly. | `test_strategy_holding_everything_equals_the_benchmark` |
| Staggering | 14 tranches, each a separate account with 1/14 of the capital, re-selecting on days *k*, *k*+14, and so on. The combined return is their capital-weighted total. The first 15 days, while tranches are still buying in, are left out of the results. | `test_tranches_are_staggered_and_combined_by_capital` |

**The tranches are one portfolio, not 14 experiments (changed).** They overlap in time and mostly hold the same coins. Inference therefore uses the single daily series of combined net return minus benchmark net return, with the same joint-date block bootstrap (block 28). Nothing is averaged or counted per tranche. The report gives the yearly excess with a 95% interval, both portfolios' yearly return and maximum drawdown, traded value per rebalance, the stress-cost result, and Bitcoin buy-and-hold as a reference.

**Survivor bias (wording corrected).** All 23 coins still trade today, so coins that collapsed or were delisted during the period are missing. That may make the long-only results optimistic or unrepresentative, mainly by leaving losers out of the equal-weight pool and out of the top third. It is **not** a strict upper bound: a missing coin could also have been one the strategy would have avoided, so the true effect could be higher or lower.

## 7. ATR%: benchmark and optional calibration

**Primary (changed).** C1 and C2 now ask whether ATR% *ranks* later move sizes better than the trailing 14-day average absolute move. The test is the forecast gain from section 2. Because it compares the two directly, it is zero when they are equally good, and the calibration study confirmed it holds its false-alarm rate. The revision 1 partial correlation did not, because rank-partialling leaves part of the benchmark's information inside ATR%.

**Exploratory benchmarks** (same statistic, no p-values):

- exponentially weighted volatility with decay 0.94;
- the 60-day average absolute move.

If ATR% beats the 14-day benchmark but not these, the conclusion is "a convenient volatility measure, not a better one".

**Ranking versus calibrated ranges (unchanged).** Passing C1 or C2 shows ATR% ranks well. It does not show that a printed "±X% expected move" is the right size. That second question needs a range fixed in advance.

**Calibration: optional, ready without delay.** Fitting needs development data only, and it runs in the same corrected development run as everything else:

- **The range:** ±*k* × ATR% × √7 around the entry price. *k* is fitted for each asset class at 50% and 80% coverage.
- **Internal check before the freeze:** fit on 2016–2021 and measure coverage on 2022 up to the boundary. The early fit uses prices cut at 1 Jan 2022, so its labels cannot see the check period.
- **Final *k*:** refitted on all development data.
- **Rule for including it:** calibration joins the hold-out as an exploratory check only if the internal check lands within ±5 points of 50% and 80% for both classes, and Angus and Drew sign off the *k* values in section 11.
- **Otherwise** it is deferred and the main work goes ahead without it.
- **On the hold-out:** report pooled coverage with a block-bootstrap interval and the spread of coverage across assets. "Calibrated" means within ±5 points. The same ranges built from exponentially weighted volatility are compared using the pinball loss.

## 8. Leakage prevention and production consistency

### 8.1 The boundary and the embargo (dates corrected)

|  | Stocks | Crypto |
| --- | --- | --- |
| Last development bar | 29 Oct 2024 | 29 Oct 2024 |
| First hold-out bar | 30 Oct 2024 | 30 Oct 2024 |
| Latest price a development label used (revision 1 leak) | 12 Dec 2024 (hold-out bar 31) | 29 Nov 2024 (hold-out bar 31) |
| **First eligible hold-out signal** | **12 Dec 2024**, entry at the close of 13 Dec | **29 Nov 2024**, entry at the close of 30 Nov |
| Last bar in the frozen cache | 29 Oct 2026 | 30 Oct 2026 |
| Hold-out bars | 501 | 731 |

**Rule.** The longest development label covered 31 bars: entry one bar after the signal, exit 30 bars later. A hold-out signal is eligible when its entry falls *after* the last bar any development label used. That excludes the first 30 hold-out signal dates. A test checks that one bar earlier would overlap and the chosen bar does not.

These dates come from the calendar column of the frozen cache. No prices were read. The revision 1 date of 16 Dec was conservative by two trading days for stocks and 17 days for crypto.

**Hold-out start check.** The start is fixed at 30 Oct 2024, and `research.checked_start` stops the run if the cache implies a different date.

### 8.2 Development code corrected (point 2 of the review)

- **Bars removed before anything else (v2).** `research.py` now removes every bar on or after the hold-out start *before* scoring or labelling, via `development_frames`. Labels at the end of development simply come out empty. The score histogram and parity check now cover development dates only.
- **Tests that prove it:**
  - `test_changing_holdout_prices_changes_nothing_in_development` multiplies every hold-out price by 3 and checks that all development labels match.
  - `test_development_run_ignores_holdout_values` runs the whole development pipeline twice, with wildly different hold-out prices and scores, and checks the reports match.
  - `test_development_run_end_to_end_never_touches_the_holdout` replaces every hold-out value with a missing value and checks the run still completes cleanly.
  - `test_v1_labels_did_leak_which_is_what_v2_fixes` documents the old defect.
- **History preserved.** The revision 1 report stays unchanged on the reports branch (`research/2026-10-31_0908_limit0/`). The v2 run saves to a new folder ending `_v2`. Changes are listed in `RESEARCH_METHOD_CHANGES.md`. Rewriting the cross-section code for speed is checked against the original code, line by line, on data with ties and gaps.
- **Branch.** The code is on the branch `research-v2`, not `main`, so the live app is not redeployed.

### 8.3 Process before the one hold-out run (unchanged, plus one step)

1. **Build and test the hold-out mode.** It is written and tested on synthetic data, then dry-run on development data, where it must reproduce the v2 development numbers.
2. **Tag before running.** The code is tagged `holdout-spec-v1`, and the hold-out mode refuses to run without `--unlock holdout-spec-v1`.
3. **One run, published as is.** It runs once, in GitHub Actions, and the report is saved unchanged.
4. **New: a fixed recipe.** κ, block lengths, seeds, run counts and the eligible dates are written into the code as constants. The run cannot be tuned after the fact.

### 8.4 Disclosures (updated)

1. **The revision 1 leak**, now fixed (8.2).
2. **Revision 1 histogram and parity check** covered hold-out-period scores, though not returns. Now fixed.
3. **Reading the cache.** While preparing revision 2 I read the cache's manifest (last dates) and the stock and coin calendars (dates only). No prices or scores from the hold-out were read.
4. **People's memory of 2025–26 markets** remains. The protection is that every rule is fixed before any hold-out number is calculated.
5. **Survivor bias** applies to the hold-out too (section 6 wording).

### 8.5 Matching the live app

- **Same scoring code:** the scoring code is imported unchanged and pinned at the tag. The claims cover default weights with adaptive mode off, and the score at the daily close.
- **Parity check (changed):** run at 90, 200 and 365 bars of history, the range of the app's slider. Tolerance is 0.5 points at 200 and 365. The run stops if either fails.
- **Short histories:** at 90 bars the 200-day average does not exist yet, so scores may differ. If they do, the claims apply only to users with at least 200 days of history, and the app should say so.

## 9. Power (recalculated)

Power was measured on the same synthetic markets by planting a real effect of known size. The figure is the chance of **Confirmed** (significant and at or above the minimum) for a single test at the loosest (5%) and strictest (1%) Holm cut-offs.

| Test | Planted effect, roughly | Chance of Confirmed at 5% | at 1% |
| --- | --- | --- | --- |
| A1 or A2 | 0.02 (the minimum) | 25–35% | 7–13% |
| A1 or A2 | 0.025–0.027 | 40–60% | 16–21% |
| B | +0.4% per 14 days | 15% | 6% |
| B | +0.9% | 34% | 14% |
| B | +1.4% (about the revision 1 development estimate) | 57% | 29% |
| C | ATR%'s development advantage was large (partial correlation 0.18–0.27) | likely high | to be measured in the v2 development run |

The conclusion from revision 1 stands: two years can probably settle C, but A and B will often come out **Inconclusive** even if they are real. That is why section 10 matters.

## 10. Forward monitoring without inflating false positives (new)

Testing the same claim every six months and acting on the first pass would inflate false alarms badly: with four looks at 5% each, the real rate is roughly 10–15%. The proposal avoids that by **separating looking from deciding**.

- **Data.** New prices from 31 Oct 2026 onwards, the day after the frozen cache ends, go into a new cache that is frozen at each review. No embargo is needed because none of this data has been seen.
- **Six-monthly reviews: descriptive only.** Each review shows the same statistics on the new data, with the running estimate and its 95% interval, labelled "descriptive – not a test". No p-values are shown, and **no product decision may rest on a review**.
- **One confirmatory analysis on a fixed date.** It is run once, after 24 months of new data (about Nov 2028), using the tests, κ, thresholds and Holm family in this spec. Testing only once means no inflation.
- **Any change gets its own spec.** If an earlier decision point is ever wanted, that needs its own spec using a group-sequential design: O'Brien–Fleming-type alpha spending across planned looks, which keeps the overall rate at 5% by demanding very strong evidence early. The boundaries would be fixed before the first look. Reviews already held under the descriptive rule cannot be reclassified as tests after the fact.
- **No pooling.** The hold-out and forward samples are reported separately. Pooling them would be a different test and would need its own spec.

## 11. Decisions for sign-off

**Steps that must happen before the freeze, in order:**

1. **Run the corrected development run** (Research workflow on branch `research-v2`). It uses development data only and takes about an hour in GitHub Actions. It produces the v2 development numbers for A, B and C, the long-only preview, the ATR% *k* values and the parity check at 90, 200 and 365 bars.
2. **Apply the development-stage gate** to A1 and A2 (section 5), and record the numbers here.
3. **Decide on the ATR% calibration** (section 7), using the internal check.
4. **Write and dry-run the hold-out mode** (section 8.3).
5. **Sign off and tag.**

**Choices to confirm** (tick to accept, or write a different answer):

- [ ] **Claim A reworded** to relative timing against other stocks (section 1), with the new statistic (section 2).
- [ ] **Development-stage gate for A:** carry A1 and A2 only if the v2 development estimate at 14 days is in the claimed direction with one-sided p ≤ 0.05.
- [ ] **Claim C tested as a forecast gain** over the 14-day benchmark, minimum +0.02.
- [ ] **Studentised tests with κ = 1.2 (A, C) and 1.0 (B),** t reference, 10,000 draws, block max(20, 2*h*).
- [ ] **Holm at 5%** across whichever primary tests survive the gate.
- [ ] **Minimum effects unchanged:** ±0.02 and +0.50%. Outcome labels as in section 4.
- [ ] **Embargo dates:** stocks from 12 Dec 2024, crypto from 29 Nov 2024.
- [ ] **Crypto gate and costs:** 0.20% per side base, 0.50% stress (Drew may have better figures).
- [ ] **ATR% calibration:** include only if the internal check passes, *k* values to be entered here. Otherwise defer.
- [ ] **Parity check:** must pass at 200 and 365 bars. If 90 bars differs, the claims are limited to users with 200 days or more.
- [ ] **Forward monitoring:** descriptive six-monthly reviews, plus one confirmatory analysis at 24 months.
- [ ] **Sign-off:** Angus and Drew. Record the doc revision and git tag here at freeze.

### 11.1 Development-stage record (v2 run, 31 Oct 2026)

This record comes from the run in reports branch folder `research/2026-10-31_1043_limit0_v2/` (commit 28115fa). The code was branch `research-v2` at 9fbb9ae, on development data only. Each primary statistic is shown at its primary horizon (14 days for A and B, 7 for C) with its 95% interval, one-sided p in the claimed direction, and p against the minimum effect.

| Test | Estimate \[95% CI\] | p | p vs minimum | Development-stage result |
| --- | --- | --- | --- | --- |
| A1 Stretch (+) | −0.003 \[−0.032, +0.025\] | 0.59 | 0.95 | **Fails the gate: dropped** |
| A2 Trend (−) | +0.004 \[−0.029, +0.037\], i.e. points the opposite way | 0.59 | 0.92 | **Fails the gate: dropped** |
| B Crypto Trend spread | +1.50% \[+0.32, +2.67\] | 0.0066 | 0.048 | Goes to the hold-out (not gated) |
| C1 ATR% stocks | +0.069 \[+0.042, +0.096\] | 0.000001 | <0.001 | Goes to the hold-out (not gated) |
| C2 ATR% crypto | +0.011 \[−0.025, +0.046\] | 0.28 | 0.70 | Goes to the hold-out as specified (not gated) |

**The primary family is now B, C1 and C2.** Holm cut-offs: 0.0167, 0.025 and 0.05.

**ATR% calibration internal check: passed.** Coverage from 2022 to the boundary, using *k* fitted on 2016–2021:

| Class | 50% target | 80% target | Final *k* (all development) |
| --- | --- | --- | --- |
| Stocks | 47.8% | 79.3% | k50 = 0.455, k80 = 0.906 |
| Crypto | 50.6% | 80.5% | k50 = 0.390, k80 = 0.863 |

Inclusion still needs sign-off.

**Parity check:** the largest difference was 0.00 points at both 200 and 365 bars, and 4.00 points at 90 bars, so the claims apply to users with 200 or more days of history.

**Note on the C1 lower bound.** The table above gives the **two-sided** 95% interval \[+0.042, +0.096\], using t at 97.5%. The +0.0465 quoted in chat is the **one-sided** 95% lower bound, using t at 95%, which is what the "clearly above the minimum" check uses. Both are correct; the chat summary should have said "one-sided".

## 12. Final specification (revision 3, for sign-off)

### 12.1 Decisions recorded (Angus, 31 Oct 2026)

1. A1 and A2 are dropped, as the development gate requires.
2. The primary hold-out family is **B, C1 and C2**. C2 is kept despite weak development evidence.
3. The ATR% calibration values are frozen as in 11.1 and reported as an exploratory check.
4. Crypto costs are 0.20% per side (base) and 0.50% (stress), and both are disclosed in every report.
5. Validated claims apply only to histories of at least 200 days.
6. Crypto strategy results are always reported against **both** equal weight and Bitcoin bought and held, with turnover and maximum drawdown. **A Confirmed B shows a ranking effect only. It is not evidence of investable outperformance.** Investable outperformance against a benchmark may be claimed only if the 95% interval of the long-only excess return against that benchmark lies above zero. This is descriptive and outside Holm.

### 12.2 The three primary hypotheses

| Test | Null H0 | Alternative H1 (one-sided) | Statistic | Assets, signal dates | Horizon | Block, expected df | κ | Minimum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B | Mean top-third minus bottom-third 14-day return, ranked by Trend points within the 23 coins, ≤ 0 | > 0 | Spread (section 2) | 23 coins, 29 Nov 2024 to 15 Oct 2026 (686 dates) | 14 days | 28, df 24 | 1.0 | +0.50% |
| C1 | Mean over stocks of \[ρ(ATR%, later move size) − ρ(trailing 14-day move size, later move size)\] ≤ 0 | > 0 | Forecast gain (section 2) | 59 stocks, 12 Dec 2024 to 19 Oct 2026 (463 dates) | 7 trading days | 20, df 23 | 1.2 | +0.02 |
| C2 | Same, over coins, ≤ 0 | > 0 | Forecast gain | 23 coins, 29 Nov 2024 to 22 Oct 2026 (693 dates) | 7 days | 20, df 34 | 1.2 | +0.02 |

**Holm:** family α = 0.05. The three one-sided p-values, smallest first, must be at or below 0.0167, 0.025 and 0.05; the first miss stops the procedure.

**Outcomes** (section 4): Confirmed, Confirmed clearly above the minimum, Inconclusive, or Contradicted.

**Frozen settings:** 10,000 bootstrap draws, seed 20261031, and κ, blocks, minimums, dates, costs and *k* exactly as in the code's `HOLDOUT_SPEC`. Its fingerprint (spec hash) is `38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61`, and any change to a value changes the hash.

The last signal dates and counts come from the calendar rule (exit bar ≤ last cache bar). The run reports the actual counts.

### 12.3 Look-ahead and survivorship review (costs, timing, benchmarks, accounting)

| Item | Check | Status |
| --- | --- | --- |
| Scores | Each date's score uses only bars up to that date. Parity was 0.00 points at 200 and 365 bars. The hold-out run also recomputes the development estimates from full-history scoring; any look-ahead in scoring would change them and stop the run. | Confirmed, guarded |
| Rebalance timing | Signal at the close of *t*, trade at the close of *t*+1. Only the price at *t*+1 is needed to trade. The *t*→*t*+1 move is never earned (tested). | Confirmed |
| Holdings and costs | Weights drift daily. Cost = cost per side × traded value, including the first purchase, charged on the trade day. The same code runs the strategy and equal weight. | Confirmed (tested) |
| Equal-weight benchmark | Same coins eligible on each date, same schedule, drift and costs. A strategy holding every coin reproduces it exactly. | Confirmed (tested) |
| Bitcoin benchmark | Bought at the same first trade close, with one purchase cost. Neither it nor the portfolios pay a final sale cost. | Added (tested) |
| Missing prices | A day with no price earns 0; the move is counted when the price returns. Nothing is filled in from the future. | Confirmed |
| Spread statistic (B) | A coin needs a measurable 14-day forward return to enter that day's ranking. That conditions on the coin still trading 15 days later. It is harmless in this universe, where no coin stops trading, but would matter with delistings. The portfolio has no such condition. | Disclosed |
| Survivorship | The universe was fixed in Oct 2026 from coins and stocks that survived. It cannot be removed with free data. Results may be optimistic or unrepresentative, in either direction, and this is stated in every report. | Disclosed, not removable |

### 12.4 The single-run procedure

| Requirement | How it is met | Status |
| --- | --- | --- |
| Fixed code commit | The run is refused unless started from the git tag `holdout-spec-v1`, inside GitHub Actions. The commit is written into the outputs. | Built |
| Frozen configuration | `HOLDOUT_SPEC` holds every number. The run needs the signed-off spec hash typed in, and refuses on a mismatch. | Built |
| Frozen data | The price cache is checked file by file against `price_checksums.lock` (88 files) before anything is read. | Built |
| Reproducible environment | Python 3.12 and exact package versions from `requirements-research.lock`, installed with no extra resolution. Before any hold-out number, the run recomputes the frozen development estimates and stops if they differ by more than 1e-9. | Lock file **pending** (needs the preflight run's package list) |
| Single execution | The run needs the typed confirmation `RUN HOLDOUT holdout-spec-v1`. It is refused if `holdout/holdout-spec-v1/holdout.json` already exists. A run stopped by a guard (parity, reproduction) produces no statistic and is filed separately. | Built |
| Immutable outputs | Every output gets a SHA-256 checksum, shown on the run page and saved with the results. A copy is kept as a run artifact for 90 days. The checksums are to be copied into this doc after the run. | Built. **Recommended:** turn on GitHub tag protection for `holdout-*` so the tag cannot be moved or deleted. Branches are not truly immutable without that. |
| No main-branch change | Everything lives on `research-v2` and in the existing Research workflow, so the live app is not redeployed. | Done |

All 235 tests pass, including 12 new procedure tests:

- refusal without each guard, before any price is loaded;
- the reproduction check catching drift;
- no price used after the label end, and no signal used before the eligible date;
- the embargo dates;
- Holm and outcomes over the three tests;
- both benchmarks;
- Bitcoin entry timing.

### 12.5 Enough independent time blocks?

| Test | Dates | Bootstrap blocks | Non-overlapping horizon windows | Checked at this size? |
| --- | --- | --- | --- | --- |
| B | 686 | 25 (block 28) | about 49 | Yes: synthetic false alarms 5.0% at 5% and 1.0% at 1% at exactly 686 dates and 23 coins |
| C1 | 463 | 24 (block 20) | about 66 | Yes: 3.8% / 1.0% at 457 dates and 59 assets |
| C2 | 693 | 35 (block 20) | about 99 | More dates than checked, so if anything safer |

There are enough blocks for the stated false-alarm rates: the t reference with blocks − 1 degrees of freedom and κ were chosen at these sizes.

What the sample cannot provide is variety of market conditions. Two years is one or two crypto phases, so the results describe that period. The bootstrap reflects variation within the period, not how a different market would behave. Power stays modest for B (section 9).

### 12.6 Crypto concentration diagnostic

This comes from preflight 1 (reports `research/2026-10-31_1122_preflight/`, code 6f0b984), using development data only. It is descriptive and does not change B.

**Concentration.** The edge is broad, not carried by one coin:

- Leaving out any single coin gives a spread between +1.27% and +1.77% (all coins: +1.50%).
- The largest single contribution is 0.40 of the 1.50 points (ETC).
- Leaving out the three largest contributors (ETC, ADA, BNB) gives **+0.97% \[−0.32, +2.25\]**. That is still positive, but the interval now includes zero.

**By market condition,** it is concentrated:

| Period | Spread at 14 days \[95% interval\] |
| --- | --- |
| Bitcoin above its 200-day average | **+2.59% \[+0.83, +4.34\]** |
| Bitcoin below its 200-day average | **+0.26% \[−1.16, +1.68\]** |
| First half of development | +2.30% \[+0.21, +4.39\] |
| Second half of development | +0.69% \[−0.57, +1.95\] |

**By year:**

| Year | Spread at 14 days |
| --- | --- |
| 2018 | +0.52% |
| 2019 | +2.16% |
| 2020 | +3.46% |
| 2021 | +3.06% |
| 2022 | **−1.17%** |
| 2023 | +1.81% |
| 2024 (to Oct) | **−0.08%** |

No single year's interval excludes zero.

**Reading.** The ranking edge has mainly appeared in rising crypto markets and has been weaker since 2022. The hold-out result will depend heavily on which kind of market 2025–26 was. This lowers the realistic power for B below section 9's figures, and it argues against presenting B as a general effect even if it is Confirmed.

**Decision (Angus, 1 Nov 2026).** B stays the primary hypothesis exactly as frozen, with no Bitcoin regime filter and no change to the ranking statistic.

The bull-versus-bear difference is recorded as an **exploratory finding for future independent validation** only. Being significant in one regime (above the 200-day: interval excludes zero) and not in the other (below: interval includes zero) does **not** show that the two regimes differ significantly. That needs a direct test of the difference, which was not pre-specified and is not part of the hold-out.

The year-by-year and regime diagnostics stay in the preflight reports on the reports branch (`preflight.md` and `preflight.json`).

**Dry run** on a pseudo window inside development (signals from 29 Nov 2022 to the boundary). It is a code test on data already seen, not evidence.

- The pipeline ran end to end.
- B: +0.92 \[−0.49, +2.33\], p 0.096, Inconclusive.
- C1: +0.073, p 0.0019, Confirmed clearly above the minimum.
- C2: +0.003, Inconclusive.
- Over that window, Bitcoin held throughout beat the long-only top third by about 42 points a year (+111.6% against +31.9%). This is the kind of result the dual-benchmark rule exists to show.

### 12.7 Remaining blockers before the freeze

**Preflight 1 (code 6f0b984) passed:**

- the frozen development estimates were reproduced exactly (B, C1 and C2 bit for bit);
- parity was 0.00 at 200 and 365 bars (4.00 at 90);
- its price checksums match `price_checksums.lock` for all 88 files;
- its package list is now `requirements-research.lock` (Python 3.12.15, pandas 3.1.0, pandas-ta 0.4.71b0, numpy 2.2.6, scipy 1.18.1).

**Remaining, in order:**

1. **Preflight 2 on the final code** (`research-v2` at ac2373b or later). It is needed because sections 12.8–12.10 added the time-invariance check, the availability audit and the read-time cut, and because the lock file must be proven by installing from it. It must show: an exact reproduction, invariance passed, internal availability drops = 0, and parity at 200 and 365.
2. **You and Drew** review the concentration finding above and sign off section 12 with spec hash `38a5e31d…` (unchanged by this revision).
3. **Turn on tag protection** for `holdout-*` (you, in GitHub settings).
4. **Create the tag** `holdout-spec-v1` on the signed-off commit (me).
5. **The hold-out run,** only on your explicit go-ahead.

### 12.8 Once-only guard, crashes, concurrency and recovery (new)

The guard no longer relies on a finished result file. It keeps a **durable attempt record**, `holdout/attempts.json` on the reports branch:

1. **Data-free checks first.** The locked environment is installed, then the tag and the typed hash are checked. No data is touched yet.
2. **Claim.** The attempt is written to the record and pushed **before any price is read**. The push is a normal one, never forced, so if two runs race, one push is rejected. The loser re-reads the record, sees the winner's attempt and is refused. The job also sits in its own one-at-a-time queue. A test runs this race on a real git remote.
3. **Stages.** As the run progresses it writes each stage to disk at once: `guards_passed → data_loaded → scored → checks_passed → statistics_computed → outputs_written`. Results are printed only after they are saved.
4. **Finish, however the run ends.** A final step (which runs even after a failure) records the last stage reached. If the runner dies so abruptly that this cannot happen, the attempt stays open with stage "unknown", which is treated as possibly exposed.

**Recovery policy:**

| Situation | What is allowed |
| --- | --- |
| No attempt yet | A first run, with the confirmation `RUN HOLDOUT holdout-spec-v1` |
| An attempt reached `outputs_written` | **Nothing, ever.** The hold-out has been run. |
| The latest attempt stopped at any earlier stage (crash, cancelled, failed check, unknown) | **Only an explicit recovery:** a person types `RECOVER HOLDOUT holdout-spec-v1` and the run id of that attempt. It must run from the same tag with the same spec hash, prices and packages. Plain re-runs are refused. |
| 3 attempts already | Nothing without a new signed-off spec |

**Why recovery cannot change the outcome.** Code (tag), configuration (hash), prices (checksums), packages (lock) and random seeds are all fixed, so a recovered run computes the same numbers the crashed run would have. If a recovery needs a *code* fix, that is a new tag and needs your sign-off. Every attempt, its kind and its last stage are copied into the final report.

### 12.9 Observations dropped because a later price is missing (new)

Measured on development prices only (each file cut at the boundary when read):

| Test | Dropped only for a missing later price | At the end of the window | Inside the window |
| --- | --- | --- | --- |
| B (crypto, 14 days) | 347 coin-dates | 345 (the last 15 rows × 23 coins) | 2: AVAX's two stray Yahoo bars on 13–14 Jul 2020, then a 69-day gap before its real listing. AVAX has no score until long after, so neither could enter a ranking. |
| C1 (stocks, 7 days) | 472 | 472 (the last 8 rows × 59) | 0 |
| C2 (crypto, 7 days) | Same calendar as B | End of window only | Same 2 AVAX bars, with no score |

**Conclusion: on development data there is no future-dependent selection.** Every exclusion of a scored observation is the normal end of the window.

The hold-out cannot be checked in advance without reading its prices. Instead, the run's pre-set **availability audit** reports, for each primary test, the end-of-window count and any internal case by date and coin. **No change to the primary test is proposed.** If internal cases appear, they will be reported next to the result, and any adjustment would need your approval as a flagged deviation.

### 12.10 No look-ahead at time T, and preflight isolation (new)

**Score values at time T.** `time_invariance` takes the exact values the three tests use (score, Trend points and ATR%) for every asset at sample dates and recomputes them through the production pipeline twice:

- with the future **removed** (data cut at T);
- with the future **modified** (every later bar reversed and scaled).

All three must match to within 1e-9. It runs in preflight 2 (development dates) and, as a stop condition, in the hold-out run (hold-out dates), before any statistic. A test shows it passes a causal pipeline and catches a deliberately leaky one that uses two future bars.

**Statistics at time T.** Tests show that B, C1 and C2 estimates and p-values are unchanged when prices after the label end, or signals and ATR% before the eligible date, are altered.

**Development numbers.** These are unchanged when every hold-out price or score is altered, and they are rechecked against frozen values in every run.

**Preflight cannot reach hold-out outcomes:**

- The start date is checked from the manifest's last dates, which are metadata only.
- Every price file is cut at 30 Oct 2024 **as it is read**, and the run stops if any later row is in memory.
- A test runs the whole preflight twice, with wildly different hold-out prices, and gets byte-identical output. It also confirms no row on or after the start ever reached scoring.

Preflight 1 used the earlier code, which loaded the full files and cut them immediately. That is still correct, but the read-time cut is stricter.

**Indirect routes, listed for completeness:**

- The price checksums are hashes of whole files and reveal nothing about prices.
- The calendar dates were read to set the embargo (section 8).
- People's memory of 2025–26 markets remains the one route that cannot be closed.

### 12.11 Freeze-readiness report (1 Nov 2026)

**Verdict: ready for your sign-off.** Every technical check has passed. Two GitHub settings (step 3 below) are still to be turned on before the tag is created. Nothing has been frozen, tagged or run on the hold-out.

**Fingerprints**

| Item | Value |
| --- | --- |
| Code commit to tag | `ac2373b71efc18fab163f8695aef7a63c474ad7f` (branch `research-v2`) |
| Spec fingerprint (`HOLDOUT_SPEC` hash) | `38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61` |
| Package lock, SHA-256 of `requirements-research.lock` (75 packages, Python 3.12.15) | `ebde66466f0a441a69f333ae181c3b41714fd01d206ffb2589abf8a204f93e10` |
| Price checksum list, SHA-256 of `price_checksums.lock` (88 files) | `a65419a19d002705ae8507392c1e1724dbdcf8b0a760f907d56c3f909bc8fdac` |

**Preflight 2** (reports `research/2026-11-01_0402_preflight/`, development data only):

| Check | Result |
| --- | --- |
| Prices | All 88 checksums computed in GitHub Actions match the lock. The checksum file itself is byte-identical (same SHA-256 as above). |
| Environment | Installed from the lock. The installed package list is identical to it (75 of 75), on Python 3.12.15. |
| Reproduction | B 1.4972999540605965, C1 0.06925556922726794, C2 0.010590860392287885: **exact matches** with the frozen values. |
| Parity | 0.00 points at 200 and 365 bars (48 days each); 4.00 at 90 bars, which is why the claims are limited to 200 or more days. |
| No look-ahead (time check) | 344 asset-dates, every asset in the universe. Largest difference is 0 for score, Trend points and ATR%. **Passed.** |
| Missing-future-price audit | B 345, C1 472 and C2 184 dropped at the end of the window (23×15, 59×8, 23×8), **0 internal** |
| Determinism | Dry run and concentration diagnostic are identical to preflight 1 |

The preflight did not write its own commit into its output (the hold-out run does). It ran on `research-v2`, whose head has been ac2373b since 31 Oct with no later commit, and its results match that code exactly.

**The time check, precisely.** For every asset in the universe, `time_invariance` picks 4 dates *T* spread evenly over the period checked: development dates from 30 Oct 2022 in the preflight, hold-out dates in the real run. At each one it takes the three values the tests use, as the run stored them: the score, the Trend points and ATR%. Those were computed with indicators on the whole price history and the score read from rows up to *T*. It then recomputes them twice through the same production code:

1. **Future removed:** the price history is cut at *T*.
2. **Future changed:** every bar after *T* has its prices reversed in order and multiplied by 3, and its volume reversed and multiplied by 5.

The check passes only if all three values agree with the stored ones to within 1e-9 in both versions, on every date and asset (a missing value must stay missing). In the hold-out run, failure stops the run before any statistic is calculated.

**Every attempt is permanently recorded and disclosed:**

- **One record, only ever added to.** Each attempt is written to `holdout/attempts.json` on the reports branch before any price is read. No step deletes or rewrites an entry; later steps only fill in its last stage.
- **Every attempt keeps its outputs.** They go to `holdout/attempts/<run id>/` with checksums, or `holdout/holdout-spec-v1/` for the completed one. That covers stopped, crashed and recovered attempts alike, together with the stage log and a copy of the full attempt record.
- **Gaps in the record count against us.** An attempt whose final record could not be written stays open as "unknown" and is treated as possibly exposed.
- **Runs refused before the claim leave no record,** and they read no data. Their GitHub run log still exists for 90 days.
- **The published result** will list every attempt, its kind and its last stage.
- **Permanence depends on GitHub settings.** Code cannot stop a repository admin from force-pushing the branch or moving the tag, so permanence needs **branch protection on `reports`** (no force-push, no deletion) and **tag protection on `holdout-*`**.

**Remaining limitations that could change how the results are read:**

1. **Survivor bias.** The universe was chosen in Oct 2026 from survivors. Results may be optimistic or unrepresentative, in either direction.
2. **One short window.** Two years covers one or two market phases. B's development edge came mainly when Bitcoin was above its 200-day average and weakened from 2022. That is exploratory, and a regime difference has not been shown statistically. B's realistic power is low.
3. **C2 will probably be Inconclusive** (development gain +0.011, p 0.28). It stays in by your decision, at a small cost to Holm.
4. **A Confirmed B is a ranking effect, not investable outperformance.** In the 2022–24 dry run, Bitcoin held throughout beat the long-only top third by about 42 points a year.
5. **Synthetic calibration.** The inflation factor κ was chosen on synthetic markets. It held on a harsher variant, but real markets could differ.
6. **Scope of the claims:** default weights, adaptive mode off, the score at the daily close, and at least 200 days of history. The live app's intraday score and 90-day setting are not covered.
7. **Data.** These are free Yahoo adjusted prices. The cache is frozen, but the live app sees later revisions.
8. **Human memory** of 2025–26 markets cannot be removed. Every rule was fixed beforehand.
9. **Exploratory results.** Many are reported, without p-values. None can confirm a claim.

**Steps to the run, in order:**

1. **You and Drew** sign off this section, including the spec hash.
2. **You** turn on branch protection for `reports` and tag protection for `holdout-*` in GitHub settings.
3. **I** create the tag `holdout-spec-v1` on ac2373b, once you say so.
4. **You** start the hold-out from the tag, with the confirmation and hash. Only on your explicit go-ahead.

### 12.12 Sign-off record

|  |  |
| --- | --- |
| **Owner (Angus)** | **Approved** on 1 Nov 2026, 11:18 (UTC+7): section 12, spec fingerprint `38a5e31dc44358e64c625e4c11ff66765bce5c17d088843bf27090226d03ab61`, code commit `ac2373b71efc18fab163f8695aef7a63c474ad7f`. Accepts the primary hypotheses, decision thresholds, exploratory-only diagnostics and limitations. |
| **Independent review (Drew)** | **Not given.** Drew was unavailable and has not independently reviewed or approved this specification. Sign-off is owner-only. |
| **Durable record** | `governance/holdout-spec-v1-signoff.md` on the protected `reports` branch (commit 1903b35) |
| **Protections** | Both verified active via the GitHub API. Ruleset 26300334 on `reports`: no deletion, no force-push. Ruleset 26300455 on `holdout-*` tags: no deletion, no force-push, no update; creation allowed. |
| **Tag** | Not created yet; waits for the owner's explicit approval |
| **Hold-out run** | Not run; waits for the owner's explicit approval after the tag |

## 13. Hold-out result (single run, 1 Nov 2026)

**C1 is Confirmed: ATR% ranks how big stock moves will be over the next 7 trading days better than recent volatility does.** B and C2 are Inconclusive, and nothing is Contradicted.

The run was GitHub Actions run 41273694276, the first and only attempt. It ran from tag `holdout-spec-v1` (commit ac2373b), spec hash `38a5e31d…`, with the locked environment (identical to the lock), between 04:36 and 04:39 UTC. Results are in reports `holdout/holdout-spec-v1/` (commit af4af75), and all output checksums verify.

**Checks before any statistic was calculated (all passed):**

| Check | Result |
| --- | --- |
| Reproduction of development estimates | Exact for B, C1 and C2 |
| No look-ahead (time check) | 344 asset-dates; largest difference 0 for score, Trend points and ATR% |
| Parity, all 86 assets, 1,032 hold-out days | 0.00 points at 200 and 365 bars. At 90 bars, 9.0 points, which confirms the limit to 200 days or more. |
| Missing-future-price audit | End of window only: B 345, C1 472, C2 184. **Internal: 0.** |

**Primary tests** (Holm, family 5%):

| Test | Estimate \[95% CI\] | One-sided 95% bound | p | p vs minimum | Holm | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| C1 ATR% stocks | **+0.064 \[+0.010, +0.118\]** | +0.0196 | **0.0107** | 0.051 | pass (≤ 0.0167) | **Confirmed** |
| B Crypto Trend ranking | +1.46% \[−1.19, +4.12\] | −0.74 | 0.133 | 0.23 | fail (> 0.025) | **Inconclusive** |
| C2 ATR% crypto | +0.043 \[−0.047, +0.132\] | −0.032 | 0.171 | 0.31 | fail | **Inconclusive** |

**Reading:**

- **C1** cleared Holm at its first step. Its estimate (+0.064) is close to development (+0.069). It just misses "clearly above the minimum": the one-sided bound is +0.0196 against the 0.02 threshold.
- **B's** point estimate, +1.46% per 14 days, is almost identical to development (+1.50%) and above the +0.50% minimum. But it is not distinguishable from zero over two years: as section 9 warned, power was low. **This is not evidence against B, and it is not evidence for it.**
- **C2** is Inconclusive, as expected.

**Exploratory: long-only crypto.** This is not a test, and a ranking effect is not investable proof. The period was a falling market for crypto:

| Costs per side | Top third (a year, max drawdown) | All coins equally (a year, max drawdown) | Bitcoin held (a year, max drawdown) | Excess over equal weight \[95%\] | Excess over Bitcoin \[95%\] |
| --- | --- | --- | --- | --- | --- |
| 0.20% | −15.6%, −63% | −32.5%, −64% | −13.5%, −53% | +20.1 \[−19.6, +66.1\] | +6.6 \[−57.1, +79.8\] |
| 0.50% | −22.0%, −65% | −32.9%, −65% | −13.5%, −53% | +12.8 \[−27.3, +58.9\] | −1.3 \[−65.2, +71.9\] |

One-way turnover was 13.2 times a year. Every interval includes zero, so **no investable outperformance is demonstrated** against either benchmark (decision 6). The top third lost less than equal weight but still lost money. The excess figures are averages of daily differences, so they do not equal the gap between the yearly returns.

**Exploratory: expected-move calibration** with the frozen *k* (targets 50% / 80%):

- Stocks: 49.8% / 80.5%.
- Crypto: 51.3% / 84.0%, within the ±5-point tolerance. The 80% crypto range was a little wide.

**Implementation note (disclosed, no effect on outcomes).** For C1 and C2 the bootstrap counted the last 8 dates of the window, which have no measurable 7-day move, as empty rows. That is why the reported dates are 471 and 701 rather than the 463 and 693 in section 12.2, and why C2 has 35 degrees of freedom rather than 34. The estimates are unaffected. The extra rows slightly change the standard error, by much less than the +8% that would have been needed to push C1's p above 0.0167. The same code was used for development and was frozen by the spec hash. Recomputing without them would mean re-analysing the hold-out, so it was not done.

**What this supports, for discussion with Drew (no product change has been made):**

- **Supported:** showing ATR% for stocks as a measure of *how much* a stock is likely to move, never which way, for users with 200 or more days of history. The calibrated stock ranges also held up (exploratory).
- **Not supported:** any claim that the score, the Trend ranking or ATR% for crypto predicts outcomes. The score popup's honest note stays.
- **For future independent data:** B's ranking effect and its apparent dependence on market conditions, through the descriptive forward monitoring in section 10.

Drew's independent review of the specification is still not given.
