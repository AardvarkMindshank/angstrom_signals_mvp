# Design proposal: Signal Groups and Signal Sets (revision 4)

Status: **proposal for review**. No application code. The examples in `docs/design/examples/` are checked by
`tests/test_design_examples.py` (references, structure, rule paths against real signal outputs, snapshot hashes);
that is design-time checking, not the product validator or evaluator. The counting worked cases
(`examples/rule_fixtures.json`) and sharing scenarios (`examples/sharing_fixtures.json`) are executed against
test-only references of sections 3.4.1 and 7; transform fixtures
are checked for shape and range only, until the evaluator exists. Revisions 2–4 answer the reviews on PR #1; section 12 maps each finding to the change.

```
Signal Library ──► Signal Groups ──► Signal Sets ──► Analysis Workspace / Strategy Builder
 (built, v3)        (this design)     (this design)    (later; not designed here)
```

## 1. Scope

In scope: what a Group and a Set are; how they are evaluated, stored, versioned, copied and shared; starter
templates. Out of scope: user interface, the Workspace, strategies, backtests, worker changes, storing results.
Non-goals: no universal composite score, no fixed membership, no averaging of incompatible values, no treating
correlated signals as independent confirmation, no tuning on the protected hold-out.

## 2. Terms

| Term | Meaning |
|---|---|
| Signal | A library observation, referenced by a `SignalRef` (id, pinned version, timeframe, params). Exists today. |
| Member | A signal inside a Group with a key, role, and (for score members) weight and transform. |
| Group | A named, versioned configuration answering one analytical question from its members. |
| Set | A named, versioned collection of pinned Groups plus standalone signals and market context. |
| Category | An editable, descriptive label on a member (trend, structure, volume...). Used for display only. |
| Lineage | The analytical inputs a signal is computed from (`price`, `volume`, `derivatives`, `tftc_btc_etf`...), recorded by input, not by provider (price is `price` whether it comes from Yahoo or Coinalyze). Fixed, versioned, not editable. Used for **source separation** only. |

Naming (D1, decided): social groups are **Communities** in the app (PR #2; tables unchanged). "Group" in the app
means a Signal Group. New tables use the `analysis_` prefix.

## 3. A Group

A Group is a JSON document, `schema: "angstrom.group/1"`. Examples: `examples/group_trend_confirmation.json`,
`examples/group_reversal_evidence.json`.

### 3.1 Roles and unavailable data

| Role | Purpose | Weight | When the signal is unavailable (missing, stale, insufficient, error) | May be used in rules |
|---|---|---|---|---|
| `score` | Contributes to the score through a transform | ≥ 0 | `exclude` or `neutral` (below) | yes |
| `condition` | Evidence for rules | – | its predicates are **unknown** (no other option) | yes |
| `levels` | Prices or zones | – | its predicates are **unknown**; levels are listed as unavailable | yes |
| `context` | Shown for interpretation | – | shown with its status | **no** (the validator refuses it) |

Nothing unavailable is ever turned into a reading. A genuine observation of "nothing" (no divergence in the
window, a `mixed` label mapped to 0) is observed data; an unavailable signal is not.

### 3.2 Score and coverage (exact arithmetic)

`score: null` means the Group has no score. Otherwise:

- Weights are finite numbers 0 ≤ w ≤ 1000, compared exactly (decimal → rational). **Enabled** members have w > 0;
  w = 0 disables a member (shown, not counted). A non-null score needs at least one enabled score member.
- `W_enabled` = sum of enabled weights. `W_observed` = sum over enabled members with an available signal **and** a
  known transformed value. A member is *not observed* when its signal is unavailable **or** its transform returns
  unknown (unlisted label, missing field, null, non-finite); both cases follow the member's policy the same way:
  `exclude` drops it, `neutral` imputes 0 and adds its weight to `W_imputed`. The result says which case applied
  (`unavailable` or `transform_unknown`).
- `observed_coverage = W_observed / W_enabled`. `min_coverage` is an exact fraction `{"num": 2, "den": 3}`; the
  score is computed only when `W_observed × den ≥ W_enabled × num`. Imputed weight never counts towards coverage.
- When computed: `score = Σ(w·c) / (W_observed + W_imputed)` with neutral members contributing c = 0;
  with only `exclude` members missing this is the mean over observed members. Always in [−1, 1].
- Withheld scores say why: `no_enabled_members`, `below_min_coverage` (with both weights), `all_unavailable`.
- The result lists every member: native value, transformed value, weight, weight share, and whether it was
  observed, excluded, imputed or disabled.

Worked cases for three equal weights (w = 1) and `min_coverage` 2/3, all `exclude`:

| Available | Values | W_observed / W_enabled | Score |
|---|---|---|---|
| 3 | up, up, down (+1, +1, −1) | 3/3 | +1/3 |
| 2 | up, mixed (+1, 0) | 2/3 → meets 2/3 exactly | +1/2 |
| 1 | up | 1/3 | withheld (below_min_coverage) |
| 2 + 1 `neutral` missing | up, up | observed 2/3, imputed 1 | (1+1+0)/3 = +2/3 |

`meaning` is a sentence saying what +1 and −1 mean. A typed `semantics` field (`{"kind": "direction",
"horizon": "swing"}`) is reserved for future Set scores and not used now.

### 3.3 Transforms (versioned, deterministic, finite)

Every transform maps a native value to a number in [−1, 1] or to **unknown**. Non-finite inputs (NaN, ±∞), nulls,
missing field paths and unlisted labels give unknown, never 0. Fixtures with expected outputs:
`examples/transform_fixtures.json`.

| Transform | Parameters (v1) | Rule |
|---|---|---|
| `map` | `field?` (typed path), `map` {label: number in [−1,1] or null} | label → its number; unlisted or null → unknown |
| `bands` | `field?`, `bands` [{`from`, `to`, `value`}] | `from` inclusive, `to` exclusive, `null` = unbounded; bands must cover the line without gaps or overlaps (validator) |
| `clip` | `field?`, `low`, `high` (finite, low < high), `invert?` | 2·(x − low)/(high − low) − 1, clipped to [−1, 1]; `invert` negates |
| `events` | `up_types`, `down_types` (and/or `up_kinds`/`down_kinds` with `direction`), `within_candles?` | only active confirmed events count (developing, expired and invalidated never do); up only → +1, down only → −1, none → 0 (observed), both → 0 with a `conflicting_events` flag |

Adaptive transforms (percentile, z-score) are deferred: they need an agreed calibration window and reproducible
history; the source of that history (stored results or recomputation from candles) is a later decision.

### 3.4 Rules: bounded, three-valued

A rule is a JSON expression evaluated to **true, false or unknown**.

- Predicates on a member (`member`, optional typed `field` path such as `support.0.distance_atr`): `eq`, `in`,
  `gte`, `lte`, `between`, `exists`; `events` filters (`type_in`, `kind_in`, `direction`, `within_candles`,
  `include_developing` default false). A path that does not resolve (missing key, index out of range, null) or a
  member that is unavailable gives **unknown**, never false. Comparing incompatible types is refused at save time.
- Predicates on the Group's score (`{"score": {"gte": 0.5}}`): unknown when the score is withheld.
- `all`: false if any false; else unknown if any unknown; else true. `any`: true if any true; else unknown if any
  unknown; else false. `not`: swaps true and false; unknown stays unknown.
- `count_at_least: k` and `count_distinct_sources_at_least: k` take a list `of` items; each item is any expression
  (a predicate or a compound). Their exact contract is section 3.4.1.
- `within_candles: N` is counted in the member's own timeframe: the number of closed candles from the candle that
  confirmed the event to the last closed candle at the evaluation cutoff (0 = confirmed on the last closed candle).
- Limits: ≤ 30 members, ≤ 20 conditions, ≤ 50 predicates, nesting depth ≤ 6, document ≤ 64 KB. No scripting.

#### 3.4.1 Counting contract

1. **Support set.** Each item's support set is every signal instance referenced anywhere inside it (all predicates,
   whichever of them made it true, so the count is conservative). A `score` predicate's support set is the
   instances of all enabled score members. Instance = the `SignalRef` instance key (id, version, timeframe, params).
2. **Clusters.** Items are merged into clusters: for `count_at_least`, items whose support sets share an instance
   (transitively); for `count_distinct_sources_at_least`, items whose lineage root sets share a root, where an
   item's roots are the union of its instances' roots under the pinned lineage version.
3. **Cluster value.** True if any item in it is true; otherwise unknown if any item is unknown; otherwise false.
   So an unknown item that shares an instance (or a source) with a true one never adds a second count.
4. **Result.** With t true clusters and u unknown clusters: true if t ≥ k; false if t + u < k; otherwise unknown.
5. The validator refuses k larger than the number of items; a rule whose items can never form k clusters (for
   example every item price-derived with `count_distinct_sources_at_least: 2`) is refused as unsatisfiable.

Worked cases (fixtures in `examples/rule_fixtures.json`):

| Rule | Items (value; support; roots) | Clusters | Result |
|---|---|---|---|
| `count_at_least: 2` | A = RSI div (true; {rsi}; price), B = same predicate again (true; {rsi}) | {A,B} → true | 1 < 2 → **false** |
| `count_at_least: 2` | A = any(RSI div, MACD div) (true; {rsi, macd}), B = all(RSI div, zone near) (true; {rsi, zones}) | shared rsi → {A,B} → true | **false** |
| `count_at_least: 2` | A = RSI div (true; {rsi}), B = zone near (unknown; {zones}) | {A} true, {B} unknown | 1 < 2 ≤ 2 → **unknown** |
| `count_distinct_sources_at_least: 2` | A = RSI div (true; price), B = zone near (unknown; price) | shared price → {A,B} → true | 1 < 2 → **false** |
| `count_distinct_sources_at_least: 2` | A = RSI div (true; price), B = ETF flows 5-session sum ≥ 0 (unknown; tftc_btc_etf) | {A} true, {B} unknown | **unknown** |
| `count_at_least: 2` | A (false; {rsi}), B (false; {macd}), C (unknown; {zones}) | three clusters | 0 + 1 < 2 → **false** |

States: a confirmation is **met / not met / unknown**; a veto is **active / clear / unknown**. The Group's overall
`status` is `ok`, `vetoed` (any veto active), `veto_unknown` (no veto active, at least one unknown) or
`insufficient` (score withheld). Every part is still shown; a met confirmation under `veto_unknown` is reported as
qualified, never as clean. Example (Trend Confirmation): bullish score and 4-hour momentum up, daily regime
unavailable → `bullish_confirmed` met, `ranging_veto` unknown, status `veto_unknown`.

### 3.5 Diagnostics (never change the score)

- **Agreement**: weighted share of enabled, observed score members whose contribution has the score's sign (zero
  contributions listed separately).
- **Source separation**: the lineage components behind the agreeing members. Distinct sources are not statistical
  independence (separate feeds can be strongly correlated); the diagnostic only shows whether agreement comes from
  one source or several. When every score member derives from `price`, the result says agreement is consistency
  between views of one source.
- **Conflicts within a category**: categories whose members point opposite ways are flagged; weights are untouched.
- **Duplicates**: the same signal instance used twice in a Group (or across Groups in a Set) is flagged and counted
  once in every count.
- **Known redundancy**: pairs the library's development check found to agree heavily (trend vs momentum ≈ 80% when
  both directional). A static, versioned table until history exists.
- **Coverage and timing**: observed/imputed/excluded members, oldest `observed_at`, newest `available_at`.

### 3.6 Lineage

Lineage is a versioned table in the Groups layer keyed by signal id (`examples/lineage.json`, version 2). It records
analytical inputs, not providers: every candle signal has `price`; CMF adds `volume`; relative volume is `volume`
only; `positioning.oi_price` and `positioning.liquidation_levels` use price as well as derivatives data, so they
are `derivatives` + `price`; reported liquidations are `derivatives`; ETF flows and stablecoin supply are their own
roots. Disjoint roots mean **separate sources**, nothing more: they are a necessary condition for treating evidence
as independent, not proof of it. Each Group and Set version records the lineage version it was validated with
(`lineage_version`), and evaluation uses that version, so a later lineage change cannot silently alter a pinned
configuration's counts. Users cannot edit lineage; a new library signal must be added before Groups can use it.

## 4. Time and provenance

An evaluation request is `{subject, as_of, data_mode}`:

- `data_mode: "live"` (the first build): `as_of` = now; closed candles only; latest revisions of published data;
  backfilled history allowed and flagged.
- `data_mode: "point_in_time"` (defined now, refused until supported): every input must have
  `available_at ≤ as_of`, use only revisions first seen by `as_of`, exclude backfilled values, and load candles cut
  at `as_of`. One cutoff applies to the asset and to market context. Until every signal and cache in a Group
  supports the cutoff, the evaluator returns `unsupported` instead of approximating. A pinned configuration does
  not pin data.
- ETF context with `point_in_time: false` is labelled "current descriptive context only"; the validator refuses it
  in point-in-time evaluations.

Each member in a result keeps its full `SignalResult` metadata: status, confirmation, `observed_at`,
`available_at`, `backfilled`, provenance and a pointer to its evidence. The Group result adds `as_of`, `data_mode`,
`evaluated_at`, the oldest `observed_at` and the newest `available_at` across its inputs.

## 5. A Set

`schema: "angstrom.set/1"` (`examples/set_multi_timeframe.json`):

- `groups`: each entry has the **embedded snapshot** of a Group version (canonical for evaluation) and its
  provenance `{source_config, source_version, source_owner, content_sha256, captured_at, audience_ceiling}`. The
  reference is kept for attribution and "upgrade available"; editing the source never changes the Set.
- `standalone` and `market_context`: library signals, same roles as Group members (`context` or `levels`).
- `score`: always `null` in the first build (D7 deferred). Diagnostics report signals and lineage shared across
  Groups, so a Set cannot hide duplicated evidence.

A Set is an analysis configuration, not a strategy: no entry, exit or risk rules.

## 6. Storage, versions and publication

Five tables:

```
analysis_configs          id uuid PK, kind ('group'|'set'), owner_id (null = Angstrom starter), current_version int,
                          copied_from_config, copied_from_version, copy_ceiling (set once at copy; null for originals),
                          archived bool, created_at, updated_at
analysis_config_versions  (config_id, version) PK, schema text, body jsonb (≤ 64 KB), content_sha256 (computed by
                          the server), lineage_version, capture_ceiling (computed by the server at save),
                          dependencies (source config, version, effective audience at capture), created_by,
                          created_at, change_note                                                  -- immutable
analysis_version_publications (config_id, version) PK, audience ('private'|'communities'|'public'), updated_at,
                          updated_by                                                               -- mutable via functions
analysis_version_shares   (config_id, version, user_group_id) PK, shared_by, shared_at            -- mutable via functions
analysis_publication_log  append-only record of every publish, share, narrowing and archive
```

- **Writes only through security-definer functions**; no direct insert/update/delete grants:
  `save_config_version(config_id, expected_version, body, note)` locks the config row, checks
  `expected_version = current_version` (else `conflict`), inserts `current_version + 1`, updates
  `current_version`, all in one transaction; `(config_id, version)` is unique.
- **Version content is immutable** (no update or delete of `analysis_config_versions`, ever). Who may read a version
  is publication metadata in separate tables, changed only by the owner through functions and logged. Archiving hides a config from lists but keeps every
  version, so pins and copies stay valid. Hard delete is only for a private config that nothing references.
- **Publication is per version.** A new version is private. Publishing version N (public, or to chosen
  communities) never publishes earlier versions. A config row is visible to someone who can read any of its versions.
- **Owner only**: only the owner saves versions, publishes, shares or archives. Starters (owner null) are written
  only by the service role.
- **Community access** = leader (`user_groups.leader_id`) or member (`group_members`). Leaving or being removed
  ends access to that community's versions immediately.

## 7. Copying, embedding and redistribution (strict capture ceilings)

**Audiences** are sets of readers: `owner` (private), a set of communities, or `public`. Intersection: public ∩ X =
X; communities A ∩ communities B = A ∩ B (empty → owner); anything ∩ owner = owner. X ⊆ Y means every reader of X
can read Y.

- **Effective audience of a source version** = its current publication audience, further limited by that version's
  own `capture_ceiling` (and its config's `copy_ceiling` when it is a copy). An unpublished version's effective
  audience is `owner`.
- **Capture.** Copying a version, or saving a Set version that embeds it, requires the caller to be inside its
  effective audience at that moment; otherwise it is refused. The server records each dependency with its effective
  audience **at capture**, and computes the new version's `capture_ceiling` = intersection of those captured
  audiences (and of the config's `copy_ceiling`, when it is a copy). Both are immutable parts of the version.
- **Strict in v1: a capture ceiling never rises.** Publishing or sharing a version to audience X requires
  X ⊆ its `capture_ceiling` **and**, for every dependency, X ⊆ that source version's effective audience **now**.
  So a Group that was private when a Set version captured it keeps that Set version owner-only, even after the
  Group is published. To redistribute, the owner saves a **new Set version**, which captures the Group again with
  its new audience. Narrowing a source still blocks later publication or widening of anything that embeds it.
- **Copies.** A copy's `copy_ceiling` is the source version's effective audience at copy time; every later version of
  the copy is limited by it, because its content derives from the captured content.
- **Already published stays published.** Narrowing or archiving a source does not withdraw versions that were
  published while authorised (content already shared cannot be recalled); it blocks new captures, publications and
  widenings. The publish screen says this before anyone publishes.
- **Server-side enforcement.** All of this is computed inside the database functions (`copy_config`,
  `save_config_version`, `publish_version`, `share_version`) from stored rows: publication audiences, shares,
  community membership (leader or member) and the recorded capture data. Submitted provenance and hashes are never
  proof of permission: the server re-reads each source version, recomputes `content_sha256`, rejects a mismatch and
  stores the provenance itself.

Worked scenarios (fixtures in `examples/sharing_fixtures.json`, executed against a test-only reference of these rules):

| Scenario | Result |
|---|---|
| Owner embeds their own **unpublished** Group v1 in Set v1, later publishes Group v1 publicly, then tries to publish Set v1 publicly | refused: Set v1's capture ceiling is `owner` |
| Owner then saves Set v2, re-capturing the now-public Group v1, and publishes Set v2 publicly | allowed |
| Bob, a member of community A, embeds a Group shared only with A, then publishes his Set to A / to community B / publicly | A allowed; B refused; public refused |
| Group shared with A and B; Bob (in A) captures it; publishes his Set to A and B | allowed (within the source's audience) |
| Carol, not in A, tries to embed a Group shared only with A | refused at capture |
| Group public at capture; later narrowed to A; Set version published publicly / to A | public refused; A allowed |
| Another owner's unpublished Group embedded by anyone else | refused at capture |

**Implementation acceptance requirement.** The build must include real Supabase tests of the row-level security and
the functions above, run against a Postgres database with the actual SQL (two signed-in test users, communities,
leader and member, anonymous): every scenario in the table, direct table writes refused for signed-in users,
version rows never updatable, a forged hash refused, concurrent saves resolved by `expected_version`, leaving a
community ending access, and unpublished earlier versions unreadable. The design-time reference in this PR does not
replace those tests.

## 8. Evaluation and resources

On demand, as the Signal Library; nothing new in the worker. A Group costs the library signals it uses (cached,
shared across Groups in a Set); intraday members fetch Yahoo candles for that asset only. Results are not stored
in the first build.

## 9. Later (not built now)

History of results (alerts on Groups, live redundancy, adaptive transforms, backtests); AI suggestions as a
proposed new version awaiting the owner's approval; the Strategy Builder referencing a Set version with its own
entry, exit and risk schema; Set scores with typed semantics and explicit Group weights.

## 10. Starter templates (descriptive, not validated trading rules; thresholds are conventions, not tuned)

- **Trend Confirmation**: score = daily trend, 4-hour trend and daily swing structure (equal weights, exclude when
  missing, min coverage 2/3). All three derive from price, which the diagnostics state. 4-hour momentum is a
  confirmation condition (it repeats trend, so it is not a second vote, and not independent confirmation either).
  Daily regime is a condition role controlling the `ranging_veto`; when it is unavailable the veto is unknown.
- **Reversal Evidence**: no score. A bullish (bearish) setup needs at least two of three items: an active RSI or
  MACD divergence (one compound item: both come from the same price swings), a CHoCH within 20 candles, price within
  1 ATR of a support (resistance) zone. Their support sets are disjoint, so they form three clusters under
  `count_at_least`; all are price-derived, so the condition is labelled corroborating, and
  `count_distinct_sources_at_least: 2` would be refused as unsatisfiable. CMF is context.
- **Multi-Timeframe Analysis** Set: both Groups embedded as snapshots, timeframe alignment and 4-hour levels as
  standalone, Bitcoin ETF flows as current market context; no Set score.

## 11. Decisions for approval

| # | Decision | Proposal (revision 4) |
|---|---|---|
| D1 | Names | **Decided**: Communities (social); Signal Groups / Signal Sets |
| D2 | Storage | Five tables (configs, immutable versions, publications, shares, publication log); per-version publication; function-only atomic writes (section 6) |
| D3 | Sets and others' Groups | Embedded snapshots; strict capture ceilings that never rise (re-capture in a new version to redistribute); server-side checks at capture/publish/widen; real Supabase RLS and function tests required at build (section 7) |
| D4 | Unavailable data and coverage | Role-specific policies; exact coverage arithmetic; imputed never counts as observed (sections 3.1–3.2) |
| D5 | Rule language | Bounded JSON, three-valued logic, typed paths, the counting contract with instance and source clusters, explicit event timing (section 3.4) |
| D6 | Transforms | `map`, `bands`, `clip`, `events` v1 as specified with fixtures; adaptive transforms deferred (section 3.3) |
| D7 | Set scores | Deferred: always null in the first build |
| D8 | First build | Admin-only validator, evaluator and starters, live mode only, synthetic/development fixtures, hold-out untouched; storage SQL accepted only with real Supabase RLS and function tests (section 7) |

## 12. Review findings and changes (PR #1)

| Finding | Change |
|---|---|
| 1 Families are not independence | `family` replaced by descriptive `category` plus fixed `lineage` (3.6); a source-counting operator (renamed in revision 3); duplicates count once; conflicts flagged; starter rule relabelled corroborating (10) |
| 2 Snapshots and permissions | Audience ceilings, checks, provenance with hash, revocation (7); Set example embeds snapshots |
| 3 Version publication and invariants | Per-version publication, function-only atomic writes, immutability, owner-only, leader + member access (6) |
| 4 Roles vs rules, unknown vetoes | Role table (3.1); regime is a `condition`, zones `levels`; three-valued logic and statuses (3.4) |
| 5 Coverage arithmetic | Exact definitions, fraction threshold, worked cases (3.2) |
| 6 Set scores | Deferred (D7) |
| 7 Point-in-time metadata | Request `as_of` and `data_mode`, full per-member metadata, `point_in_time` refused until supported, ETF live-only label (4) |
| 8 Transform schemas | Parameters, boundaries, unknowns, conflicts, fixtures (3.3) |
| 9 Example tests | Structural checks: roles and policies, rule walk with paths resolved on real outputs, transforms, coverage fraction, starter aliases and versions, snapshot hashes, lineage coverage, fixture ranges |
| R3-1 Ceilings from the source version's audience | Section 7 rewritten: effective audience = publication ∩ ceiling; private sources owner-only; widening rechecked against current source audience; all computed server-side, submitted hashes never trusted |
| R3-2 Sources are not independence | Operator renamed `count_distinct_sources_at_least`; diagnostic renamed source separation and qualified; lineage records inputs not providers (`positioning.oi_price` and `.liquidation_levels` now include `price`); `lineage_version` pinned per Group/Set version |
| R3-3 Counting compound rules | Section 3.4.1: support sets, instance and source clusters, cluster values, three-valued bounds, unsatisfiable rules refused; worked cases and `examples/rule_fixtures.json` |
| R3-4 Immutable content vs publication | Audience moved out of the version row into publication and share tables plus an append-only log |
| R3-5 Neutral with an unknown transform | Section 3.2: not observed = unavailable or transform unknown; both follow the member's policy |
| R4-1 Captured ceilings contradiction | Strict capture ceilings: immutable per version, never rise; redistribution needs a new Set version that re-captures; worked scenarios incl. cross-community, executed against a test-only reference |
| R4-2 Table count and RLS tests | Section 6 lists the five tables; real Supabase RLS/function tests made an implementation acceptance requirement (section 7) |
| 10 CI gate | `checks.yml` shared jobs; required failures fail the job; optional live-feed checks labelled; `pr-checks.yml` runs read-only with artifacts (forks included); `v2-checks.yml` publishes on push |
