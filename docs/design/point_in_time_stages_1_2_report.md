# Point-in-time evaluation: Stages 1 and 2 report

Branch `feature/replay-foundation`, head `616bc97`, on top of the accepted design note
(`docs/design/point_in_time.md`, revision 2, with implementation notes in §11). **Not merged and not deployed.**
Stages 3–5 have not been started.

All four CI jobs pass on `616bc97` (tests, chart, overlap and the new replay job).

## Stage 1: replay foundation

**Replay context** (`signal_library/replay.py`). A DataContext at time T inside a ReplayRun:
- **Candles:** only candles closed by T are used, inside the window the live app loads (range plus 260 warm-up
  candles, capped at 4,000, with fewer than 6 candles in the range refused, as the live loader does). The candle
  containing T is dropped.
- **Stored flows:** only rows first seen by T, inside the live 120-day window. Backfilled rows are never used, and
  `point_in_time=true` is required.
- **Derivatives:** always `not_replayable`.

**Timestamp invariant.** Every market-data timestamp anywhere in a result must be at or before T:
- this covers `observed_at`, `available_at`, and every timestamp in values, events, levels and evidence;
- otherwise the result becomes an error ("Replay integrity: … is after the cutoff");
- administrative times are exempt and labelled as such: `computed_at`, and `administrative.run_started_at` in the
  record.

**Engine hooks** (`engine.py`). These are only active for replay contexts; live contexts take the unchanged path:
- the certification gate (`permit`);
- a private per-run cache, so the shared live cache is never read or written;
- `verify`;
- signal bookkeeping.

**Certification gate** (`signal_library/certification.py`). The committed record `certification.json` counts
only when its code hash matches the current code (11 files). Otherwise nothing is certified. Uncertified signals
return `not_replayable` with the reason.

**Source quality** is recorded on every input: `reconstructed` for crypto, `reconstructed_with_limitations` for
shares (with the limitation text), `point_in_time` for flows, `unavailable` for derivatives.

**Reproducibility record** (`ReplayRun.record()`):
- mode and cutoffs;
- code: Git commit and replay code hash;
- environment: Python, pandas, numpy and pandas_ta versions, plus the lock-file hash;
- dataset;
- every input, with its source, window and SHA-256 of the exact cut data;
- every signal, with its parameters and the certification it ran under.

**Display entry** (`replay_display.py`):
- reads current providers (the chart's loader, without the forming candle);
- reads flows through an as-of query (`fetched_at <= T`, not backfilled);
- is capped at 90 steps;
- has no writing, export or statistics code.

**Research entry** (`replay_research.py`):
- reads only the frozen research price cache;
- reads and parses each file whole, then filters out rows dated on or after 2024-10-30 before returning the data,
  so they never reach signal evaluation (the rows are read from the file, but excluded before any use);
- refuses any T on or after 2024-10-30 before touching data;
- refuses any source other than the frozen dataset;
- records the dataset (reports-branch location and commit, manifest hash, SHA-256 of every file read).

`accept(record)` is the gate for statistics. It refuses display records, records without a frozen dataset, and
records with any cutoff in the hold-out.

## Stage 2: certification suite

`signal_library/certify.py`, run by `replay_certify.py` in a new required CI job. Each signal and timeframe is
tested on every dataset that has it, at 50 or more cutoffs per dataset:

1. **Independent truncated reference.**
   - A separate process, a fresh DataContext and empty caches.
   - The raw candles are cut at T by a separate loop implementation before indicators are computed; the worker
     only ever receives cut data.
   - It is compared with the replay result as complete canonical JSON (only `computed_at` is excluded).
2. **Future-data poisoning.** Two variants per cutoff, rotating through noise, spikes, deleted rows, inserted rows
   and ×1000 volume. Flows use later revisions, late first sightings and later backfills.
3. **Cache isolation.**
   - A run warmed with later cutoffs.
   - A run after the shared live cache was filled.
   - The shared cache must not change size.
   - The clean run also visits the cutoffs in shuffled order, so state carried between evaluations shows up.
4. **Timestamp invariant**, on every result.
5. **Boundary cutoffs:**
   - exact candle closes, one second before and after, and runs of consecutive closes;
   - weekends and New York session opens;
   - daylight-saving changes;
   - times around swing confirmations, divergence confirmation and expiry, and structure breaks found in the data.
6. **Slice-equivalence** is certified separately (indicators computed once on the whole history, then sliced,
   compared with the reference).

A signal is certified only with zero failures, at least 50 cutoffs on every dataset, and at least one real
reading (results that are always "insufficient data" do not count).

**Datasets:**
- synthetic 15-minute crypto bars (500 days), grouped like the chart;
- synthetic New York session share bars (357 sessions, crossing daylight-saving changes);
- synthetic stored ETF flows and stablecoin supply (with revisions and a backfill);
- frozen development daily data for BTC-USD, SOL-USD, AAPL and JPM, before 2024-10-30.

The hold-out is not read anywhere.

**Mutation checks.** These prove the suite refuses leaks, and run locally and in CI:
- a signal that keeps memory between calls: refused;
- a signal that reports a timestamp after T: refused;
- an honest signal: certified;
- a non-causal (centred) indicator: the signal stays certified on the exact path, but is refused for the slice
  shortcut.

## Certification results (CI, real indicators, about 8 minutes, 51,150 checks)

- **58 of 61 signal/timeframe pairs certified.** Every candle signal on all five timeframes, plus both flow
  signals (1D).
- **Not certified (3): the derivatives signals** (open interest, liquidations, liquidation levels). They are not
  failures: there is no stored history, so they are live only (decision E).
- **No algorithm failed the leak tests.** The first CI run reported one failure on multi-timeframe alignment. It
  was a harness artefact: a poisoned run reported a missing timeframe with different wording. The harness was
  fixed, and the signal passed.
- **Slice shortcut:** equivalent for every certified candle signal except **RSI divergence on 1D**. On real AAPL
  data, RSI computed on the whole history moves one pivot by a day compared with the cut data. It is certified
  for the exact path only, so the shortcut is not used for it.
  - Flow signals have no slice path: they are not tested for it, and the shortcut is not used.

## Tests

- **18 new replay tests.** They cover:
  - the cut-at-T window;
  - derivatives and non-point-in-time flows being refused;
  - flow row rules;
  - the certification gate and its code hash;
  - the timestamp invariant;
  - the shared-cache isolation;
  - the step cap and the record;
  - research cut-off, refusals and `accept`;
  - the module separation guard;
  - the mutation checks;
  - flow certification;
  - that poisoning only changes data after T.
- **Live results unchanged.** A golden snapshot of every live signal, both starters and the example Set, taken
  before this work, is compared byte for byte.
- **Full suite:** 652 passed in CI; 607 passed and 10 skipped locally, where Streamlit and Postgres are
  unavailable.

## Resource measurements (CI, real indicators)

Each replay step runs every 1D candle signal, including multi-timeframe alignment, which loads all five
timeframes.

| Dataset | Steps | Exact path | Slice shortcut | Peak Python memory (exact / slice) |
|---|---|---|---|---|
| Synthetic crypto | 30 | 3.6 s (0.12 s/step) | 1.8 s | 6 / 24 MB |
| Synthetic crypto | 365 | 35 s (0.10 s/step) | 17 s | 21 / 42 MB |
| BTC-USD (development) | 365 | 26 s (0.07 s/step) | 21 s | 20 / 22 MB |
| AAPL (development) | 365 | 23 s (0.06 s/step) | 19 s | 18 / 20 MB |

- Process memory growth stayed under 40 MB in every run.
- A 90-step display replay is roughly 6–11 seconds on these machines; Render's CPU is slower.
- Long research replays belong in CI or one-off jobs, as designed.

## Deviations and additions (all recorded in §11 of the design note)

- The candle containing T is dropped rather than marked forming.
- Research data is daily only (1D, with 1W grouped from it). The research share prices are split- and
  dividend-adjusted, and their limitation text says so.
- Intraday timeframes and flow signals are certified on synthetic data only, because all real intraday and stored
  flow data falls inside the hold-out period.
- The reference shares `chart_data.candle_end` (the definition of a candle close) with the replay path. Everything
  else in it is independent.
- `not_replayable` is a new result status, used only in replays.
- Certification is tied to a code hash: changing any of the 11 files requires re-running the suite and committing
  its record. CI enforces this.

## Ready for review

Stages 1–2 are complete. Merging would change nothing users see:
- no UI uses replay yet;
- live evaluation is proven unchanged;
- Render only loads the new modules, not the CI suite.

Waiting for approval before merging, and before Stages 3–5 (Groups/Sets integration, the admin "as of" inspector,
Set-level benchmarks).
