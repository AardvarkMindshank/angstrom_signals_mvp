# Library completion (step 1): report

Branch `feature/library-completion`, built on main `17add16`. Implements `docs/design/library_completion.md`,
revision 2. **Not merged and not deployed.** No builder or strategy work has been started.

## What was built

**Ten component signals** (`signal_library/signals_components.py`): `ma.position`, `ichimoku.position`,
`macd.level`, `macd.acceleration`, `move.seven_day`, `rsi.level`, `stochastic.level`, `bollinger.position`,
`obv.balance`, `volume.heavy_candle`. Each signal:
- reports its native measurement, plus `standard_score` as one field inside its value;
- takes `standard_score` from `signals_v2`'s own component function. `signals_v2._components` was split into ten
  functions; the new signals and v2 both call them;
- works on all timeframes. Outside 1D its notes say "daily-derived scaling (not calibrated for this timeframe)";
- leaves the `SignalResult` structure and every existing signal's output unchanged.

**Starter Groups** `starter:trend`, `starter:stretch` and `starter:flow` (lineage version 3):
- the cluster's components as equal-weight score members, read through `clip` on `standard_score`;
- excluded when unavailable;
- minimum coverage of 1 of n;
- question and meaning taken from `signals_v2.CLUSTERS`.

The `clip` transform now applies the −1..+1 identity exactly (no floating-point round trip). This changes no
existing Group: none uses that range.

**Sentiment** (`signal_library/signals_sentiment.py`):
- **`sentiment.market`:** subjects `market:crypto` and `market:stocks`, via a scope that accepts either.
- **`sentiment.asset`:** any watchlist asset.
- **What they report:** the score on −100..+100, coverage and the thin-news flag, the model, and the 7-day change
  and staleness (36 hours), both measured from the evaluation time.
- **Missing is not neutral:** no observation is `missing_data`, never 0.
- **Replays** count a row only from `first_seen_at`, the database receipt time, never from `recorded_at`. Until
  `sql/2026-11-05_sentiment_first_seen.sql` is run, sentiment replays report that sentiment is live only.

**Lineage v3** adds the new signals (roots: price; price and volume; news_sentiment). Groups and Sets pinned to
v2 still validate and evaluate (tested).

**Other changes:**
- The signal catalogue was regenerated; every existing entry is unchanged.
- The admin inspectors and the Analysis card can read sentiment.

## Legacy authority: no change to production readings

- Splitting `signals_v2._components` was checked against the pre-split code on 90 frames: outputs are
  byte-identical, key order included.
- The live golden snapshot (every result captured before this work) is unchanged.
- The overlap and smoke checks in CI pass.
- The guard test still forbids `signals_v2`, scoring, alerts, evidence, digest and the Signal Matrix from
  importing the library.

## Parity (identical inputs)

**CI**, with real indicators, on synthetic crypto, a synthetic share and frozen development data (BTC-USD,
SOL-USD, AAPL, JPM), at about 60 cutoffs each: **1,143 comparisons, 0 differences.** Every comparison checks:
- the value within 1e-9;
- an identical displayed −100..+100 percent;
- identical coverage;
- identical missing-data behaviour.

**Local tests** add:
- short histories (16–90 bars, no SMA 200 or Ichimoku);
- no volume, no ATR, and gaps on the last bar;
- crafted half-percent boundaries;
- 20,000 random component combinations: no displayed-percent differences.

**Live parity is not claimed.** The dashboard reads the stored daily bars and closes shares at 16:30 New York;
the library reads Yahoo through the chart loader and closes shares at 16:00. Unifying the sources is a separate
task, required before any library reading replaces a production reading.

## Certification (CI, suite v1, 12 datasets, at least 50 cutoffs per dataset)

**110 of 113 signal/timeframe pairs certified:**
- every new component signal on all five timeframes;
- both sentiment signals (1D);
- all existing signals, as before.

**The three not certified are the derivatives signals** (live only, decision E): unchanged.

Sentiment certification used synthetic histories only, with gaps and thin-news days. Each cutoff was poisoned with
one of three cases:
- late imports: recorded before T, received after T;
- scores recorded after T;
- rows received after T.

None changed a result.

**Slice shortcut (whole-history indicators):** not equivalent, so those pairs keep the exact path, for:
- the standard scores of Bollinger, MA, MACD and RSI (differences of about 1e-12 to 1e-16 from indicator
  warm-up);
- the raw OBV level, which depends on where the history starts. The OBV *balance* is not affected, because it
  subtracts the average;
- weekly MACD early in the data.

The exact path is always correct; the shortcut is used only where certified.

## Tests and CI

- **New:** `tests/test_library_completion.py` with 14 tests: legacy authority, the ten signals, lineage
  compatibility, parity, boundaries, the real-indicator parity test (CI), the starter definitions, sentiment
  behaviour, replay receipt time, the certification suite with backfill poisoning, the catalogue and the SQL.
- **CI** gained a required step: Trend/Stretch/Flow parity with real indicators and development data.
- **Full suite:** 685 tests pass in CI; 638 pass locally.
- **Final CI** on commit `10cdf85`: all four jobs pass. That means 685 tests, the committed certification
  record matching the code (110 of 113), parity with 0 differences, and the replay shortcuts still equal to the
  exact path.

## Exceptions and follow-ups

- **Derivatives** stay live only (decision E: investigating stored history is a separate task).
- **Sentiment replays** need the SQL file run first. The history begins on 3 Nov 2026, inside the hold-out
  period, so research has no sentiment data.
- **Live-source unification** (decision C) is outstanding, as above.
- **For you to run after the merge, in Supabase:**
  - `sql/2026-11-05_sentiment_first_seen.sql`;
  - `sql/2026-11-04_signal_groups_starters.sql` again, which adds the three new starters to the database and is
    safe to re-run.

## Ready for review

Step 1 is complete. Waiting for approval before merging. After the merge, the two SQL files above should be run.
