# Prism History: when would a Set have said Yes, and what followed?

Status: **proposal, revision 1 (5 November 2026)**. For review before anything is built. The research design that
`lattice_prism.md` §5.4 asks for. Nothing here touches the dashboard, alerts, saved configurations or the protected
hold-out.

## 1. What it is, and what it is not

**It is** an event study for one Set with a decision: across the research history, on which days did the answer
turn Yes, and how did the price move afterwards, compared with an ordinary day for the same asset?

**It is not:**
- a strategy or backtest: no positions, sizing, entries, exits, stops or costs;
- a tuning tool: no search for the best thresholds, labels or timeframes;
- evidence that a Set works: results are labelled exploratory, and only a separate pre-registered certification
  (`lattice_prism.md` §9) could support a "researched" claim.

## 2. Data, period and the hold-out

- **Data:** the frozen research dataset only (`replay_research.FrozenDailyCandles`, the `data/prices` manifest on
  the reports branch: 88 daily histories, about 60 shares and 28 crypto assets). Research mode, `RESEARCH` replay
  rules.
- **Period:** each asset's first usable day (its first candle plus the 260-candle warm-up) up to **29 October 2024**.
  Rows from 30 October 2024 onwards are removed as the files are read (`point_in_time.md` §6). Requests reaching
  into the hold-out are refused before any data is touched. **No event or outcome uses the hold-out**, including
  the forward window of an event near the end: an event whose 20-candle window would cross 30 October 2024 has no
  20-candle outcome.
- **Assets:** the Watchlist assets present in the research dataset, or the whole research universe (chosen per
  study). Watchlist assets not in the dataset are listed as not studied.

## 3. Which Sets can be studied

A study is refused, with the reason, unless:
- the Set has a decision (`sg.scannable`);
- every member and standalone item is a **daily** candle signal (the research data is daily). Members on other
  timeframes are refused for now;
- every signal is **certified** for 1D in `certification.json`;
- no member needs data the research period does not have: **sentiment** (history from November 2026),
  **stored flows** (first-seen history starts after the hold-out), **derivatives** (live only). These Sets can be
  scanned live but not studied.

## 4. Events

For each asset, the Set's answer on every research day is a series of Yes / No / Unknown (one point-in-time
evaluation per daily close).

- **An event** is a day the answer **turns Yes**: Yes after No. Yes after Unknown is counted separately as
  "after a data gap" and excluded from the main numbers, because the earlier answer is unknown.
- The **Yes spell** that follows (how many days it stayed Yes) is reported, but outcomes are measured from the event
  day only.
- Unknown days are reported (count and share), never filled.

## 5. Outcomes

Using the existing research statistics (`research_stats.py`), so the conventions match the validation work:

- **Forward return** after an event at horizons **5 and 20 daily candles** (1 candle shown for information only):
  from the close one candle after the event (`LAG = 1`, the next close, so the event day's own close is never
  "traded") to the close `h` candles later (`research_stats.forward_returns`).
- **Baseline:** the same measure on **every eligible day** for the same asset (its ordinary day), and separately on
  days the answer was No.
- **Market-relative:** each forward return ranked across the research universe on the same date
  (`cross_section_ranks`, shares and crypto separately), so a rising market does not make every Set look good.
- **Shown:** event count, median and mean forward return, share positive, and the same for the baseline; the
  difference with a 95% interval from the joint-date block bootstrap (`block_draws`, block length
  `block_for(h)`). No p-values in the headline.

## 6. Overlap, small samples and repeated tries

- **Overlap:** events of the same asset closer together than the horizon share price moves. The main numbers use
  non-overlapping events per horizon (an event within `h` candles of the previous counted event is skipped); the
  count of all events is shown beside it.
- **Minimum events:** below **30** non-overlapping events at a horizon, only the count is shown and the comparison
  is withheld ("too few events to compare").
- **Repeated tries:** every study run is logged with the Set version's content hash. The page shows "study N for this
  Set" and lists earlier versions studied, so fitting the past by small edits stays visible. There is no automatic
  "best setting" search.
- **Plain warnings** on every result: exploratory, not validated; no costs or slippage; research period ends 29
  October 2024; shares are split-adjusted daily closes.

## 7. The fast path (history mode)

Step-by-step replay costs about 1 second per date per asset; a Watchlist over the research period is hours. History
needs each signal's whole history computed in one pass, without giving up the point-in-time guarantee.

- **Signals with certified slicing** (`slice_equivalent` in the record): indicators are computed once on the full
  frozen frame; each cutoff reads its slice. Already certified; reused as is.
- **Other signals** (swing points, divergences, structure, OBV and the others listed as not slice-equivalent): a
  **causal full-history implementation** per signal, computing every day's value in one forward pass using only past
  data. This is the planned swing-point speed-up, brought forward.
- **History equivalence certification** (new, required before any study uses a signal): the history-mode value
  must equal the step-by-step research replay at sampled cutoffs (every 20th day, a random sample, and every event
  day of the test Sets), on synthetic data and development data before the hold-out, within the §13 tolerance;
  plus the existing poisoning test applied to history mode. A signal that fails falls back to step-by-step replay
  (slow, but correct) and the study says so.
- **Target:** a 15-asset study over the research period in under 10 minutes in CI.

## 8. Where it runs and how it is shown

- **Runs as a research job**, never in a page load (`point_in_time.md` §8): a GitHub Actions workflow, started by
  hand or nightly for pending requests. It reads the frozen data, writes the results and the replay record.
- **Requests:** an admin presses **Request a history study** for a saved Set version on the Prism page; a request
  row is stored. The job picks up pending requests, runs them and stores the result.
- **Storage:** a results table (owner-readable, written only by the service role), with the Set version hash,
  period, assets, eligibility notes, per-horizon statistics, the event list (date, asset) and the replay record.
- **Display:** a **📜 History** view in Prism shows stored results only:
  - a summary per horizon (events, median and share positive vs baseline, interval, market-relative);
  - per asset: events and Yes spells on a timeline;
  - the warnings in §6 and any assets or signals that could not be studied.

## 9. Build stages

1. **H1, history engine and certification** (headless): history mode for the slice-equivalent signals, causal
   full-history implementations for the rest, the history-equivalence certification in CI, and benchmarks.
2. **H2, the study** (headless): events, outcomes, overlap, bootstrap and the report, run by a CI job on test Sets
   with a markdown report.
3. **H3, requests, storage and the History view.**

Each stage on its own branch with a report and CI, merged on approval.

## 10. Questions for review

- **A. Events as "turns Yes after No"**, with "after a data gap" separate. Alternative: count every Yes day.
  Recommended: transitions.
- **B. Horizons 5 and 20 daily candles, entry at the next close**, matching `research_stats`. Recommended: yes.
- **C. Baselines:** all eligible days of the same asset, plus No days, plus market-relative ranks. Recommended: all
  three, with all-days as the headline.
- **D. Non-overlapping events and a minimum of 30** per horizon before any comparison. Recommended: yes.
- **E. Eligibility:** daily, certified, candle-only Sets in the first build. Recommended: yes.
- **F. History equivalence certification** before any signal's fast path is used, with step-by-step fallback.
  Recommended: yes.
- **G. Runs as a research job with requests**, results displayed only. Recommended: yes.
- **H. Study log** visible per Set to show repeated tries. Recommended: yes.
