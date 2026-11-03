# Design proposal: Signal Groups and Signal Sets

Status: **proposal for review**. No code in this PR besides a test that checks the examples against the live
Signal Library. Nothing is built until the decisions in section 9 are approved.

```
Signal Library ──► Signal Groups ──► Signal Sets ──► Analysis Workspace / Strategy Builder
 (built, v3)        (this design)     (this design)    (later; not designed here)
```

## 1. Scope

In scope: what a Group and a Set are, how they are evaluated, stored, versioned, copied and shared, and the
starter templates. Out of scope: any user interface, the Workspace, strategies, backtests, AI suggestions
(only the hooks they need), and storing signal history.

Non-goals carried over from the Signal Library brief: no universal composite score, no fixed membership,
no averaging of incompatible values, no assumption that correlated signals confirm each other.

## 2. Terms (and a naming clash)

| Term | Meaning |
|---|---|
| Signal | One library observation, referenced by a `SignalRef` (id, pinned version, timeframe, params). Exists today. |
| Member | A signal inside a Group, with a role, an optional weight and an optional transform. |
| Group | A named, versioned configuration that answers one analytical question from its members. |
| Set | A named, versioned collection of pinned Groups plus standalone signals and market context. |
| Family | A label on a member saying which evidence source it comes from (price trend, price structure, volume, flows...). Agreement is counted per family, not per member. |

**Naming:** the app's social groups (`user_groups`, formerly shown as "👥 My Groups") are renamed
**Communities** in everything users read (PR #2; tables and ids unchanged). "Group" in the app then only ever
means a Signal Group. The new layer uses its own tables (`analysis_configs`, below), so nothing collides in the
database either. Sharing "to communities" below means sharing to those social groups.

## 3. A Group

A Group is a JSON document (`schema: "angstrom.group/1"`). Two full examples are in `docs/design/examples/`.

### 3.1 Members and roles

| Role | Used for | Weighted? |
|---|---|---|
| `score` | Contributes to the Group's score through an explicit transform | yes (weight ≥ 0; 0 disables; equal by default) |
| `condition` | Referenced by rules (confirmations, vetoes) | no |
| `levels` | Supplies prices or zones (shown as levels; usable in rules) | no |
| `context` | Shown alongside for interpretation only | no |

Each member also says what happens when its signal is unavailable (missing, stale, insufficient):
`exclude` (drop it and re-weight the rest; scores only), `neutral` (counts as 0), `fail` (rules that need it
are "not evaluable"), `ignore` (context: just show the status). Nothing is silently treated as a reading.

### 3.2 Transforms (how native values become score contributions)

Signals keep native units. A score member must declare a transform; the transform is versioned like a signal.
First set:

| Transform | Input | Output | Example |
|---|---|---|---|
| `map` | label (optionally a `field` inside an observation) | −1..+1 or null | `{"up": 1, "down": -1, "mixed": 0}` |
| `bands` | number | −1..+1 | CMF ≤ −0.1 → −1, between → 0, ≥ 0.1 → +1 |
| `clip` | number | −1..+1 | linear between declared bounds, clipped |
| `events` | events list | −1..+1 | +1 if a confirmed bullish event is active, −1 bearish, else 0 |

No percentile or z-score transforms in the first build: they need stored history (section 7).

### 3.3 Score (optional)

`score: null` means the Group has no score (the Reversal Evidence example). When present:

- method `weighted_mean` of transformed contributions over available `score` members, range −1..+1;
- `meaning` (required): one sentence saying what +1 and −1 mean for this Group;
- `min_coverage`: the share of total score weight that must be available, else the score is withheld
  ("not enough evidence"), never estimated;
- the result always lists each member's native value, its contribution and its weight share.

Display: the app shows scores on −100..+100; a Group score uses the same convention, labelled with its
`meaning`. It is never mixed with Trend, Stretch or Flow.

### 3.4 Conditions: confirmations and vetoes

Rules are separate from the score. A rule is a small JSON expression:

- combinators: `all`, `any`, `not`, `count_at_least` (members), `count_families_at_least` (distinct families);
- predicates on a member: `eq`, `in`, `gte`, `lte`, `between`, `exists` on its value or a `field` path inside it;
  `events` filters (`type_in`, `kind_in`, `direction`, `status`, `within_candles`);
- predicates on the Group's own score: `{"score": {"gte": 0.5}}`.

Kinds: `confirmation` (reported as met / not met / not evaluable) and `veto` (when true, the Group result is
marked vetoed with the reason; the score is still shown, never altered). Evaluation is deterministic and has no
side effects; there is no scripting.

### 3.5 Diagnostics

Every evaluation reports:

- **agreement**: the share of score weight pointing the same way, counted by family (two price-trend members
  agreeing count once);
- **disagreement**: which members or families point the other way;
- **redundancy warnings**: two score members in the same family, or a pair the library's development check found
  to agree heavily (today: trend vs momentum ≈ 80%); stored as a small static table until history exists;
- **coverage and freshness**: which members were missing or stale, and the oldest `available_at` used.

### 3.6 Result shape

```
GroupResult: config, version, subject, evaluated_at,
             members[] (key, ref, status, native value, unit, contribution, weight share, available_at),
             score (value | null, coverage, withheld_reason), conditions[] (key, kind, state, reason),
             diagnostics (agreement, disagreement, redundancy, coverage, oldest_input)
```

Evaluation reuses the library engine, so a signal used by several Groups in a Set is calculated once.

## 4. A Set

A Set (`schema: "angstrom.set/1"`) lists:

- `groups`: pinned references `{config, version}`; editing a Group later never changes a Set until the owner
  upgrades it;
- `standalone`: library signals shown directly (context or levels);
- `market_context`: market-level signals (ETF flows, stablecoins) with the asset types they apply to.

`score` is `null` by default. A Set score is only allowed when every included Group has a score with the same
declared `meaning` category (for example all "trend direction"), and it is then a weighted mean of Group scores
with the same coverage rule. The validator refuses anything else.

A Set is an analysis configuration, not a strategy: it carries no entry, exit or risk rules.

## 5. Storage, versions, copies, sharing

Two new tables (one for both kinds, plus their versions) and one for community sharing:

```
analysis_configs        id uuid, kind ('group'|'set'), owner_id (null = Angstrom starter), name,
                        visibility ('private'|'communities'|'public'), current_version int,
                        copied_from (config id, version) null, created_at, updated_at, archived bool
analysis_config_versions config_id, version int, schema text, body jsonb (≤ 64 KB), created_by, created_at,
                        change_note; immutable once written (no update policy)
analysis_config_shares  config_id, user_group_id (existing user_groups), shared_by, shared_at
```

- **Versions are immutable.** Saving creates version n+1; references (Set → Group) pin a version.
- **Copying** creates a new config owned by the copier with `copied_from` set (attribution) and version 1 =
  the source version's body. It is independent from then on.
- **Visibility**, enforced by row-level security: owners see and edit their own; others can read a config when it
  is public, or shared with a social group they belong to. Starter templates are public, read-only, owner null.
- **No leaks through Sets.** When a Set is shared, every Group it pins must be readable by the same audience. The
  proposal (D3) is to embed a frozen copy of each pinned Group body inside the Set version when it is saved, so a
  Set never depends on someone else's private Group staying visible.
- **Popularity is not performance.** Votes and comments reuse the social features later; they are stored and
  shown apart from any evidence about results.
- **Validation** happens before any write: schema, signal ids and versions exist, params valid, transforms match
  output types, weights ≥ 0, rules reference existing members, Set score compatibility.

## 6. Evaluation and resources

On demand, like the Signal Library: nothing new runs in the worker. One Group on one asset costs the library
signals it uses (cached and shared). Intraday members load Yahoo candles for that asset only. Group and Set
results are not stored in the first build.

## 7. What later stages will need (not built now)

- **History** of signal and Group results (needed for alerts on Groups, live redundancy diagnostics, percentile
  transforms and backtests): a decision to reverse "calculate on demand" for whatever Groups use.
- **AI suggestions**: stored as a proposed new version (a diff) awaiting the owner's approval; never applied
  automatically; any performance claim needs evidence.
- **Strategy Builder**: references a Set version and adds explicit entry, exit and risk rules in its own schema.

## 8. Starter templates

- `starter:trend-confirmation` — see `examples/group_trend_confirmation.json`. Score from daily trend, 4-hour trend
  and daily swing structure (equal weights); 4-hour momentum confirms instead of voting (it repeats trend);
  vetoed when the daily regime is ranging.
- `starter:reversal-evidence` — see `examples/group_reversal_evidence.json`. No score. A setup needs evidence from
  two independent families among: RSI/MACD divergence (one family), a recent CHoCH, price within 1 ATR of a zone.
- `examples/set_multi_timeframe.json` — both Groups, the timeframe alignment, 4-hour levels and Bitcoin ETF flows;
  no Set score.

The current Trend, Stretch and Flow readings could later be added as templates; they do not constrain this design.

## 9. Decisions for approval

| # | Decision | Recommendation |
|---|---|---|
| D1 | Visible names | **Decided:** social groups become "Communities" (PR #2); the new layer is "Signal Groups" and "Signal Sets" |
| D2 | Storage | The three tables above (needed for sharing and RLS), not JSON inside `user_preferences` |
| D3 | Sets and private Groups | Embed a frozen copy of each pinned Group in the Set version |
| D4 | Unavailable members | Per-member policy (`exclude`, `neutral`, `fail`, `ignore`) with `min_coverage` on scores |
| D5 | Rule language | The fixed JSON expressions above; no scripting |
| D6 | First transforms | `map`, `bands`, `clip`, `events`; percentile/z-score wait for history |
| D7 | Set scores | Off by default; only for Groups with the same declared meaning |
| D8 | First build scope | Data model, validator and evaluator, starter templates, inspection in the admin view; no user editing UI yet |

## 10. Proposed build after approval (separate PRs)

1. Schema validator and evaluator for Groups (pure Python, tests on the starter templates), shown in the admin
   inspector.
2. Sets evaluator and the SQL for the three tables (run by you), with row-level-security tests.
3. Save, version and copy (admin only first).
4. User interface for creating and editing Groups and Sets (separate approval).
