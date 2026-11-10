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
