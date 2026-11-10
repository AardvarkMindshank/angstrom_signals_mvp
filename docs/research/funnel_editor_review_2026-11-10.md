# Funnels v2 brief: reviews (10 Nov 2026)

Brief: funnel_editor_brief_2026-11-10.md

## Gemini

### 1. Verdict on the Approach

**Sound with changes.** Moving to a Lattice-style funnel editor, implementing shared-answer caching keyed by set logic fingerprints, and allowing custom asset pools are all architecturally correct. However, pinning every stage Set version statically within a funnel risks user fatigue when a core indicator definition improves, requiring a hybrid inheritance model instead.

---

### 2. Answers to Questions 1–9

1. **Editor Model (Pinned vs. Following):** **Hybrid approach.** A funnel should *reference* Sets, but allow an option for whether it follows the latest minor bug-fix/re-certification of a Set or stays pinned to a specific major version. Total decoupling (editing a Set automatically alters the funnel) is simpler for casual users, whereas pinning prevents historical drift. For version 2, make funnels follow the *latest active version* of a Set by default, but flag breaking schema changes.
2. **Validation:**
* *Block saving:* Timeframe inversions (e.g., checking a 1-hour stage *before* a daily stage), missing scannability, or choosing a pool whose history is shorter than the longest indicator lookback (e.g., weekly EMA 50 on a newly listed token).
* *Warn only:* Sub-optimal timeframe spacing or unusual custom volume thresholds.


3. **Shared Answers (Caching Traps):** Caching across users based on `(Set logic fingerprint × asset × close)` is powerful, but beware of **pinned-asset drift** (e.g., a Set that reads *another* asset like Bitcoin: the answer depends on both assets' states at that close). The cache key must explicitly incorporate all dependency fingerprints, including any pinned asset identifiers and data revision timestamps.
4. **Cost & Limits:** A per-Set budget (or a deduplicated worker queue) is vastly fairer than a per-funnel budget, because 10 users running funnels built on the exact same 5 standard Sets should only trigger *one* evaluation pass per asset close. A 25-minute window for ~500 assets across shared-cache checks is easily achievable.
5. **Pools:** Market cap ranking, minimum daily volume filters, and custom blacklist/whitelist tags (e.g., excluding meme coins) matter most to traders. Pools *should* be shareable and reusable across a single user's multiple funnels to prevent redundant configuration.
6. **Newcomers vs. Experts:** Use a **"Simple Mode / Advanced Mode" accordion** in the Lattice editor. Newcomers see pre-built templates where they only adjust sliders (e.g., RSI thresholds, moving average lengths), while experts can unlock the full modular stage builder.
7. **Wording and Safety:** Custom funnels must carry a prominent, unmissable badge: **"Custom Funnel: Unstudied (No historical performance check)"**. This prevents newcomers from assuming user-invented funnels share the rigorous testing caveats of provided templates.
8. **Market practice:** TradingView multi-timeframe screeners and TrendSpider allow custom multi-timeframe alerts, but they completely lack automated historical validation and epistemic honesty regarding missing data. Angstrom should copy the *modularity* while avoiding TradingView's black-box opaque alerting style.
9. **Simplify:** Leave out cross-user funnel sharing and automated portfolio asset exclusions for version 2; focus entirely on the single-user Lattice editor and shared-answer caching layer.

---

### 3. Traps We Missed (Most Serious First)

1. **The Pinned-Set Update Deadlock:** If a user builds a funnel and every underlying Set is strictly pinned, any minor fix to an underlying indicator's calculation bug breaks backward compatibility or forces users to manually rebuild funnels from scratch.
2. **Cache Invalidation Failures on Indicator Recertification:** If a developer modifies a signal's math or lookback window in the code repository, old cached evaluation results in Supabase will become invalid. Without a global cache-busting version hash tied to signal code deployments, stale answers will silently persist.
3. **Exploding Combinatorial Query Costs in Custom Pools:** Allowing complex custom pool definitions (e.g., custom market cap ranks combined with dynamic volume and sector exclusions) can degrade Supabase query performance if evaluated dynamically during hourly worker runs. Pools must be materialized into static asset lists at the hourly cron trigger.

---

### 4. Recommended Version 2 Architecture

* **Editor Model:** Lattice-based UI (`🔻 Funnels`) using a "Start from template → Edit → Save" lifecycle, defaulting to latest minor Set versions with clear breaking-change warnings.


* **Validation:** Hard blocks on timeframe sequencing errors and insufficient history depth; soft warnings on performance-heavy custom configurations.
* **Shared Answers:** Global Supabase evaluation cache keyed by `(Set Logic Fingerprint + Pinned Asset ID + Asset ID + Candle Close Timestamp)`. Deduplicate worker queues so identical Sets across different users' funnels are only calculated once per hour.


* **Pools:** First-class objects in the funnel definition, supporting top-$N$ market cap cutoffs, minimum daily volume floors, and category/sector filters, materialized into static arrays at the hourly cron start.
* **Limits:** Maximum 6 funnels per account, 5 stages per funnel, and strict daily alert caps to eliminate notification fatigue.



---

### 5. Sources

* Angstrom Signals repository design docs (`docs/research/funnel_brief_2026-11-10.md`).


* TradingView Multi-Timeframe Alert Architecture & Screener Specifications.

## Cursor / Grok

## 1. Verdict

**Sound with changes.** An editor that starts from a provided funnel, pins Set versions, and shares answers by Set logic is the right next step. Treat shared answers as the main build, keep pools simple, and do not let “latest Set” auto-follow — that would make two people with the “same” funnel get different histories without noticing.

## 2. Answers to questions 1–9

**1. Editor model.** Use **Start from → edit → save a version**, with **each stage pinning a Set version** (same idea as Sets embedding Group versions). Do not make the funnel silently follow “latest Set.” Stability matters more than convenience: flicker counts, Candidate latches, and “what was I watching yesterday” break if a stage Set changes underfoot. Allow an explicit **Upgrade available** on a stage (compare fingerprints); applying it starts assets again from the pool, as a stage edit does today. Editing a Set elsewhere must not rewrite a running funnel.

**2. Validation.**  
**Block save:** fewer than 3 or more than 5 stages; a stage Set with no decision; Set not readable on that stage timeframe; market/direction/pool missing; history need of any stage longer than the pool can supply; duplicate stage order keys.  
**Warn only:** timeframes not strictly longer→shorter; a stage Set whose members use a different timeframe than the stage label (allowed if intentional, e.g. daily filter inside a 4h stage — but show it loudly); pool so tight that expected survivors are tiny; flicker = one No (noisier).  
Do not block mixed member timeframes inside a Set if Prism already allows that; the stage timeframe is when the funnel *checks*, not a claim that every member is on that TF.

**3. Shared answers — traps and key.**  
Traps: (a) fixed-subject lines (“Bitcoin’s trend”) — the fingerprint must include every pinned subject, not only the scanned asset; (b) provider revisions — store the run’s input hash / replay identity like Prism; later rebuilds may differ; the funnel reads the **stored** answer for that close, not a live recompute; (c) signal code re-certification — bump or namespace the fingerprint when certified logic changes so old closes stay immutable; (d) failures — cache a definite **error/unavailable** distinct from Unknown, or funnels will Pending forever; (e) privacy — answers are market facts from shared Sets, fine; never store another user’s notes in that cache.  
**Key:** `logic_fingerprint` (canonical Set body + lineage/code identity used for evaluation) × `subject_asset` × `timeframe` × `cutoff_T` × `data_mode`. If the Set has fixed subjects, fold those into the fingerprint or an explicit side key. Do not key only by Set config id — two copies with the same logic should share; two versions of one id must not.

**4. Cost.** Worst case if every funnel used unique Sets: `N × F × stages × assets` evaluations. Shared answers cut that to roughly **distinct (Set logic × TF closes × assets in union of pools)**.  
Practical limits for ~25 minutes/hour: keep **≤6 funnels/account**, prefer **shared provided stage Sets**, cap **active custom stage Sets** globally or per hour (e.g. evaluate the most-used fingerprints first; defer rare custom Sets to the next hour with “ran late”); **pool ≤ ~200 crypto / S&P-sized shares** unless the user narrows; one claim per (fingerprint, asset, close) not per funnel.  
**Fairer budget:** **per Set fingerprint** (and secondarily per account fairness). Per-funnel alone punishes people who reuse provided Sets and rewards duplicate logic under new names — unless fingerprinting collapses duplicates (which it should).

**5. Pools.** Most useful narrowing, in order: **my watchlist only**, **min daily volume**, **top N by market cap**, then exclude categories (meme / leveraged). Sectors for shares are nice but secondary.  
A pool should be **pinned on the funnel version** (as proposed). Optionally let someone **reuse a named pool template** across their funnels, but copy-on-save into the funnel so editing one funnel’s pool does not surprise the other. Do not force one shared live pool across all funnels.

**6. Newcomers vs experts.** Default path: **Start from [provided crypto long / short / shares…] → change one threshold via “Edit stage Set (makes my copy)” → save funnel version.** Advanced: add/reorder stages, pick any Set, custom pool, flicker, alerts. Hide fingerprint, PIT, and budget jargon behind “How this run works.” Presets must remain one click; empty “build a funnel from scratch” is expert-only.

**7. Wording and safety.** Custom funnels need a **stronger mark** than provided ones: e.g. “Your funnel — not reviewed, not tested, not advice.” Stage labels like “entry” are dangerous; prefer **Ready to review** / **On watch** (as in v1 reviews). No green “buy” styling on Candidate. Alerts: “X newly meet your last-stage rules” — never “signals to trade.”

**8. Market practice.** TradingView: screeners/alerts on lists; multi-TF usually one script, not a versioned stage ladder ([Pine Screener](https://www.tradingview.com/support/solutions/43000742436-tradingview-pine-screener-key-features-and-requirements/), [watchlist alerts](https://www.tradingview.com/support/solutions/43000739708-watchlist-alerts-your-trading-edge/)). TrendSpider: custom multi-factor scans → smart watchlist, closed vs current candle ([Market Scanner](https://help.trendspider.com/kb/scanner/market-scanner)). 3Commas-style bots: form parameters, not research-grade shared PIT answers.  
**Copy:** start-from template, alert on enter-list, closed candles.  
**Avoid:** auto-follow latest logic, current-candle “force close,” and anything that looks like auto-trading.

**9. Simplify this version.** Leave out: public funnel sharing, funnel studies, sector filters (v2.1), meme-category taxonomies beyond a simple exclude list, per-stage alert types beyond Candidate batching, editing Sets in-place inside the funnel (deep-link to Lattice Set editor to copy instead), pools larger than today’s usable universe. Ship: Lattice Funnels section, pinned stages, shared answer cache, pool = top N + min volume + watchlist-only + basic excludes, limits 6 / 5 / fair hourly continue.

## 3. Traps missed (worst first)

1. **Identical UI, different fingerprints** — two “Daily trend” Sets that look the same but differ by one weight will not share answers and will double cost; show “sharing answers with N other runs” / fingerprint short id for experts.  
2. **Renaming vs logic change** — label-only edits must not bust the cache; body edits must.  
3. **Stage reorder without reset policy clarity** — reordering is a logic change; must reset from pool (you said stage changes do; include reorder explicitly).  
4. **Watchlist-only pool + Dynamic table** — newcomers may think Dynamic still searches the market; say “only your watchlist.”  
5. **Shares session vs crypto UTC** — custom funnels will mis-set 4h/1h; validate market-specific calendars as hard rules where needed.  
6. **Alert storms from flicker=1** — default stay at two Nos; daily alert cap is necessary but say when drops were suppressed.  
7. **Candidate sentiment refresh × many users** — keep one sentiment job per asset, not per user, same as shared answers.

## 4. Recommended version

- **Editor:** Lattice 🔻 Funnels; Start from provided or own; stages 3–5 with **pinned Set versions**; Upgrade available; save immutable funnel version.  
- **Validation:** block unscannable/wrong-TF/history/pool mismatches; warn on TF order and mixed member TFs.  
- **Shared answers:** mandatory for this version; key = logic fingerprint × asset × TF × cutoff (+ fixed subjects + code identity); store success and failure; funnels only store stage state.  
- **Pools:** on the funnel version — top N, min volume, watchlist-only, basic excludes; optional copyable pool template.  
- **Limits:** 6 funnels/account; 5 stages; fair continue-next-hour; budget by fingerprint first; daily alert cap; Candidate-only batched alerts by default.  
- **Safety:** stronger “not tested” on custom; no advice wording; keep Pending/Unknown rules from v1.

## 5. Sources

- This brief (Funnels v2, 10 Nov 2026) and v1 behaviour described there.  
- Existing Angstrom pattern: Sets pin Group versions; Prism point-in-time runs; studies keyed by Set logic fingerprint (as stated in the brief).  
- [TradingView Pine Screener](https://www.tradingview.com/support/solutions/43000742436-tradingview-pine-screener-key-features-and-requirements/)  
- [TradingView watchlist alerts](https://www.tradingview.com/support/solutions/43000739708-watchlist-alerts-your-trading-edge/)  
- [TrendSpider Market Scanner](https://help.trendspider.com/kb/scanner/market-scanner)

## ChatGPT

# Angstrom Prism Funnels V2 — Design Review

10 November 2026 · Reviewed against the V2 brief and the V1 decisions in GitHub

## 1. Verdict

Sound with changes. I support the funnel editor, reusable Set evaluations and configurable pools. These are logical extensions of the production V1 system.

The biggest opportunity is shared computation, but it's also the biggest technical risk. Done correctly, Angstrom can support substantially more users without multiplying market-data requests. Done incorrectly, it could silently reuse an outdated or inappropriate answer.

I'd approve the direction, with a few specific contracts defined before implementation.

## 2. Answers to questions 1–9

### 1. Editor — Keep pinned Set versions

Strongly favour pinned versions, not automatic following of the latest Set.

This is consistent with the accepted Groups/Sets architecture.

If Drew changes his daily Trend Set, every funnel referencing its latest version shouldn't silently change behaviour. That undermines reproducibility and makes alert changes difficult to explain.

I recommend:

- Start from → customise → save as a new immutable funnel version.
- Each stage references an immutable Set snapshot/version.
- Show “A newer version of this Set is available” with an explicit upgrade action.
- Provide Duplicate funnel for experimentation.
- Show a summary of changes before activating a revised funnel.

One refinement: saving and activating should be separate actions. A user should be able to prepare a new version without immediately resetting the active funnel's state.

### 2. Validation — Block invalid configurations, warn about questionable ones

| Block saving or activation                                        | Warn, but allow                              |
| ----------------------------------------------------------------- | -------------------------------------------- |
| Set has no decision rule                                          | Timeframes not ordered longest to shortest   |
| Referenced Set version missing or inaccessible                    | Mixed timeframes inside a Set                |
| Invalid timeframe, market or signal compatibility                 | Highly correlated evidence across stages     |
| Unsupported pool filter or invalid threshold                      | Pool likely to contain few eligible assets   |
| Required signal history cannot be satisfied by any eligible asset | Some assets lack sufficient history          |
| Configuration exceeds hard resource limits                        | Slow estimated evaluation or repeated stages |

Important distinction: a Set containing 4H and daily signals is not inherently invalid in a 1H funnel stage. The stage's 1H schedule determines when the Set is reevaluated; its members retain their explicitly configured timeframes.

I'd rename the editor field from Stage timeframe to Check frequency / trigger timeframe, unless it genuinely overrides every signal's timeframe.

Don't allow the interface to imply that a 1H stage automatically converts a daily indicator to 1H.

### 3. Shared answers — Approve, with stricter cache identity

This is the architectural centrepiece.

A Set's answer is shareable only when all relevant evaluation inputs and semantics are identical.

A safe conceptual key is:

```
Set evaluation fingerprint
+ subject asset identity
+ canonical evaluation cutoff T
+ evaluation/data mode
+ evaluator and signal code identity
+ market-data snapshot identity
+ provider/venue identity
+ fixed-subject dependency identities
```

The Set fingerprint must include the complete canonical logic, embedded Group versions, signal versions, parameters, lineage and evaluation-affecting settings.

A logic fingerprint plus asset plus candle close is insufficient on its own.

For example, a BTC Set might include COIN's daily trend. The key must account for COIN's actual input data and cutoff as well.

Further requirements:

- Never share incomplete evaluations as permanent cached answers.
- Unknown can be cached only with explicit missing-data provenance and an expiry or invalidation rule.
- Provider corrections and code changes must generate new cache identities or invalidate affected entries.
- The result must include the evaluation's actual `available_at` boundaries.
- Cache lookup must never bypass access controls on private Set configurations.

I'd distinguish the immutable evaluation result cache from users' private funnel states, histories and alerts.

Shared calculations, private decisions about what to do with them.

### 4. Cost — Budget by unique work, not by user or funnel

The proposed six-funnel limit is sensible, but it doesn't meaningfully bound total computation if everyone creates unique Sets.

Illustrative worst-case demand

# 100

Users

# 6

Funnels each

# 500

Assets per pool

# 300,000

Potential funnel–asset combinations per cycle, before stage filtering or cache reuse.

Not a runtime prediction: actual cost depends on unique Set evaluations, due stages, surviving assets and shared underlying signals.

I'd use three resource controls:

1. Global computation budget: unique Set evaluations and provider fetches within the worker's safe time allowance.
2. Fairness budget: bounded work per account, so one user cannot monopolise the queue.
3. Configuration limits: six active funnels, five stages, and a capped pool size.

A per-Set budget alone is not sufficient; a highly expensive Set can dominate a shared worker.

Use atomic jobs, leases and idempotent writes. Cache completed signal calculations as well as Set answers where safe.

Most importantly, measure actual unique evaluations per minute before expanding limits.

One technical correction: a funnel that needs 25 minutes of processing should resume from a checkpoint within the same logical scheduled run, rather than being treated as a fresh scan next hour. Progress must survive worker interruption.

### 5. Pools — Start with four useful controls

I'd prioritise:

- Universe: eligible crypto, eligible S&P 500 shares, or My Watchlist.
- Size: top 50, 100, 200 or 500 by market cap.
- Liquidity: minimum quote-dollar volume, applied using the correct venue or market-specific definition.
- Category/sector: optional inclusion or exclusion.

I'd allow users to reuse a saved pool definition, but a funnel should reference a pinned pool-rule version. Pool membership itself should remain dynamic.

That's a crucial distinction: a rule saying top 100 by market cap stays fixed, while the qualifying assets change over time.

Show the difference between excluded by user filter, ineligible due to poor data, and removed from the dynamic universe.

For the first build, saved reusable pools could be deferred. Embedded pool rules are simpler.

### 6. Newcomers versus experts — Two editing depths

I wouldn't create two different funnel engines.

Use one engine with two interface levels.

Funnel editor — concept

Beginner view

START FROM

Crypto multi-timeframe trend

Daily → 12H → 4H → 1H

What would you like to change?

Market direction

Long

Number of coins

Top 200

Exit after

2 failed closes

Advanced: edit stages and their Sets

Concept only — not a working editor.

Beginners change a supplied funnel's pool, direction and a few clearly exposed settings. Experts can replace stages, select their own Sets and adjust evaluation settings.

For someone changing a signal threshold, provide Edit a copy of this Set, returning them to the existing Lattice Set editor. Don't build a second threshold editor inside Funnels.

### 7. Wording and safety — Distinguish built-in from validated

I'd label funnels:

- Provided by Angstrom
- Customised
- My funnel

But I would not label a provided funnel Tested unless it has actually undergone the relevant research validation.

Similarly, Custom should not automatically imply something is defective or unsafe.

A standard note is sufficient:

> Candidate means this asset matches your selected conditions. It is not a recommendation to trade.

Avoid High conviction, Strong buy, Winning setup, Proven and Trade ready.

Keep Candidate and Flagged from V1 for consistency.

### 8. Market practice — Copy accessibility, not complexity

TradingView provides saved screens, editable filters, copies and custom columns. The useful lesson is that users can begin with a preset and progressively customise it without touching a programming language.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://th.tradingview.com\&sz=32)

TradingView+1



TrendSpider is the closer conceptual reference: custom multi-timeframe scanning, built-in scans, personal copies, scheduled results and Smart Watchlists.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://help.trendspider.com\&sz=32)

TrendSpider+2



3Commas provides configurable signal-driven bots. Its trading and exchange-execution controls are not an appropriate model for Prism Funnels, which remain analytical.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://help.3commas.io\&sz=32)

3Commas Help Center



The most useful design lesson is progressive disclosure: simple presets first, full rule editing only when needed.

### 9. Simplification — What I'd leave out

For V2, I would defer shared user-created pool libraries, complex sector/category combinations, cross-market funnels, automatic Set upgrades, public sharing, historical studies and execution features.

I'd also avoid adding another generic visual rule language. Lattice already has Groups and Sets for that.

## 3. Most serious traps missed

1\. Flicker state versus new versions. When a funnel changes, resetting every asset can produce hundreds of apparent new Candidates. A new version needs a bootstrap evaluation that establishes initial state without automatically treating every qualifying asset as a new alert. Let the user explicitly request initial-match notifications.

2\. Two-No rule ambiguity. Define whether two failures must be consecutive eligible closed candles of that stage's timeframe. Unknown must neither count as No nor silently reset the counter. I'd preserve the count through Unknown, but display that the evidence is pending. If a new Yes arrives, reset the count.

3\. Cache permission leakage. Two users can produce identical logic, but that doesn't give either user access to the other's private configuration. Compute shared results within trusted server code; expose only results the caller is authorised to obtain. Don't expose fingerprint lookups as a way to discover private strategies.

4\. A pool change can resemble a signal change. An asset disappearing because its market cap fell below a threshold is not the same as failing a Trend Set. Store the reason and distinguish left pool from failed condition. Removal should invalidate current eligibility without generating a misleading signal-transition alert.

5\. Historical corrections and provider failures. A cached answer may be mathematically correct for an earlier data snapshot but wrong for the currently available dataset. Retain provenance, data revisions and certification identity. An operational outage must not become a confirmed No.

6\. Equity schedules and stage clocks. A shares funnel using weekly, daily, 4H and 1H conditions must respect exchange sessions, half-days, holidays and the actual close of each aggregated bar. Fixed UTC hour arithmetic is not enough.

7\. Limits that aren't enforceable globally. Six funnels per user is not a hard capacity guarantee. A flood of custom Sets can exhaust the shared worker even when everyone respects the limit. Add admission control and visible queue delays.

## 4. My recommended V2

| Area           | Decision                                                                                                     |
| -------------- | ------------------------------------------------------------------------------------------------------------ |
| Editor         | Start from template → customise → save immutable version → explicitly activate                               |
| Stages         | 3–5, each with pinned Set logic and a separate evaluation trigger                                            |
| Validation     | Block structural and unsupported configurations; warn about timeframe order, partial history and likely cost |
| Shared answers | Trusted server-side cache keyed by full evaluation and data identity; private per-user state                 |
| Pools          | Embedded versioned filters: market, top N, minimum liquidity, optional category/sector and My Watchlist      |
| Limits         | Up to 6 active funnels, 5 stages, capped pool, global plus per-account work budgets                          |
| Alerts         | Existing Candidate-only batched alerts, version-safe bootstrap, unchanged Yes/No/Unknown latch semantics     |

### What I'd require before implementation

Only four focused specifications:

1. Cache identity and invalidation contract, including provider revisions, code changes, fixed-subject dependencies and authorisation.
2. Version activation and state-transition contract, including the two-No rule, bootstrap alerts and pool-membership changes.
3. Capacity benchmark and queue policy demonstrating how shared evaluations, fair scheduling and resumable jobs fit the worker budget.
4. Editor validation and usability fixtures, ensuring saved documents are identical in meaning to the headless engine and custom Sets aren't silently rewritten.

These don't require another broad architecture review.

## 5. Sources

- [TradingView — Create, save and copy custom screens](https://www.tradingview.com/support/solutions/43000718804/?utm_source=chatgpt.com)
- [TradingView — Screener filters](https://www.tradingview.com/support/solutions/43000718745/?utm_source=chatgpt.com)
- [TrendSpider — Market Scanner](https://help.trendspider.com/kb/scanner/market-scanner?utm_source=chatgpt.com)
- [TrendSpider — Multiple timeframes](https://help.trendspider.com/kb/scanner/multiple-timeframes-and-the-current-candle?utm_source=chatgpt.com)
- [3Commas — Signal Bot configuration](https://help.3commas.io/en/articles/16281112-signal-bot-comprehensive-json-guide?utm_source=chatgpt.com)

Final recommendation: approve Funnels V2 in principle.

I would keep the implementation deliberately focused on the editor, shared computation and configurable pools.

There is no need to redesign Groups, Sets or Prism. The value of this release is letting users build their own multi-timeframe funnels without making Angstrom slower, more expensive or less trustworthy as the user base grows.
