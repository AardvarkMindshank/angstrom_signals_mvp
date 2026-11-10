# Funnels v2: the four specifications

10 Nov 2026. Implements the approved decision in `docs/research/funnel_editor_brief_2026-11-10.md` ("Decision after
review"). ChatGPT asked for these four contracts before building; each is tested in `tests/`.

## 1. Shared answers: key and invalidation (`set_answers`, `funnel_runner.SharedAnswers`)

A stage's answer for one asset at one close is stored once and read by every funnel that checks the same Set logic.

**Key** = `logic_hash` × `code_id` × `asset_key` × `cutoff`.

| Part | What it is | Why |
|---|---|---|
| `logic_hash` | `what_followed.logic_hash(set_body)`: the Set body without its name, purpose, notes or where its Groups were copied from. It includes embedded Group versions, signal ids and versions, parameters, timeframes, the decision and every fixed subject (a line pinned to Bitcoin carries Bitcoin's id). | A renamed copy shares answers; any change to what it checks does not. |
| `code_id` | The first 12 characters of `signal_library.certification.code_hash()`: the certified calculation code. | A change to any certified calculation (re-certified) gives new answers; old closes stay as they were. |
| `asset_key` | `crypto:bitcoin`, `equity:AAPL`. The venue is part of the asset: a coin's source is fixed by the daily universe (Binance pair or Yahoo). | |
| `cutoff` | The close the stage is checked at (UTC), as `funnel_runner.latest_close` gives it. | |

**Rules**
- A stored answer for a past close is read, never worked out again.
- Only finished answers are stored: Yes, No and Unknown (Unknown = the Set ran and some reading was missing). A
  failure (data could not be read, the reconstruction refused: prism's "Not evaluated" rows) is **not stored**; the
  funnel records it as Unknown for that close, and the next funnel or pass at the same close tries again. An outage is
  never a No.
- Answers are written and read only by the funnel job with the service role. No account can read the table (it holds
  no Set bodies, only hashes, but hashes of private Sets must not be a way to discover them).
- Rows older than 120 days can be deleted (nothing reads them: a funnel only checks the latest close).

## 2. Versions and state transitions (`funnel.py`, `funnel_runner.py`)

- **Saving and activating.** A funnel has an active version (`stages`, `stages_version`) and, while being edited, a
  draft. Activating the draft replaces the stages and bumps `stages_version`. Nothing else resets places.
- **Changes that start again from the pool:** any change to a stage's Set (including ⬆ Upgrade), a stage added,
  removed or reordered, a stage timeframe changed, the pool rule changed. Renaming the funnel or a stage, alerts and
  the leave rule do not.
- **First pass of a version is silent.** Places are set and Candidates latched without "new Candidate" alerts, unless
  the funnel's alerts say `first_matches`. (Live since 10 Nov.)
- **Two No closes to leave:** two No answers in a row at that stage's closes. Unknown neither counts as a No nor resets
  the count; a Yes resets it. With the leave rule set to one, the first No leaves.
- **Unknown:** never promotes; a held stage shows ❔ Pending; three Unknown closes in a row and it leaves.
- **Leaving the pool** (the coin is no longer in the daily universe, or below the funnel's pool rule): its state is
  kept as "left the pool", it is not checked, it is never alerted, and it is not counted as failing a stage. If it
  returns to the pool, it starts from the pool again.
- **Alerts:** only on newly becoming a Candidate, latched until it stops being one; one batched note per funnel per
  pass; the first pass of a version is silent.

## 3. Capacity and queue (`funnel_runner.run_all`)

- Limits: 6 funnels per account (database), 5 stages, pool capped at the universe (≈200 coins, ≈495 shares).
- Order of work in a pass: stages due now, grouped by `logic_hash`, most-used first; each account's funnels take
  turns so one account cannot fill the hour. Shared answers mean a Set used by ten funnels is worked out once.
- Budget: 35 minutes a pass; a stage that does not start waits for the next pass at the same close (claims are per
  funnel, stage and close, and a stopped claim is taken over after an hour). The page shows a stage that ran late.
- Measured 10 Nov (before sharing): daily stage ~1 s per coin (197 coins, 3 min); shares 4-hour ~0.3 s per share.
  Benchmark to record before raising limits: unique answers per minute.

## 4. Editor validation (`funnel_spec.validate`)

**Blocks saving:** fewer than 3 or more than 5 stages; a stage without a Set, or a Set without a decision, or one
not scannable; a stage timeframe not allowed (15m … 1W); a shares funnel whose stage timeframe is 12h (shares trade
6½ hours: use daily); a pool rule outside the allowed values.

**Warns:** stage timeframes not running from longest to shortest; a Set whose readings are on a different timeframe
from the stage that checks it (allowed: the stage sets *when* it is checked); a Set needing more history than the
pool's newest assets have (they will show ❔ Pending).

Fixtures (`tests/test_funnel_spec.py`): every provided funnel validates with no blocks; each block and warning above
has a failing example.
