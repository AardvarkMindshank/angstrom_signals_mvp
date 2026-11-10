# Study enhancements — design review

10 Nov 2026 · Independent review of `docs/research/study_enhancements_brief_2026-11-10.md`

Read against: `what_followed.py`, `what_followed_run.py`, `research_stats.py`, `docs/research/what_followed_brief_2026-11-08.md`.

---

## 1. Verdict

**Sound with changes.** Keep the always-on crypto/equity split and a descriptive per-asset guide. Drop free year picking and Chosen-assets studies from the first version. Treat every extra cut as exploratory: show the search, put confirmatory tests in one Holm family, and never let a narrowed card outrank the default all-assets study.

## 2. Answers to questions 1–11

**1. Split.** Separate crypto and equity *reporting* on every card is sound and answers the Breakout-fading question without a new study request. Do **not** give the split its own Holm family: that under-corrects. Put pooled + crypto + equity tests for a Set in **one** family (with the run’s other Sets as today), or treat the split as descriptive only (plain numbers, weeks, Too few) without a second verdict ladder. Prefer: headline stays pooled; split gets the same four verdicts only when each part clears 40 weeks **and** its tests sit in that shared family. Replace the sign-only coins/equities consistency lines with these stratified estimates; keep the three calendar periods for “Consistent difference.”

**2. Per-asset table.** Keep it as a guide, not a test. The random-No-day luck check is directionally fair but slightly optimistic: Yes episodes cluster in time more than random No draws, so the 95% band can be too narrow. Prefer a **calendar-block** or week-block reshuffle within the asset (or a pooled “how many assets look unusual” null that redraws episode dates jointly). Do not mark individual assets as winners; lead with the count line (“7 look unusual; about 4 would by chance”). Mild shrinkage toward the pool (James–Stein / partial pooling) helps phone users not chase noise; a funnel plot is optional for a later “research” view, not v1. Leaving per-asset numbers out entirely throws away the owner’s real question — keep counts and raw gaps, soft-pedal ranks.

**3. Minimums.** Any **verdict-bearing** slice (pool, crypto, equity, future scope): same as today — episodes in **≥ 40 distinct weeks**, else Too few to judge. Per-asset guide row: show numbers from **≥ 15 episodes** (10 is thin for two measures); below that, show count only and “too few to compare.” Do not invent a lower bar for scopes.

**4. Scopes.** Once the split is on every card, **Crypto only / Equities only as separate stored studies are redundant** in v1 — drop them. **Chosen assets: defer.** If added later: minimum **8 assets** and **40 weeks**, plus the self-confirm guard in Q7. Pinned “Bitcoin breakout → other coins” is already answered by studying the Set on crypto (or all) with the pin inside the Set — not by a Chosen list.

**5. Years.** Free year picking is not worth it for newcomers: it is the easiest way to find a lucky window. **Defer.** If ever kept, offer only the **fixed blocks** already used for consistency (before 2019, 2019–21, 2022–Oct 2024), each as an exploratory slice with a capped verdict — never arbitrary start/end years.

**6. Search guard.** Use **show the search** + **cap narrowed verdicts**, and fold formal split tests into the **existing Holm family** (guard 3 for confirmatory tests only). Capping is honest, not hiding: still show the plain numbers; the card simply refuses “Consistent difference” on a post-hoc cut unless the default all-assets study already shows the same direction at “Some difference” or better. Showing every attempt (Harvey / Bailey–Borwein–López de Prado disclosure) matters more than any single p-value tweak.

**7. Self-confirming scopes.** Warning-only is too weak. For v1, **do not offer Chosen assets**, so the table cannot feed a confirmatory study. Later: require a **time split** — assets flagged on period A, tested only on period B (non-overlapping, both before the hold-out) — or require the Chosen list to be declared before the per-asset table is shown (pre-registration). Same-sample “best coins → re-study” must be refused or labelled non-evidence.

**8. Pinned assets.** Calendar-block resampling is necessary and already the right joint-date defence, but not sufficient alone. Also show **concentration**: unique calendar weeks / unique pin-event dates, and top-date share of episodes. If most coin episodes sit on a handful of Bitcoin Yes days, effective N is those days — raise Too few when unique pin-event weeks are scarce (reuse the 40-week spirit on pin dates). Do not treat 700 coin rows as 700 independent Bitcoin stories.

**9. Wording.** Split: “Among coins / among shares — same method, fewer episodes. A part can look different by luck.” Per-asset: “Guide only. Outside the chance band means ‘look closer,’ not ‘this Set works on this coin.’” Count line always above the table. Narrowed (later): “Exploratory cut. Highest label here is Some difference, not established, unless the all-assets study agrees.” Never “works,” “edge,” or green ticks on unusual assets.

**10. Market practice.** Event-study and trial guidance: pre-specify primary analysis; report all subgroups tried; label post-hoc cuts exploratory; correct multiplicity (Holm / BH); test interaction when claiming crypto ≠ equity rather than shopping separate p-values (CONSORT subgroup advice; EventStudy multiplicity docs). Finance: disclose the search (Harvey 2017; Bailey–Borwein–López de Prado honest backtest templates). Copy disclosure and exploratory labels; avoid product UIs that rank symbols by backtest score.

**11. Simplify.** Leave out of v1: Chosen assets, free year spans, Crypto/Equities as separate queued studies, per-asset p-values, funnel plots, and “Consistent difference” on any non-default cut. Keep: always-on split beside the pooled headline; per-asset guide + luck **count**; shared Holm for pool+split; search log even when only the default + split exist.

## 3. Traps we missed (most serious first)

1. **Interaction shopping** — declaring “crypto differs” from two separate p-values without testing whether crypto and equity differences differ.
2. **Measure shopping inside a slice** — Gain first vs Move vs Size still multiply looks; the family must include every measure shown.
3. **Pin-date collapse** — many assets, one Bitcoin day, looks like a large N.
4. **Comparable-day mismatch in thin slices** — year×trend baseline cells go empty; silent drop of episodes can bias a crypto-only cut.
5. **Survivorship already in the 86** — coin-only views overweight names that lasted; dip/fade Sets look kinder.
6. **UI ranking** — sorting the per-asset table by gap invites the Chosen trap even without a Chosen button.
7. **Cross-Set search** — users try many Sets then many cuts; run-level Holm helps Sets, not the human’s private tour unless the card lists attempts per Set.
8. **Hold-out peeks via “which years looked good live”** — year tools make informal post-2024 impressions easy to recreate pre-hold-out.
9. **Double use of consistency periods** — if year presets are those same three blocks, they are no longer independent checks for Consistent difference.

## 4. Recommended first version

**Build:**

1. On every What followed card: **pooled headline unchanged**; beside it, **Coins** and **Shares** panels with plain numbers, week counts, and a verdict only if ≥ 40 weeks and tests enter the **same Holm family** as the pool (replace sign-only kind checks in consistency).
2. A **per-asset guide** under the fold: episode count; gain-first / move (or size) vs that asset’s comparable days; “too few” under 15 episodes; **no per-asset p-values**; luck line on the **count of unusual assets** (prefer blockish null); default sort by asset name or episode count, **not** by gap.
3. A one-line **study log** on the card: “Default + coins + shares” (and later any scopes).

**Thresholds:** 40 weeks for any verdict; 15 episodes to show per-asset gaps; hold-out untouched.

**Search guard:** show the log; split is pre-specified not searched; no user scopes in v1; cap any future scope at “Some difference, not established” unless the default agrees.

**Wording:** exploratory labels as in Q9; unusual ≠ works.

**Leave out:** Chosen assets, year picker, duplicate crypto/equity study requests.

**Check:** Breakout-fading card shows coin vs equity plainly under No clear difference; fixtures for thin crypto weeks → Too few; pin-Set card shows unique event-week concentration; sorting by gap is impossible or clearly discouraged.

## 5. Sources

- Internal: `what_followed.py` (episodes, ATR outcomes, `consistency`, verdicts); `research_stats.py` (studentised block bootstrap, Holm); `what_followed_run.py` (2014-09-17…2024-10-29 cut).
- Harvey, C. R. (2017), “The Scientific Outlook in Financial Economics,” *Journal of Finance*: https://doi.org/10.1111/jofi.12530 · PDF https://people.duke.edu/~charvey/Research/Published_Papers/P131_The_scientific_outlook.pdf
- Bailey, Borwein, López de Prado — honest multiple-test disclosure: https://doi.org/10.3905/jpm.2018.45.1.141 · https://doi.org/10.3905/jfds.2019.1.099
- Subgroup / cherry-picking practice: https://manuelgarcia.info/guides/research/guide/subgroup-analysis-cherry-picking
- EventStudy multiplicity (Holm / BH): https://eventstudy.de/docs/inference-robustness
- CONSORT 2025 subgroup reporting (via above guide): report which subgroups, prespecified vs post hoc, and how many were tried.
