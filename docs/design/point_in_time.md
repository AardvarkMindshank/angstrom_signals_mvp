# Point-in-time evaluation ("replay"): design note

Status: draft for review, revision 1 (4 Nov 2026). Nothing here is built yet.

## 1. What this is for

Today every Signal Library signal, Group and Set is worked out for **now** only. Groups and Sets refuse any other
date on purpose: not every signal and cache can yet be trusted to ignore data that arrived later.

Point-in-time evaluation means answering: **"what would this signal, Group or Set have said at time T, using only
what was knowable at T?"** Everything historical depends on it:
- a Signal matrix built from Groups;
- evidence views;
- the later Strategy builder and Research/Evaluate tests, for example Drew's TradingView strategy or "does
  Coinbase's share price lead Bitcoin?".

This note covers the foundation only. It changes nothing on the dashboard: Trend, Stretch, Flow, the matrix and
alerts stay exactly as they are.

## 2. The rule

A replayed result at time **T** may use only:
- candles whose **close time is at or before T**;
- stored observations whose **first-seen time is at or before T**, using the value as known at T and never a later
  revision.

Every result already carries `available_at`, the time it could first have been known. In a replay,
**`available_at <= T` must hold for the result and for every event and evidence item inside it.** A result that
breaks this is an error, never a value.

**What it targets.** A replay at T reproduces **what the app would have shown at T**: the same candle history
length the live app loads (for example one year of daily candles), cut off at T. It is not "the best possible
answer using all history". Long-memory indicators (EMAs, swing lists, zones) therefore match what a user would
actually have seen. *(Review question A.)*

## 3. How each kind of data is handled

| Data | How it is replayed |
|---|---|
| **Candles** (all technical signals) | Load the history once. For each T, keep only candles that had closed by T, recompute which candle is "forming" relative to T (the existing `chart_data.mark_forming(now=T)`), and apply the live lookback window. Shares use their exchange session close; crypto uses UTC. |
| **Multi-timeframe signals** (`mtf.alignment`) | Each timeframe is cut separately at T. A weekly candle still open at T is excluded, exactly as live. |
| **Stored flows** (Bitcoin ETF flows, stablecoin supply) | Already supported: `daily_values(as_of=T, point_in_time=True)` keeps the latest revision first seen by T and drops backfilled rows. Replays force `point_in_time=True`. |
| **Derivatives** (open interest, liquidations, liquidation levels) | **Live only.** The stored record keeps about 7 days and is overwritten hourly, so no honest history exists. Marked "not replayable". *(Review question E: start storing an append-only hourly history now, so these become replayable later.)* |
| **Sentiment** (later, once it joins the library) | The same first-seen rule as flows. |

**Price adjustments.** Yahoo's history is adjusted for share splits, so past prices differ from the raw prices
quoted at the time. This does not reveal direction, and every signal uses ratios or comparisons, so we accept it
and document it as a known limitation. *(Review question C.)*

**Intraday history limits.** Yahoo gives about 60 days of 15-minute candles and about 2 years of 1-hour candles.
Replays of intraday signals before that return "insufficient history". They never fall back to another timeframe.

## 4. Certification: proving each signal does not peek

Each signal definition gets a replay status: **`certified`** or **`live_only`** (with a reason). Only certified
signals run in a replay; the others come back as unavailable with reason `not_replayable`.

A signal is certified only by passing the automated **truncation test** in CI, for every timeframe it supports:

1. Take a candle history: made-up random walks, plus frozen real development data for several crypto and stock
   assets.
2. Choose at least 50 cut points T spread across the history, including just before and after candle closes,
   weekends and share sessions.
3. Evaluate the signal at T twice:
   - **(a)** with the full history loaded, replayed at T;
   - **(b)** with the history physically cut at T.
4. Status, value, events and their states, levels and `available_at` must be identical.
5. Every timestamp inside the result must be at or before T.

This catches the subtle cases:
- swing points need `right` candles to confirm;
- the regime state must hold for N candles;
- divergences expire after 30 candles;
- an indicator could accidentally be computed on the whole frame and then sliced.

A failing signal is either fixed or stays `live_only`. Certification is re-run on every change, so a later edit
cannot silently break it.

## 5. Groups and Sets

- `evaluate_group` and `evaluate_set` accept `data_mode="point_in_time"` with `as_of=T`. Live mode is unchanged.
- **Uncertified members** (for example derivatives) are treated as unavailable with reason `not_replayable`. The
  existing rules then apply unchanged: score coverage, exclude/neutral policies, and conditions becoming "unknown".
  The whole Group is **not** refused. *(Review question B.)*
- Each Group and Set gets a computed **history label**, for example "replayable from 2019-01-01", "replayable from
  2026-08-14 (Bitcoin ETF flows)" or "live only". It comes from its members' certification and data start dates,
  never typed by hand.
- Stored Group and Set versions are immutable and pinned, so a replay of version 3 always means the same rules.

## 6. Protecting the hold-out

The validation spec fixes the hold-out start at 2024-10-30 (`research.HOLDOUT_START`, tag `holdout-spec-v1`).

- Every replay request states its purpose: **`display`** or **`research`**.
- **`display`** (charts, a matrix of recent days, the admin inspector) may use any date. It is descriptive only and
  never produces statistics.
- **`research`** (lead tests, backtests, evidence, anything that produces a statistic or tunes a parameter) is
  **refused for any T on or after the hold-out start**, and uses the frozen research price cache, so results can
  be repeated exactly. *(Review question D.)*
- The hold-out itself stays untouched. Nothing in this work reads it.

## 7. Speed and memory

A naive replay reloads data and recomputes every indicator for each T. Instead:

- **Load once per run.** Each timeframe's candles are fetched once. Indicators are computed once on the full
  frame. This is allowed only because certification proves the result equals computing on the cut frame.
- **Step through T.** Each step slices the precomputed frame, which is cheap because signals read the last closed
  candles.
- **Separate cache.** Each replay run has its own short-lived result cache. It does not touch the shared live
  cache (512 entries), so a long replay cannot push out the dashboard's live results.
- **Bounded runs.** Display replays are capped (for example 90 steps per request). Long research replays run in CI
  or a one-off job, not inside a user's page load.
- **Measured before release.** Time and memory for a 30-step and a 365-step replay of the Multi-Timeframe Set on one
  asset, reported in CI as was done for the Analysis card.

## 8. What gets built (in reviewable stages)

1. **Replay context.** Cutting at T, forming-candle recomputation, the live lookback window, the purpose flag, the
   hold-out guard and the per-run cache.
2. **Certification harness** (CI), the replay status on every definition, and fixes for any signal that fails.
3. **Groups and Sets** accept `point_in_time`; the computed history labels.
4. **Admin inspector:** an "as of" date on the Groups & Sets tab, to try replays on live data. Admin only;
   nothing on the dashboard changes.
5. **Measurements** (section 7) and a report.

**Not in scope:**
- redesigning the Signal matrix;
- the Strategy builder;
- statistics or lead tests;
- storing derivatives history (question E, separate small task if approved);
- any change to Trend, Stretch, Flow or alerts.

**Acceptance:**
- every candle signal is certified, or listed as `live_only` with a reason;
- the truncation test runs in CI on every change;
- research-purpose replays on or after 2024-10-30 are refused (tested);
- replay results satisfy `available_at <= T` (tested);
- live evaluation results are byte-for-byte unchanged (tested against the current starters);
- measurements are reported.

## 9. Questions for review

- **A. What a replay reproduces.** "What the app would have shown at T" (same lookback as live), rather than "the
  best answer using all history before T". Recommended: the former.
- **B. Uncertified members.** Treat them as unavailable (the Group still evaluates under its coverage rules, with
  the history label), rather than refusing the whole Group. Recommended: unavailable.
- **C. Split-adjusted prices.** Accept Yahoo's adjusted history as a documented limitation. Recommended: accept.
- **D. Candle source for research replays.** Use the frozen research cache (reproducible) for research purposes,
  and live Yahoo for display. Recommended: yes.
- **E. Derivatives history.** Start an append-only hourly record now (small, cheap), so open interest and
  liquidations become replayable in future. Recommended: yes, as a separate task.
