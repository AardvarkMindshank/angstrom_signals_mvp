# Point-in-time evaluation ("replay"): design note

Status: draft for review, revision 2 (4 Nov 2026). Nothing here is built yet.

**Changes from revision 1** (review of 4 Nov):
- Replays are called **as-of reconstructions**, not reproductions (§2).
- Certification now uses an independent truncated path, future-data poisoning tests and cache checks (§4.1).
- Algorithm certification is kept separate from data-source quality (§4.2), and whole-frame slicing has its own
  certification (§4.3).
- Results carry a completeness level per evaluation (§5), and coverage labels have four levels (§5.2).
- The hold-out is enforced by data absence and separated code paths, not by a label alone (§6).
- Every replay result carries a reproducibility record (§7).
- Speed claims are only made after measuring the real path (§8).
- Decisions A–E are recorded as reviewed (§10).

## 1. What this is for

Today every Signal Library signal, Group and Set is worked out for **now** only. Groups and Sets refuse any other
date on purpose: not every signal and cache can yet be trusted to ignore data that arrived later.

Point-in-time evaluation answers: **"what does this signal, Group or Set say at time T, using only inputs
knowable at T?"** Everything historical depends on it:
- a Signal matrix built from Groups;
- evidence views;
- the later Strategy builder and Research/Evaluate tests (Drew's TradingView strategy; "does Coinbase's share
  price lead Bitcoin?").

This note covers the foundation only. The dashboard, Trend, Stretch, Flow, alerts and the Signal matrix stay
exactly as they are. There are **no research statistics, strategy optimisation or hold-out evaluation** in this
work.

## 2. The rule, and what a replay is

A replayed result at time **T** may use only:
- candles whose **close time is at or before T**;
- stored observations whose **first-seen time is at or before T**, using the value known at T and never a later
  revision.

Every result carries `available_at`, the time it could first have been known. In a replay, **`available_at <= T`
must hold for the result and for every nested event, level and evidence item.** A breach is an error, never a
value.

**As-of reconstruction, not reproduction.** A replay runs the **current** signal algorithms, with their normal
live lookback windows (for example one year of daily candles), on inputs cut off at T. It is *not* a claim about
what the app actually displayed at T. Exact reproduction would also need:
- the code and configuration in use at T;
- the provider's data exactly as published at T, before later corrections;
- data that may simply no longer exist.

The app and documents call these results "reconstructed as of T".

## 3. How each kind of data is handled

| Data | Replay handling | Source quality (§4.2) |
|---|---|---|
| **Candles** (all technical signals) | Keep only candles closed by T. Recompute which candle is forming relative to T (the existing `chart_data.mark_forming(now=T)`). Apply the live lookback window. Shares use their exchange session close; crypto uses UTC. | Crypto: `reconstructed`. Shares: `reconstructed_with_limitations` (split-adjusted). |
| **Multi-timeframe** (`mtf.alignment`) | Each timeframe is cut separately at T. A weekly candle still open at T is excluded, as live. | Same as candles. |
| **Stored flows** (Bitcoin ETF flows, stablecoin supply) | `daily_values(as_of=T, point_in_time=True)`: the revision first seen by T; backfilled rows dropped. Replays always force `point_in_time=True`. | `point_in_time` from the first stored sighting; nothing before it. |
| **Derivatives** (open interest, liquidations, levels) | None. About 7 days are stored and overwritten hourly. | `unavailable` (live only). |
| **Sentiment** (later) | The first-seen rule, as flows. | Decided when added. |

**Split-adjusted prices (decision C).** Yahoo's share history is adjusted for splits, so historical price levels,
and indicators derived from them, can differ from what traders saw at T. This is accepted **for descriptive
replay only**, recorded as a limitation on every affected result, and never treated as strict point-in-time data.

**Intraday history limits.** Yahoo gives about 60 days of 15-minute candles and about 2 years of 1-hour candles.
Replays before that return "insufficient history". They never fall back to another timeframe.

## 4. Certification

### 4.1 Algorithm certification: proving a signal does not use the future

Each signal version gets an **algorithm status** per timeframe: `certified`, or `not_certified` with a reason.
Only certified signals run in a replay; the others return unavailable with reason `not_replayable`.

Certification runs automatically in CI on every change. The tests use **synthetic data and development data
dated before 2024-10-30 only**; the protected hold-out is never used (§6). A signal is certified only when all of
the following pass, for every supported timeframe, on at least 50 cut points per dataset:

1. **Independent truncated reference.** The reference result comes from a **separate execution path**:
   - raw OHLCV (or raw stored rows) are physically cut at T *before* any indicator is computed;
   - a fresh DataContext and an empty cache are used;
   - it runs in a separate process, so nothing in memory is shared.

   The replay path's result must equal it exactly, compared as complete canonical JSON: status, value, every
   nested event and its state, levels, evidence and all timestamps.
2. **Future-data poisoning.** Data **strictly after T** is altered in several ways:
   - random noise;
   - extreme spikes;
   - added and deleted candles;
   - shifted volumes;
   - for flows, later revisions and late first sightings.

   The result at T must not change in any field.
3. **Cache isolation.** The same cut point is evaluated cold, after a warm cache filled by evaluations at later
   times, and after the shared live cache has been filled. All results must be identical.
4. **Timestamp invariant.** Every timestamp anywhere in the result is at or before T.
5. **Boundaries.** Cut points include:
   - exactly at a candle close and one second before it;
   - weekends;
   - share session opens and closes;
   - daylight-saving changes;
   - the first T with enough history;
   - Ts on either side of swing confirmations, regime-change confirmations and divergence expiry.

Expected sensitive cases:
- swing points need `right` candles to confirm;
- the regime state must hold for N candles;
- divergences expire after 30 candles;
- long-memory indicators depend on where their history starts.

A failing signal is fixed or stays `not_certified`. Certification is recorded per signal **version**, so changing
a signal requires re-certifying it.

### 4.2 Data-source quality, kept separate

An algorithm can be replay-safe while a provider's history is not. Each data source therefore has its own
**source quality**, with the date range it applies to:

| Source quality | Meaning |
|---|---|
| `point_in_time` | Values as first known, with first-seen times (our stored flows). |
| `reconstructed` | Today's copy of historical data, believed not to be materially revised (crypto candles). |
| `reconstructed_with_limitations` | Today's copy with known revisions (split-adjusted share prices). The limitation text travels with every result. |
| `unavailable` | No honest history (derivatives today). |

A replay of a signal at T is allowed only when **algorithm = certified** and the **source has history covering T**.
Its result carries both facts.

### 4.3 Whole-frame computation is a separate certification

Computing indicators once on the full frame and slicing per T is faster, but it is only allowed for a signal that
separately passes the **slice-equivalence** test: sliced results must equal the independent truncated reference
(§4.1, test 1). That test also runs under poisoning. Signals without it recompute on the truncated data at every
T. Correctness never depends on the shortcut.

## 5. Groups and Sets

- `evaluate_group` and `evaluate_set` accept `data_mode="point_in_time"` with `as_of=T`. **Live mode results are
  unchanged byte for byte** (tested against the current starters).
- Members whose signal is not certified, or whose source has no history at T, are unavailable with reason
  `not_replayable` or `no_history_at_T`. The existing coverage, exclude/neutral and three-valued condition rules
  then apply unchanged (decision B).

### 5.1 Completeness of each replayed result

Every replayed Group result carries a **completeness** field:
- `complete`: every member is replayable at T.
- `partial`: one or more members are not replayable at T. The result lists them and what they affect: the score's
  coverage, which conditions became unknown, and which vetoes became unknown.
- `limited`: everything is replayable, but at least one source is `reconstructed_with_limitations`. The
  limitation text is attached.

A result can be both partial and limited.

**Rule:** a replayed Group whose veto is unknown, or whose confirmation is unknown because of a non-replayable
member, is never shown or exported unqualified:
- its status is already `veto_unknown` for vetoes;
- unknown confirmations are listed;
- completeness `partial` is shown next to every score.

A Set reports the completeness of each Group and its own worst case.

### 5.2 Coverage labels

A single start date is not enough. Each Group and Set gets a computed **coverage profile**: date ranges, each with
one of four levels:

| Level | Meaning |
|---|---|
| **Replayable** | All members certified, all sources `point_in_time` or `reconstructed`. |
| **Reconstructed with limitations** | Complete, but a source carries a limitation (for example split-adjusted prices). |
| **Partially evaluable** | Some members are missing; lists which, and whether a veto or confirmation depends on them. |
| **Live only** | Not replayable at all (for example a Group built only on derivatives). |

Example:
- 2019-01 → 2026-08-13: partially evaluable (Bitcoin ETF flows missing; the "flow-backed" confirmation becomes
  unknown);
- 2026-08-14 → now: replayable.

Members used by a veto, or needed for the score's minimum coverage, are marked **critical**. If a critical member
is missing, the whole range is labelled partially evaluable, never replayable. The profile is computed from
certification records and source ranges, never typed by hand.

## 6. Protecting the hold-out

The validation spec fixes the hold-out start at **2024-10-30** (`research.HOLDOUT_START`, tag
`holdout-spec-v1`). It is protected by design, not only by a label:

1. **Research data excludes it.** Research-mode replays read only the frozen, versioned development dataset:
   - its manifest lists every file with a SHA-256 hash and the cut-off rule;
   - rows on or after 2024-10-30 are removed when the data is read, as the existing overlap checks already do;
   - each file is read and parsed whole, and its hold-out rows are filtered out immediately, before the data is
     returned: they never reach signal evaluation, statistics or caches (clarified after the stage 1–2 review: the
     rows are read from the file, but excluded before any use).
2. **Research mode refuses later dates.** Any request with T on or after 2024-10-30 is refused before data is
   touched. This is tested.
3. **Separate code paths.**
   - Display replays live in the app's display module and never write results anywhere that statistics are
     computed.
   - Research and statistics modules are refused display results: every replay result carries its mode, and
     the research entry points reject anything not marked `research` and not built from the frozen manifest.
   - A guard test, like the existing ones for readings and alerts, fails CI if a research or statistics module
     imports the display replay path.
4. **No tuning on display output.** Display replays (charts, recent-days views, the admin inspector) are not
   saved to research records, not exported in bulk, and offer no statistics or parameter search. Parameter
   choice and optimisation happen only in research mode.
5. **Certification uses no hold-out.** Certification datasets are synthetic, or development data before
   2024-10-30 (§4.1).

The hold-out itself stays untouched: no evaluation, statistic, test or certification in this work uses it.

## 7. Reproducibility record

Every replayed result carries a **replay record**:
- **Mode:** `display` or `research`.
- **Cutoff T,** and the time the replay was run.
- **Code:** Git commit, Signal Library version, lineage table version.
- **Every signal instance:** id, version, timeframe, parameters, instance key, algorithm certification
  reference.
- **For a Group or Set:** config id, version and `content_sha256`.
- **Data, per source:**
  - its identity and quality level;
  - for research, the frozen dataset version and file hashes;
  - for display, the provider, fetch time and a hash of the exact cut inputs used.
- **Completeness and limitations** (§5.1).

Research results are exactly repeatable from this record. Display results from live providers are not guaranteed
repeatable (providers revise data). The input hash makes any later difference detectable, and the app says
"reconstructed".

## 8. Speed and memory

- Load each timeframe's candles **once per run**, never once per T.
- Step through T, recomputing per T **unless** the signal holds slice-equivalence certification (§4.3).
- Each replay run has its own short-lived result cache, separate from the shared live cache, so a long replay
  cannot push out the dashboard's live results.
- Display replays are capped (for example 90 steps per request). Long research replays run in CI or a one-off
  job, never in a page load.
- **Benchmarks of the real path, before any claim:**
  - 30-step and 365-step replays of the Multi-Timeframe Set on one crypto and one share;
  - with and without slice-equivalent shortcuts;
  - reporting time, peak memory and memory growth, in CI as for the Analysis card.

## 9. What gets built (in reviewable stages)

1. **Replay foundation:**
   - the replay context: cutting at T, forming-candle recomputation, the live lookback, the mode, the per-run
     cache;
   - the replay record;
   - source-quality records;
   - the hold-out refusal and module guard tests.
2. **Certification harness (CI):**
   - the independent truncated path, poisoning, cache isolation, timestamp and boundary tests;
   - algorithm status per signal version;
   - fixes for failures;
   - slice-equivalence certification.
3. **Groups and Sets integration:** `point_in_time` mode, the completeness field, critical members and coverage
   profiles.
4. **Admin inspector:** an "as of" date on the Groups & Sets tab (display mode only; it shows completeness,
   limitations and the replay record). Nothing on the dashboard changes.
5. **Benchmarks** (§8) and a report. Stages 1–2 are reported before stage 3 starts.

**Not in scope:**
- the Signal matrix redesign;
- the Strategy builder;
- research statistics, lead tests or optimisation;
- hold-out evaluation;
- derivatives history collection (decision E, separate task);
- any change to Trend, Stretch, Flow or alerts.

**Acceptance:**
- every candle signal is certified per version and timeframe, or listed as not certified with a reason;
- the certification suite runs in CI on every change;
- research mode refuses T on or after 2024-10-30, and the research dataset contains no hold-out rows (tested);
- the module guard test passes;
- `available_at <= T` everywhere in replay results (tested);
- completeness and coverage profiles are correct for the starters and the example Set;
- live results are unchanged byte for byte;
- benchmarks are reported.

## 10. Decisions (reviewed 4 Nov 2026)

- **A. Approved, with clarification.** As-of reconstruction: current algorithms, normal lookback, inputs cut at
  T. Not a reproduction of the historical display (§2).
- **B. Approved.** Non-replayable members are unavailable under the existing rules. Partial results are always
  qualified (§5.1).
- **C. Approved for descriptive replay only.** Split-adjusted prices are a recorded limitation, never strict
  point-in-time data (§3, §4.2).
- **D. Approved.** Research uses frozen, versioned, hashed development data. Display uses current providers,
  marked as reconstructed (§6, §7).
- **E. Approved in principle, as a separate task.** Before any collection is enabled, investigate append-only
  hourly derivatives snapshots: observation time, first-seen time, source, revisions, API availability, the
  meaning of the history, licensing, storage and cost.

## 11. Implementation notes (stages 1–2)

The review of revision 2 accepted it with two clarifications, both implemented:
- **Timestamp rule.** It applies to all market data, events, evidence and observations. The only exemptions are
  administrative times: `computed_at` on each result, and `administrative.run_started_at` in the replay record,
  which is labelled as not market data.
- **Reproducibility.** Research records reference the actual frozen dataset, not only hashes:
  - its location (reports branch, `data/prices`), the reports-branch commit, the manifest hash and the hash of
    every file read;
  - the execution environment: Python and package versions, plus the hash of `requirements-research.lock`.

Where the build differs from, or adds detail to, the text above:
- **The candle containing T is dropped.** It is not shown as "forming", because its values include data from
  after T. Signals only read closed candles, so their results are unaffected.
- **Research data is daily only.** The frozen research dataset holds daily bars (1D, with 1W grouped from them).
  Intraday research replays report that no research data exists for that timeframe.
- **The research price limitation is wider.** The frozen research prices are split- **and dividend-adjusted**
  (downloaded with `auto_adjust`), so their limitation text says both.
- **Some data can only be certified on synthetic data:**
  - intraday timeframes: all real intraday data available today falls inside the hold-out period;
  - flows signals: stored flows begin in 2026, also inside the hold-out period.

  Daily and weekly timeframes are also certified on frozen development data dated before 2024-10-30.
- **The reference shares one definition with the replay path.** The independent reference still uses
  `chart_data.candle_end` (the definition of when a candle closes). Its window cut, data handling, process and
  caches are all separate.
- **Replays have their own status.** `not_replayable` is a new result status, used only in replays.
- **A certification record is tied to code.** It counts only for the exact source of 11 files (the Signal
  Library, `scoring.py`, `regime.py`, `chart_data.py`). After a change to any of them, nothing counts as certified
  until the suite is re-run and its record committed. CI fails while the committed record differs.
- **Display replays are capped** at 90 time steps per run.

## 12. Implementation notes (stage 3: Groups and Sets)

**Calling it.** `evaluate_group` and `evaluate_set` accept `data_mode="point_in_time"` together with a replay
context at T (`ReplayRun.context`). A live context in that mode, a replay context in live mode, or a context at a
different T is refused with status `unsupported` and the reason. Live results are unchanged, checked against the
golden snapshot.

**Members.** Each member row in a replayed result carries `replay_availability`:
- `replayable` (the signal status is ok or stale);
- `not_replayable` (not certified, a derivatives source, or non point-in-time flows);
- `no_history_at_T` (missing or insufficient data at T);
- otherwise the signal's own status.

Missing members go through the existing coverage, exclude/neutral and three-valued rules unchanged.

**Completeness** (`signal_groups/replay.py`):
- **Label:** `complete`, `partial`, `limited`, or `partial and limited`.
- **For each missing member:**
  - the reason;
  - whether it is critical, and why;
  - whether it affects the score's coverage;
  - which confirmations and vetoes it leaves unknown. Only conditions actually left `unknown` are listed: a
    confirmation already false on the score alone stays false.
- **Limitations:** the limitation texts of the sources used.
- **`qualified`:** true for a partial or limited result, or one with an unknown veto.
- **Sets:** a Set reports each Group's label and its own worst case. Standalone items and applicable market items
  that cannot be replayed count as missing. A market item that does not apply to the asset (Bitcoin context for a
  share) does not.

**Critical members:**
- members any veto depends on (a score predicate in a veto depends on every scoring member);
- score members without which the minimum coverage cannot be reached.

**Coverage profiles.** `group_coverage` and `set_coverage` produce date ranges, each with one of the four levels,
plus the missing and critical-missing members and the reasons. They are computed from:
- the certification record;
- the first candle close of every timeframe the member reads. Multi-timeframe alignment needs at least two
  timeframes, so its start is that of its second timeframe;
- the first live (not backfilled) sighting for stored flows, from `flow_history_start`, or from `flow_starts`
  passed in.

**Live-only market items.** In point-in-time mode, a market item marked `data_modes: ["live"]` (for example the
example Set's Bitcoin ETF flows, which use backfilled history) is skipped as live only. A Set that contains it is
therefore partial.

**Market contexts must match.** A market context must itself be a replay context at the same T, otherwise the item
is skipped with the reason.

**Coverage is conservative** (Stage 3 review). For each member a coverage profile records two starts:
- `source_from`: when its input data first exists;
- `confirmed_from`: the first cutoff from which the signal is confirmed to produce readings, so warm-up,
  confirmation periods and other timeframes are included. It is found by evaluating the signal: bisection over
  candle closes (or days, for flows), then the next three cutoffs must read as well, otherwise the search
  continues after the failure.

Levels use `confirmed_from` only. Ranges where source data exists but readings are not yet confirmed are labelled
partially evaluable, with the reason "source data present, but no confirmed reading yet". A flows source whose data
is not in the run has a source start but no confirmed start, so it is never counted as replayable. Inside a
replayable range an individual date can still lack a reading (for example a weekly timeframe early in a run); the
completeness of a replay at that date reports it.

## 13. Slice equivalence within a stated tolerance (5 November 2026, approved by the owner)

The certified slicing shortcut and the exact path compute the same numbers by different routes. On different CI
machines they differed in about the 16th significant digit (for example 0.7347059897980095 vs 0.7347059898057529),
which made the committed certification record match one kind of machine and fail on the other.

- **Slice equivalence** now treats numbers as equal when |a − b| ≤ 1e-9 × max(1, |a|, |b|), the tolerance already
  used for the Trend/Stretch/Flow parity check. Everything that is not a number (statuses, labels, keys, list
  lengths, timestamps) must still match exactly.
- The **reference, poisoning, cache and timestamp checks stay exact**: they compare the same computation and are
  what detects leaks.
- Slice failures are recorded as the field and the size of the gap ("differs by 1.0e-04"), never as raw float
  digits, so the compared record is the same on every machine.
- Certification suite version 2. A shortcut certified under it may differ from the exact path by at most the
  tolerance, far below anything displayed (scores are shown to whole points).
