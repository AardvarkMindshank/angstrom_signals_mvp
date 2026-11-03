# Design proposal: Signal Groups and Signal Sets (revision 2)

Status: **proposal for review**. No application code. The examples in `docs/design/examples/` are checked by
`tests/test_design_examples.py` (references, structure, rule paths against real signal outputs, snapshot hashes);
that is design-time checking, not the product validator. Revision 2 answers the review on PR #1; section 12 maps
each finding to the change.

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
| Lineage | The raw data sources a signal is computed from (`price`, `volume`, `derivatives`, `tftc_btc_etf`...). Fixed by the library, not editable. Used for independence. |

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
- `W_enabled` = sum of enabled weights. `W_observed` = sum over enabled members with an available signal and a
  non-null transformed value. `W_imputed` = sum over unavailable members whose policy is `neutral`.
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
- `count_at_least: k` over a list: duplicates of the same signal instance count once. True if trues ≥ k; false if
  trues + unknowns < k; else unknown.
- `count_independent_at_least: k`: like `count_at_least`, but true predicates whose signals share any lineage root
  are merged and count once (section 3.6). The same three-valued bounds apply.
- `within_candles: N` is counted in the member's own timeframe: the number of closed candles from the candle that
  confirmed the event to the last closed candle at the evaluation cutoff (0 = confirmed on the last closed candle).
- Limits: ≤ 30 members, ≤ 20 conditions, ≤ 50 predicates, nesting depth ≤ 6, document ≤ 64 KB. No scripting.

States: a confirmation is **met / not met / unknown**; a veto is **active / clear / unknown**. The Group's overall
`status` is `ok`, `vetoed` (any veto active), `veto_unknown` (no veto active, at least one unknown) or
`insufficient` (score withheld). Every part is still shown; a met confirmation under `veto_unknown` is reported as
qualified, never as clean. Example (Trend Confirmation): bullish score and 4-hour momentum up, daily regime
unavailable → `bullish_confirmed` met, `ranging_veto` unknown, status `veto_unknown`.

### 3.5 Diagnostics (never change the score)

- **Agreement**: weighted share of enabled, observed score members whose contribution has the score's sign (zero
  contributions listed separately).
- **Independent support**: the lineage components behind the agreeing members. When every score member derives
  from `price`, the result says so: agreement is consistency between views of one source, not independent
  confirmation.
- **Conflicts within a category**: categories whose members point opposite ways are flagged; weights are untouched.
- **Duplicates**: the same signal instance used twice in a Group (or across Groups in a Set) is flagged and counted
  once in every count.
- **Known redundancy**: pairs the library's development check found to agree heavily (trend vs momentum ≈ 80% when
  both directional). A static, versioned table until history exists.
- **Coverage and timing**: observed/imputed/excluded members, oldest `observed_at`, newest `available_at`.

### 3.6 Lineage

Lineage is a versioned table in the Groups layer keyed by signal id (`examples/lineage.json`, `lineage@1`). Today
every candle-based signal derives from `price` (CMF and relative volume add `volume`); ETF flows, stablecoin supply
and Coinalyze derivatives are separate roots. Two signals are independent only when their lineage sets are
disjoint. Users cannot edit lineage; a new library signal must be added to the table before a Group can use it.

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

```
analysis_configs          id uuid PK, kind ('group'|'set'), owner_id (null = Angstrom starter), current_version int,
                          copied_from_config, copied_from_version, audience_ceiling, archived bool, created_at, updated_at
analysis_config_versions  (config_id, version) PK, schema text, body jsonb (≤ 64 KB), content_sha256,
                          audience ('private'|'communities'|'public'), created_by, created_at, change_note
analysis_version_shares   (config_id, version, user_group_id) PK, shared_by, shared_at
```

- **Writes only through security-definer functions**; no direct insert/update/delete grants:
  `save_config_version(config_id, expected_version, body, note)` locks the config row, checks
  `expected_version = current_version` (else `conflict`), inserts `current_version + 1`, updates
  `current_version`, all in one transaction; `(config_id, version)` is unique.
- **Versions are immutable** (no update or delete, ever). Archiving hides a config from lists but keeps every
  version, so pins and copies stay valid. Hard delete is only for a private config that nothing references.
- **Publication is per version.** A new version is private. Publishing version N (public, or to chosen
  communities) never publishes earlier versions. A config row is visible to someone who can read any of its versions.
- **Owner only**: only the owner saves versions, publishes, shares or archives. Starters (owner null) are written
  only by the service role.
- **Community access** = leader (`user_groups.leader_id`) or member (`group_members`). Leaving or being removed
  ends access to that community's versions immediately.

## 7. Copying, embedding and redistribution

- **Audience order**: private ⊂ communities ⊂ public. Each config carries an `audience_ceiling`: `public` for an
  original or a copy of a public/starter source; for a copy of a community-shared source, those communities
  (at copy time).
- **Copying** needs read access to the source version. The copy is owned by the copier, starts at version 1 with
  provenance, and can never be published beyond its ceiling.
- **Embedding in a Set** needs read access to each Group version. The Set's ceiling is the intersection of its
  own and every embedded snapshot's ceiling (an empty intersection = private only).
- **Checks** run at save, at publish/share, and whenever an audience is widened. A widening beyond any ceiling
  is refused with the source named.
- **Revocation**: narrowing or archiving a source stops new copies and new embeddings. Copies and snapshots made
  while authorised remain (content already shared cannot be recalled); the publish screen says so before anyone
  publishes. A copy's ceiling never widens because the source later becomes public; the owner can re-copy.
- Tests in the build: another owner's community-only Group into a public Set (refused), community→public
  widening (refused), source access removed after copy (copy kept, ceiling kept), version 2 published while
  version 1 private (version 1 unreadable).

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
- **Reversal Evidence**: no score. A bullish (bearish) setup needs at least two of: an active RSI or MACD
  divergence (both from the same price swings, so one signal family in practice; the same instance counts once),
  a CHoCH within 20 candles, price within 1 ATR of a support (resistance) zone. All are price-derived, so the
  condition is labelled corroborating, not independent. CMF is context.
- **Multi-Timeframe Analysis** Set: both Groups embedded as snapshots, timeframe alignment and 4-hour levels as
  standalone, Bitcoin ETF flows as current market context; no Set score.

## 11. Decisions for approval

| # | Decision | Proposal (revision 2) |
|---|---|---|
| D1 | Names | **Decided**: Communities (social); Signal Groups / Signal Sets |
| D2 | Storage | Three tables; per-version publication; function-only atomic writes; immutable versions (section 6) |
| D3 | Sets and others' Groups | Embedded snapshots with provenance; audience ceilings; checks at save/publish/widen; revocation stops new copies only (section 7) |
| D4 | Unavailable data and coverage | Role-specific policies; exact coverage arithmetic; imputed never counts as observed (sections 3.1–3.2) |
| D5 | Rule language | Bounded JSON, three-valued logic, typed paths, lineage-based independence, explicit event timing (section 3.4) |
| D6 | Transforms | `map`, `bands`, `clip`, `events` v1 as specified with fixtures; adaptive transforms deferred (section 3.3) |
| D7 | Set scores | Deferred: always null in the first build |
| D8 | First build | Admin-only validator, evaluator and starters, live mode only, synthetic/development fixtures, hold-out untouched |

## 12. Review findings and changes (PR #1)

| Finding | Change |
|---|---|
| 1 Families are not independence | `family` replaced by descriptive `category` plus fixed `lineage` (3.6); `count_independent_at_least`; duplicates count once; conflicts flagged; starter rule relabelled corroborating (10) |
| 2 Snapshots and permissions | Audience ceilings, checks, provenance with hash, revocation (7); Set example embeds snapshots |
| 3 Version publication and invariants | Per-version publication, function-only atomic writes, immutability, owner-only, leader + member access (6) |
| 4 Roles vs rules, unknown vetoes | Role table (3.1); regime is a `condition`, zones `levels`; three-valued logic and statuses (3.4) |
| 5 Coverage arithmetic | Exact definitions, fraction threshold, worked cases (3.2) |
| 6 Set scores | Deferred (D7) |
| 7 Point-in-time metadata | Request `as_of` and `data_mode`, full per-member metadata, `point_in_time` refused until supported, ETF live-only label (4) |
| 8 Transform schemas | Parameters, boundaries, unknowns, conflicts, fixtures (3.3) |
| 9 Example tests | Structural checks: roles and policies, rule walk with paths resolved on real outputs, transforms, coverage fraction, starter aliases and versions, snapshot hashes, lineage coverage, fixture ranges |
| 10 CI gate | `checks.yml` shared jobs; required failures fail the job; optional live-feed checks labelled; `pr-checks.yml` runs read-only with artifacts (forks included); `v2-checks.yml` publishes on push |
