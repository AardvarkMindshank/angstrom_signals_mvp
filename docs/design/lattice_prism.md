# Lattice and Prism: the research workspace and the market scanner

Status: **proposal, revision 1 (5 November 2026)**. Step 2 of the agreed sequence (design the builder). For review
before any build starts. Nothing here changes the dashboard, Trend/Stretch/Flow, alerts as they work today, the
Signal Matrix, or the accepted Groups/Sets design, except the extensions in §4, which need explicit approval.

Inputs:
- the clickable mockup (four screens: Groups, Sets, Prism run now, Prism scheduled scans), reviewed by ChatGPT and
  Grok in three rounds on 5 November;
- Grok's external research, `docs/research/visual_strategy_builders.md`;
- the accepted designs `groups_sets.md` (revision 4), `point_in_time.md` and `library_completion.md`.

## 1. Names

| Name | What it is |
|---|---|
| **Angstrom Signals** | The product. Unchanged; no second product name. |
| **Lattice** | The research workspace inside it. Header: "Angstrom Signals · Lattice", subtitle "Research workspace". |
| **Groups**, **Sets** | As in `groups_sets.md`. |
| **Prism** (subtitle "Market scanner") | Runs a Set on assets: **Run now** (once, now or at a past date) and **Scheduled scans** (on a schedule, with alerts). Replaces the mockup's separate "Evaluate" tab. |
| **Strategies** | Later, shown greyed out. Specified separately once Drew's trading rules are in. |

Vocabulary in the app: "Open Lattice", "Build a Group", "Create a Set", "Run Prism", "Schedule a Prism scan".
Trademark and product-name checks are needed before any public use of "Lattice" and "Prism".

## 2. What the reviews settled (frozen as the design reference)

**Groups**
1. Signals are added by drag and drop or by tapping **+** (iPad). Each member has a role (Score, Condition,
   Levels, Context) and its own timeframe.
2. Every member shows what it is read from, generated from its timeframe and source: "4H · last closed candle",
   "Latest score at the time" (sentiment), "Last published flow day" (flows), "Live reading only" (derivatives).
3. Rule operands always show **which number** they are and its scale: a signal's *native value* (RSI, 0 to 100), its
   *standard score* (−1 to +1), the *Group score* (shown −100 to +100), or a *yes/no* reading. Labels (Bullish…) are
   categories, never numbers.
4. Thresholds are validated against the chosen operand: wrong type or a value outside the scale **blocks saving**,
   with the reason in plain words.
5. Rule order is visible and reorderable; first match wins. **Unknown** is a fixed, visible outcome: if a rule
   cannot be checked, the label is Unknown and later rules are not tried. **Neutral** only when every rule was
   checked and none matched.
6. Checks: blocks (cannot save) vs warnings (can save). Warnings include: two score members measuring the same
   thing; all score members from price; mixed timeframes; members with short or no history; members available for
   some assets only; a Condition member no rule uses; a Score member also tested in a rule (reused evidence, not
   independent confirmation); an OR rule that can overlap another rule (priority decides).
7. An auto-written description of what the Group does, always generated from the document.

**Sets**
8. Groups and single signals are combined. No Set score (D7 unchanged). A Group in a rule is used either by its
   **label** or its **score**, chosen explicitly.
9. The Set's decision is shown as an **ALL (AND)** box, optionally holding **ANY (OR)** groups, with a fixed
   explanation of how Yes / No / Unknown are reached: No if any necessary line is No, even with gaps; Unknown when
   nothing is No but something is missing, naming what.
10. Warnings when members share signals or sources.

**Prism**
11. Results separate the **answer** (Yes / No / Unknown), **how sure** (Definite / Undecided, with the decisive
    reason: "Fails on Trend; missing sentiment could not change this") and **data available** (Complete / Partial).
12. Scheduled scans run on the Watchlist only, with a chosen schedule, alert on change by default, never alert on
    Unknown, and use the existing alert channels.
13. Strategies are a greyed-out future preview: no position, order, fill or stage is implied anywhere.

## 3. How the mockup maps to the accepted Groups/Sets design

| Mockup | Accepted design (`groups_sets.md`) | Gap |
|---|---|---|
| Roles Score / Condition / Levels / Context | §3.1, identical | none |
| Score member uses the standard score | `transform` on a field (`clip` on `standard_score`, as the starters do) | none |
| Group score −100..+100 | stored −1..+1 (§3.2), displayed ×100 as the dashboard does | display only; thresholds typed in display units are converted |
| Rules with AND / OR, three-valued | §3.4 `all` / `any` / `not`, three-valued | none |
| Type check on operands | §3.4 "comparing incompatible types is refused at save time" | range check is new (E3) |
| **Ordered label rules** (Bullish / Bearish / Neutral / Unknown) | named `conditions` (confirmation / veto) and `status`; labels are presentation | **E1** |
| **Set decision** (Yes / No / Unknown) | Sets have no rules: "an analysis configuration, not a strategy" | **E2** |
| Standalone signal used in a Set rule | standalone role must be `context` or `levels` | part of **E2** |
| Warnings (unused, reused evidence, overlap) | §3.5 diagnostics, never change results | additions to diagnostics only |
| Prism run now | evaluation on demand (§8), replay `DISPLAY` mode for past dates | none |
| Scheduled scans and alerts | §9 "Later: alerts on Groups" | **this proposal (§5)** |

## 4. Proposed extensions (need approval)

### E1. Group outcome labels

An optional `outcomes` list on a Group, evaluated **after** the existing conditions, in order:

```json
"outcomes": {
  "version": 1,
  "rules": [
    {"label": "Bullish", "when": {"all": [{"score": {"gte": 0.30}}, {"member": "rsi_1d", "lte": 70}]}},
    {"label": "Bearish", "when": {"score": {"lte": -0.30}}}
  ],
  "otherwise": "Neutral"
}
```

- Each `when` is an ordinary §3.4 rule (same engine, limits and counting contract).
- Evaluation: first rule that is **true** wins. If a rule is **unknown** before any rule is true, the outcome is
  `Unknown` and later rules are not evaluated, because the unknown rule might have matched. `otherwise` only when
  every rule is false.
- Labels are free text (≤ 24 characters) from a short suggested list; the Set editor offers a Group's own labels
  plus `Unknown`.
- Existing documents without `outcomes` are unchanged; their content hashes do not change. The starters gain no
  outcomes in this step (their words stay presentation, as decided in `library_completion.md` §3).
- Schema: additive optional key under `angstrom.group/1`, accepted by the validator from this version on.
  *Review question A.*

### E2. Set decision rule

An optional `decision` on a Set:

```json
"decision": {
  "version": 1,
  "rule": {"all": [
    {"group": "trend", "outcome": {"eq": "Bullish"}},
    {"not": {"group": "momentum", "outcome": {"eq": "Bearish"}}},
    {"member": "sentiment_market", "gte": -20}
  ]}
}
```

- New predicate targets: a Group's `outcome` (E1 label), `score` (−1..+1), or a named `condition` state (met / not
  met / unknown). Signals by `member`, as in Groups.
- The same three-valued `all` / `any` / `not` and counting contract. Answer: **Yes** = true, **No** = false,
  **Unknown** = unknown. A Group whose outcome is `Unknown` makes its predicate unknown.
- To use a standalone signal in the decision, standalone items may take role **`condition`** (today: `context` or
  `levels` only). Context items stay unusable in rules.
- Still no Set score, no entry, exit, sizing or risk: the decision answers "does this asset match?", nothing more.
- The result names the **decisive lines**: for No, the lines that are false; for Unknown, the unknown lines that
  could change the answer. This is computed from the rule tree, not from the completeness labels.
  *Review question B.*

### E3. Operand scales and range checks

- Signal definitions gain an optional `fields` description: for each readable field, its type (number, label,
  yes/no, events), unit and, where fixed, its range (RSI 0..100, standard score −1..+1, sentiment −100..+100).
  Fields without a fixed range (MACD in ATRs, ETF flows in US$) show the unit only.
- The validator refuses a threshold outside a fixed range, and a comparison between incompatible types. The editor
  shows the scale next to every threshold.
- Adding `fields` documents existing outputs; it is not a calculation change and no signal version changes. The
  definitions live in files listed in `CODE_FILES`, so the code hash changes and the certification record is
  regenerated in the usual way; every certified result must be identical before and after. *Review question C.*

## 5. Prism

### 5.1 Run now

- Pick a Set and assets (default: the Watchlist). **Now** evaluates live with confirmed candles only; **a past
  date** uses the certified point-in-time reconstruction in `DISPLAY` mode (`replay_display.display_run`).
- Results table: one row per asset with each Set line's reading (label and score for Groups, value with its scale
  for signals), the answer, how sure with the decisive reason, and data available.
- No statistics (hit rates, returns after a Yes). Those are research and need the protected hold-out rules; they
  belong to the backtesting and strategy work.

### 5.2 Scheduled scans

**What a scan is.** Owner, a pinned Set version, the Watchlist, a schedule, an alert mode, channels, paused flag.

**Schedules.**
- *Each candle close* for 4H, 1D or 1W: the scan runs once a new candle of that timeframe has closed for the asset
  (crypto 1D at 00:00 UTC; shares after the US close, using the library's share calendar).
- *Set times*: up to 4 times a day in the user's time zone, with every day, weekdays or chosen days.
- Each run's cutoff **T** is the scheduled moment. Every member uses only its last closed candle at T.
- A warning (not a block) when the schedule is faster than the Set's slowest-changing member ("this Set reads daily
  candles; every 4 hours gives the same answer until the next daily close").

**Where it runs.** Inside the existing worker (`run_alerts.py`, started every 5 minutes by the Supabase clock via
`alerts.yml`). No new service, no always-on process. Each tick:
1. find scans that are due (like `digest_due`), oldest first;
2. evaluate each due scan at its cutoff T through the **same point-in-time path as "past date"** in Run now, so a
   scheduled result can be reproduced exactly later and matches what "Check past dates" shows;
3. store a compact run record; decide alerts; send.

**Budget.** About 1 second per asset per Set (stage 4–5 benchmarks). Limits for the first build: 5 active scans per
user, Watchlist size as today, and a per-tick time budget (default 4 minutes of the worker's 15). Scans that do not
fit wait for the next tick and say so ("ran 6 minutes late"); none are dropped silently.

**Alerts.**
- Default mode **turns Yes**: an alert when an asset's answer becomes Yes after being No or Unknown. A latch per
  (scan, asset), like the existing reading alerts: released only by a **No**. Unknown neither opens nor releases it,
  so a data gap cannot cause a repeat alert.
- Optional mode **every run while Yes**.
- Unknown never alerts; it is listed on the results page ("couldn't decide: market sentiment missing").
- Delivery through the existing system: an in-app row in `user_notifications` (new `alert_type` `prism`), instant
  email if the user has instant alerts on, otherwise a **Prism** section in the daily digest. Discord and Telegram
  later.

**Storage** (new SQL file, same safety rules as `2026-11-04_signal_groups.sql`: owner-only, writes through
security-definer functions, re-runnable):
- `prism_scans`: id, owner, set config + version, schedule (jsonb), alert mode, channels, paused, timestamps.
- `prism_scan_runs`: scan, cutoff T, started/finished, code identity (as the replay record), and per asset: answer,
  how sure, decisive lines, data available. Kept 90 days.
- `prism_scan_latches`: (scan, asset) → open since.

**Results page.** Latest run grouped as: New Yes (alerted) · Still Yes · Couldn't decide · No (collapsed), each
with its reason and a link to the asset. **Check past dates** replays the scan over recent dates in `DISPLAY` mode
(at most 90 steps, as now) to show what it would have flagged, without statistics (§5.1).

*Review questions D–F.*

### 5.3 History: when would it have fired, and what followed? (proposed for discussion)

A single past date is mainly a check that a reconstruction is faithful. The practical question is: **across all the
available history, when did this Set's answer turn Yes, and what did the price do afterwards?** This is an event
study, not a strategy: no positions, sizing, entries or exits.

- **Events:** every date the answer turned Yes (after No or Unknown), per asset. Unknown periods are reported, not
  filled.
- **What followed:** forward returns after each event (for example 1, 5 and 20 candles), compared with the same
  measure on all dates for that asset (the baseline), with the number of events, their spread and the share
  positive.
- **Research rules apply:** statistics use `RESEARCH` mode on the frozen data before 30 October 2024 only; the
  protected hold-out stays untouched until a separate certification. Sets whose members have no history in that
  period (sentiment, derivatives) cannot be studied, and say so.
- **Guardrails against fitting the past:** minimum event counts with a warning below them; overlapping events
  counted once per window; every Set version tested is recorded so the number of tries is visible; no "best
  setting" search.
- **Speed:** step-by-step replay costs about 1 s per date per asset, which is hours for six years of a Watchlist.
  History needs the planned fast path: each signal's full history computed in one causal pass, certified equal to
  the step-by-step replay at sampled cutoffs. This brings the planned speed-up forward from the strategy work.
- **Place in the order:** after scheduled scans and before strategies; strategies later reuse the same fast path
  and event engine.

*Review question H.*

## 6. The editor (Lattice UI)

- Streamlit cannot drag and drop natively. Proposal: one small custom component, built like the existing chart
  component (`lw_chart.js` / `lw_chart.py`): a signal panel and drop zones with HTML5 drag and drop **plus tap-to-add
  buttons** for touch screens. It returns the edited document; all validation, warnings, descriptions and saving
  stay in Python, using `validate.py` and the existing save functions.
- Icons with hover explanations, as elsewhere. Text strings collected in one place, ready for translation later.
- Saving uses the accepted versioned storage (`analysis_configs`); nothing about versions, publication or sharing
  changes.

## 7. Build order (proposed)

Each stage on its own branch with a report, CI green, merge only on approval.

1. **Engine extensions** E1–E3, headless: validator, evaluation, decisive-line explanation, tests and fixtures for
   every Yes/No/Unknown case in §2, including definite No with missing inputs.
2. **Prism Run now**, admin-only first: a Lattice page with Set and asset pickers and the results table. Usable with
   starter Groups and Sets made by an admin, so Drew can start before the editor exists.
3. **Scheduled scans**: SQL, worker integration, alerts, digest section, results page; admin-only, then all users.
4. **Editor**: the drag-and-drop component and Group/Set editors.
5. **Strategy specification**: separate design note from Drew's rules, script and examples (unchanged plan,
   including the swing-algorithm speed-up and re-certification for the strategy engine).

This moves Prism ahead of the strategy work: it needs no trading logic and answers Drew's daily need (a shortlist
from the Watchlist) soonest. *Review question G.*

## 8. Not in scope

Strategies, ladders, positions, orders and fills; statistics or backtests on scan results; assets outside the
Watchlist; Discord and Telegram; Set scores; any change to the dashboard, Trend/Stretch/Flow, existing alerts or
the Signal Matrix.

## 9. Questions for review

- **A. Group outcome labels (E1)** as an optional, ordered `outcomes` list on top of the existing conditions, with
  "Unknown stops evaluation". Recommended: yes.
- **B. Set decision (E2)** as an optional three-valued rule, with standalone `condition` items allowed. This relaxes
  "a Set has no rules" while keeping "no entry, exit or risk". Recommended: yes; it is what makes Prism possible.
- **C. Field descriptions and range checks (E3)** as documentation on definitions, with no signal version change.
  Recommended: yes.
- **D. Scheduled runs use the point-in-time path** at cutoff T rather than the live path, so stored results are
  reproducible and match "Check past dates". Recommended: yes (cost about 1 s per asset).
- **E. Alert latch** released only by No, never by Unknown. Recommended: yes.
- **F. Limits**: 5 active scans per user, Watchlist only, 4-minute budget per worker tick, 90-day run history.
  Recommended: yes, revisit with usage.
- **G. Build order** with Prism before the editor and before strategies. Recommended: yes.
- **H. History (§5.3)**: an event study of when a Set turned Yes and what followed, under the research and
  hold-out rules, with the fast path certified against replay. Recommended: yes, as its own stage after scheduled
  scans; open on which forward measures to show first and on the minimum event count.
