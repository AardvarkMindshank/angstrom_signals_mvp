# Lattice and Prism: the research workspace and the market scanner

Status: **revision 2, approved for stage 1 (5 November 2026)**. Step 2 of the agreed sequence (design the builder).
Revision 1 was reviewed by ChatGPT and Grok; their findings and the decisions taken are in §11. Revision 2 adds the
Group status truth table (§4.1), exact Set predicates and semantics (§4.2), backward compatibility (§4.5), the stage 1
fixtures (§6), a hold-out policy (§9), and moves History to its own research design (§5.4).

Nothing here changes the dashboard, Trend/Stretch/Flow, alerts as they work today, the Signal Matrix, existing saved
configurations, or the protected hold-out. The accepted Groups/Sets design changes only by the optional extensions in
§4, which need explicit approval.

Inputs: the clickable mockup (Groups, Sets, Prism run now, Prism scheduled scans), reviewed in three rounds;
`docs/research/visual_strategy_builders.md`; the accepted designs `groups_sets.md` (revision 4), `point_in_time.md`
and `library_completion.md`.

## 1. Names

| Name | What it is |
|---|---|
| **Angstrom Signals** | The product. Unchanged; no second product name. |
| **Lattice** | The research workspace inside it. Header: "Angstrom Signals · Lattice", subtitle "Research workspace". |
| **Groups**, **Sets** | As in `groups_sets.md`. |
| **Prism** ("Market scanner") | Runs a Set on assets: **Run now** and **Scheduled scans**. |
| **Strategies** | Later, shown greyed out. Specified separately from Drew's trading rules. |

Trademark and product-name checks are needed before any public use of "Lattice" and "Prism".

## 2. What the mockup reviews settled

**Groups.** Drag and drop or tap **+** (iPad). Roles Score / Condition / Levels / Context, each member with its own
timeframe and a source tag generated from it ("4H · last closed candle", "Latest score at the time", "Last published
flow day", "Live reading only"). Rule operands show which number they are and its scale (native value, standard
score −1..+1, Group score shown −100..+100, yes/no, label). Wrong types and out-of-scale thresholds block saving.
Rule order is visible and reorderable; first match wins; **Unknown** stops evaluation; **Neutral** (the
`otherwise` outcome) only when every rule is false. Blocks vs warnings: overlapping measures, price-only scores,
mixed timeframes, short or no history, partial asset coverage, an unused Condition member, a Score member reused in
a rule, overlapping OR rules. An auto-written description.

**Sets.** Groups and single signals; no Set score. A Group is used by its **outcome**, **score**, **condition state**
or **status**, chosen explicitly. The decision is an **ALL (AND)** box with optional **ANY (OR)** groups and a fixed
explanation of Yes / No / Unknown. Warnings for shared signals and sources.

**Prism.** Results separate the **answer**, **how sure** (with the decisive reason) and **data available**. Scheduled
scans on the Watchlist with a chosen schedule, alert on change, never on Unknown, existing channels. Strategies are a
greyed-out preview; nothing implies a position, order or fill.

## 3. Mapping to the accepted Groups/Sets design

| Mockup | Accepted design | Gap |
|---|---|---|
| Roles, transforms, three-valued `all`/`any`/`not`, counting contract | §3.1–3.4 | none |
| Group score −100..+100 | stored −1..+1 (§3.2), shown ×100 | display only; thresholds converted exactly (+30 → 0.30) |
| Ordered labels Bullish / Bearish / Neutral / Unknown | named conditions and `status`; words are presentation | **E1** |
| Set decision Yes / No / Unknown; standalone signal in a rule | Sets have no rules; standalone `context`/`levels` only | **E2** |
| Scales and range checks | type check at save (§3.4) | **E3** |
| "Trend on COIN" inside a Set run on another asset | not in the design | **E4**, not in stage 1 |
| Warnings | §3.5 diagnostics | additions only; never change results |

## 4. Extensions (for approval)

### 4.1 E1: Group outcomes

```json
"outcomes": {
  "version": 1,
  "rules": [
    {"id": "bullish", "label": "Bullish", "when": {"all": [{"score": {"gte": 0.30}}, {"member": "rsi_1d", "lte": 70}]}},
    {"id": "bearish", "label": "Bearish", "when": {"score": {"lte": -0.30}}}
  ],
  "otherwise": {"id": "neutral", "label": "Neutral"}
}
```

- `id`: `[a-z][a-z0-9_]{0,23}`, unique in the Group, stored in Set predicates. `label`: display text, ≤ 24
  characters, may be renamed in a new version without breaking Sets. Reserved ids, never user-defined:
  **`unknown`** and **`vetoed`**.
- Each `when` is an ordinary §3.4 rule (same engine, limits, counting contract).

**Step 1, ordered rules → raw outcome.**

| Rules in order | Raw outcome |
|---|---|
| rule *i* true, every earlier rule false | rule *i*'s id |
| the first rule that is not false is unknown | `unknown` (later rules are not evaluated) |
| every rule false | `otherwise` id |

A rule that is false because one of its `all` lines is false is false even if another of its lines is unknown
(the existing `all` contract), so it falls through.

**Step 2, Group status → published outcome.** The Group's `status` (§3.4 of `groups_sets.md`) gates the raw
outcome, so a label never hides a veto or a withheld score:

| Group status | Published outcome | Qualified |
|---|---|---|
| `ok` | raw outcome | no |
| `vetoed` (any veto active) | `vetoed` | no |
| `veto_unknown` (no veto active, at least one unknown) | raw outcome | **yes**: may be `vetoed` |
| `insufficient` (score withheld) | `unknown` | no |

The result carries `outcome`, `outcome_label`, `status` and `qualified`. The dashboard-style words for the starters
stay presentation: starters get no `outcomes` in this step.

### 4.2 E2: Set decision

```json
"decision": {
  "version": 1,
  "rule": {"all": [
    {"group": "trend", "outcome": {"eq": "bullish"}},
    {"not": {"group": "momentum", "outcome": {"eq": "bearish"}}},
    {"member": "sentiment_market", "gte": -20}
  ]}
}
```

**Predicates** (inside `all` / `any` / `not`; counting operators and `within_candles` event filters are not available in decisions yet and are refused at save):

| Shape | Value |
|---|---|
| `{"group": g, "outcome": {"eq": id}}` or `{"in": [ids]}` | compares the published outcome (ids only; `unknown` and `vetoed` may appear in `in`/`eq` only as described below) |
| `{"group": g, "score": {"gte"/"lte"/"between": …}}` | the Group score, stored −1..+1 |
| `{"group": g, "condition": c, "state": {"eq": s}}` | a named condition's state: confirmations `met` / `not_met`, vetoes `active` / `clear` |
| `{"group": g, "status": {"in": [statuses]}}` | the Group status, always known |
| `{"member": m, …}` | a standalone item with role `condition`, as Group member predicates |

**Semantics.**
- An outcome predicate is evaluated against the published outcome. If the outcome is **qualified**
  (`veto_unknown`), it is evaluated for both the raw outcome and `vetoed`: the same result for both gives that
  result, otherwise **unknown**. So `outcome eq bullish` is unknown under an unknown veto, but `outcome eq bearish`
  is definitely false when the raw outcome is bullish (it is false either way).
- An outcome of `unknown` makes every outcome predicate on it **unknown**, including `not` (unknown stays unknown).
  No predicate tests "is unknown": Unknown can never be turned into a decision. `vetoed` may be named in `eq` or
  `in` (for example "Trend is not vetoed" as `{"not": {"…eq": "vetoed"}}`).
- A condition whose state is unknown makes its predicate unknown. A score that is withheld makes score predicates
  unknown. A Group that failed to evaluate makes all its predicates unknown.
- Standalone items may take role `condition` in Sets; `context` items stay unusable in rules (refused at save).
- **Answer**: Yes = true, No = false, Unknown = unknown.
- **Decisive lines**: a sufficient reason taken from the rule tree, not a list of everything evaluated. For No,
  the false lines that make the result false; for Unknown, the unknown lines that could change it.
- A Set **without** a `decision` is **not scannable**: Prism refuses it with a reason. Run now shows its readings
  without an answer. It is never treated as No.
- Still no Set score, and no entry, exit, sizing or risk.

### 4.3 E3: field descriptions and range checks

- A field table next to the signal definitions (`signal_library/fields.py`, keyed by signal id and version): for
  each readable field path, its type (number, label, yes/no, events), unit and, where fixed, its range (RSI 0..100,
  standard score −1..+1, sentiment −100..+100). Fields without a fixed range (MACD in ATRs, ETF flows in US$) carry
  a unit only. Signals not in the table are checked structurally only, as before.
- The **backend validator** (`signal_groups/validate.py`) enforces: the field path exists, the comparison matches the
  type, thresholds sit inside a fixed range. The editor repeats the checks for display only.
- Display thresholds are converted exactly before storing (Group score +30 → 0.30, as `Fraction`).
- No calculation or signal version changes. The table is documentation that no calculation reads, so it is kept
  outside `CODE_FILES`: the certified code hash and the certification record are unchanged (tested).

### 4.4 E4: fixed-subject Set lines (named now, not in stage 1)

A Set item may pin a subject ("Trend on COIN") while the rest of the Set runs on the scanned asset. Both are read at
the same cutoff T and both appear in the replay record. Stateless and testable. Specified with the stage that needs
it.

### 4.5 Backward compatibility and immutable versions

- `outcomes` and `decision` are additive optional keys under `angstrom.group/1` and `angstrom.set/1`. A document
  without them validates, evaluates and hashes exactly as today (keys absent, never null).
- Every existing starter, example and stored version keeps its content hash and its result (golden tests).
- Adding outcomes or a decision creates a **new version** of that configuration; old versions are untouched.
- A Set embeds a Group **version**. An outcome predicate on an embedded version without `outcomes` is refused at
  save with "this Group version has no outcomes; embed a newer version".
- Lineage version is unchanged. Live Trend/Stretch/Flow, alerts and the Signal Matrix do not read these keys.

## 5. Prism

### 5.1 Run now

- Pick a Set (with a decision) and assets (default: the Watchlist).
- **Now** uses the live path with confirmed candles. **A past date** uses the point-in-time reconstruction in
  `DISPLAY` mode. The results page says which path it used.
- One row per asset: each line's reading (label and score for Groups, value with its scale for signals), answer,
  how sure with the decisive reason, data available.
- No statistics, returns or bulk export (`point_in_time.md` §6, §8).

### 5.2 Scheduled scans

**A scan**: owner, pinned Set version, the Watchlist, schedule, alert mode, channels, paused.

**Schedules.**
- *Each candle close* (4H, 1D, 1W). The cutoff **T** is the candle's close, not the worker tick. Shares use the
  library's share calendar (16:00 New York), shown on the scan, not the dashboard's 16:30.
- *Set times*: up to 4 a day in the user's time zone, every day, weekdays or chosen days; T is the set time.
- A warning when the schedule is faster than the Set's slowest-changing member.

**Running.** Inside the existing worker (`run_alerts.py`, every 5 minutes):
1. the existing alert and digest work runs first; Prism uses the time left, at most 4 minutes of the 15;
2. due scans are claimed atomically (one claim per scan and cutoff), oldest due first, fairly across users;
3. each is evaluated at T through the point-in-time path and its **run record** is stored with input hashes and code
   identity;
4. a failure is recorded for that scan only and does not stop the others or count as an answer;
5. a scan that did not fit waits for the next tick and says how late it ran.

**Records, not re-runs.** The stored run record is what the scan said. A later reconstruction ("check past dates")
can differ if a provider revised data; the page labels actual scans and reconstructions differently.

**Alerts.**
- Latch per (scan, asset). The first Yes ever observed alerts once. Only a confirmed **No** releases the latch;
  **Unknown** and failed runs neither open nor release it.
- A new Set version on the scan keeps the latches, with the version change noted; the user can reset them.
- "Every run while Yes" is off unless chosen.
- Notifications are idempotent: one per (scan, asset, cutoff), whatever retries happen.
- Delivery: in-app (`user_notifications`, new type `prism`), instant email if on, otherwise a Prism section in the
  daily digest. Discord and Telegram later.

**Storage** (new re-runnable SQL file, owner-only, writes through security-definer functions):
`prism_scans`, `prism_scan_runs` (kept 90 days), `prism_scan_latches`, and a claim table or claim column for (scan,
cutoff).

**Limits for the first build**: 5 active scans per user, Watchlist only, 4 minutes per tick after existing work,
90-day run history.

### 5.3 Results page

Latest run grouped as New Yes (alerted) · Still Yes · Couldn't decide · No (collapsed). "Check past dates" is a
display reconstruction, at most 90 steps, with answers only: no returns or statistics.

### 5.4 History (separate research design, not in this build)

The useful question is "across all history, when would this Set have turned Yes, and what did the price do
afterwards?". Both reviews approve the concept, not an implementation. It gets its own research design covering:
eligibility (members and timeframes with history in the permitted period), event transitions, forward horizons (for
example median return at 5 and 20 daily candles and the share positive, against all dates for that asset), overlap
handling, minimum events (for example 30, below which only the count is shown), recorded tries, no best-setting
search, and the causally certified fast path.

Direction for that design: a **research job** (CI or background) computes the study under the research rules and
§9's hold-out policy; Prism **displays stored results** and never computes statistics in a page load.

### 5.5 Linking evaluations

Same asset and moment: one Set. Another asset at the same moment: E4. Sequences over time ("A then B within N days"):
the strategy layer's state machine, as an alert-only strategy. No action that runs another evaluation.

## 6. Stage 1 fixtures (executable, synthetic data and frozen pre-hold-out data only)

**Outcomes (E1).**
1. Rule 1 true → its id; rule 1 false and rule 2 true → rule 2's id; all false → `otherwise`.
2. Rule 1 unknown and rule 2 true → `unknown` (not rule 2).
3. Rule 1 false because one `all` line is false while another is unknown → falls through to rule 2.
4. Reordering rules changes the outcome where two rules overlap (priority is the order).
5. Status `vetoed` → `vetoed`; `insufficient` → `unknown`; `veto_unknown` → raw outcome, qualified.
6. Reserved ids refused; duplicate ids refused; renaming a label does not change any Set result.

**Set decisions (E2).**
7. Outcome `eq bullish` under `veto_unknown` with raw bullish → unknown; `eq bearish` with raw bullish under
   `veto_unknown` → false.
8. Active veto → `eq bullish` false.
9. `not` of unknown stays unknown; an outcome of `unknown` makes predicates unknown.
10. Definite No: one necessary line false while another input is missing → No, with the false line decisive.
11. Unknown: no line false, one missing → Unknown, naming the missing line.
12. ANY group: one true → true; all false → false; none true and one unknown → unknown.
13. A `context` item in a decision refused; a `condition` standalone item accepted.
14. Set without a decision: not scannable.
15. Outcome predicate on an embedded Group version without outcomes refused.

**Scales (E3).**
16. Field table for the starter members and the example Set; every fixture value lies inside its stated range.
17. One out-of-range value per fixed field refused (for example 70 on a −1..+1 standard score).
18. Type mismatches refused (a yes/no field compared with a number; a label compared with `gte`).
19. Group score +30 stored as exactly 0.30.

**Compatibility.**
20. Every starter, example and stored test document without the new keys: identical content hash and identical
    evaluation (golden).
21. Live Trend/Stretch/Flow, the v2 overlap job and the live golden snapshot unchanged; certification results
    identical after regeneration.

## 7. The editor (Lattice UI)

One small custom component, built like the existing chart component (`lw_chart.js` / `lw_chart.py`): signal panel,
drop zones, HTML5 drag and drop plus tap-to-add. It returns the edited document; validation, warnings, descriptions
and saving stay in Python. Icons with hover explanations; strings collected for later translation. Saving uses the
existing versioned storage.

## 8. Build order

Each stage on its own branch with a report, CI green, merge only on approval.

1. **Engine extensions E1–E3**, headless, with the §6 fixtures.
2. **Prism Run now**, admin-only: Set and asset pickers and the results table. Starters have no outcomes, so it is
   first used with an admin-authored Set deciding on scores, condition states or outcomes of admin-made Groups.
3. **Scheduled scans**: SQL, worker integration, alerts, digest section, results page; a plain form to choose a
   saved Set, schedule and channels (no drag and drop needed). Admin-only, then all users.
4. **Editor**: the drag-and-drop component and the Group and Set editors.
5. **Strategies**: separate specification from Drew's rules, script and examples.

History (§5.4) is a separately approved research stage; its place relative to the editor is decided when its design
is approved. E4 is specified with the stage that needs it.

## 9. Hold-out policy

The hold-out (`holdout-spec-v1`, data from 30 October 2024 onwards) protects **Angstrom's own research claims**: a
signal, threshold or starter is only called "researched" with evidence from data that was not used to design it. It
is not a permanent limit on what users can analyse.

1. **During development (now):** untouched. No events, outcomes, statistics or tuning on it, in any stage of this
   plan.
2. **One certification, pre-registered:** when the research layer is ready, an owner-approved certification run.
   Before the hold-out is accessed, the models, configurations, thresholds, evaluation procedure and pass/fail
   criteria are frozen and recorded. The result is reported whether it passes or fails.
3. **Release by separate decision:** after certification the period is no longer unseen validation data. It becomes
   ordinary research history only through a separate, explicit, owner-approved release decision, never
   automatically. Live observations after that provide forward validation, but are not automatically equivalent to a
   new independent hold-out.
4. **Users' own studies**, once released, may use all available history, labelled as exploratory, with the
   fitting-the-past guardrails (event counts, recorded tries, no best-setting search).

Changing the hold-out itself, including the certification and release steps, needs its own design note and approval.
Until then point 1 applies.

## 10. Not in scope

Strategies, ladders, positions, orders, fills; History implementation; statistics on scans; assets outside the
Watchlist; Discord and Telegram; Set scores; E4; any change to the dashboard, Trend/Stretch/Flow, existing alerts or
the Signal Matrix.

## 11. Review decisions (revision 1 → 2)

ChatGPT and Grok reviewed revision 1. Decisions taken with the owner:

| Question | Decision | Change in revision 2 |
|---|---|---|
| A. Outcomes | approved with changes | stable ids; reserved `unknown` and `vetoed`; status gate and qualified outcomes (§4.1) |
| B. Set decision | approved with changes | exact predicates and semantics; decisive lines as a sufficient reason; no decision = not scannable (§4.2) |
| C. Fields and ranges | approved | enforced in the backend validator; field paths checked (§4.3) |
| D. Point-in-time scans | approved with changes | run records with provenance are the record; no promise of exact re-runs; T = candle close; library share calendar (§5.2) |
| E. Latch | approved | first Yes alerts once; failed runs do not reset; Set-version changes (§5.2) |
| F. Limits | approved with changes | Prism after existing worker work; atomic claims; idempotent notifications; failure isolation (§5.2) |
| G. Build order | approved | History removed from the sequence; plain scan form in stage 3 (§8) |
| H. History | concept approved | separate research design; stored results displayed, never computed in a page (§5.4); hold-out policy (§9) |
| I. Linking | approved | fixed subjects named E4, not in stage 1 (§4.4, §5.5) |

Both reviews conditionally approve stage 1 once revision 2 contains §4.1, §4.2, §4.5 and §6.
