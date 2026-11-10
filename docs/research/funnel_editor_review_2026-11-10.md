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
