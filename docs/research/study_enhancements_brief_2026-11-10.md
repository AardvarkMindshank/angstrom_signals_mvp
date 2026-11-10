# Study enhancements — design brief for review

10 Nov 2026 · Angstrom Signals

## Purpose

"What followed" studies are live. A study asks one question of a Set: after a fresh Yes, did anything different tend to happen next, compared with comparable ordinary days? It answers with one verdict pooled over every studied asset.

Users now want to look closer: crypto against equities, asset by asset, a chosen list of assets, and a chosen span of years. Each of these is a fair question. Each also gives a user more ways to find a result that is only luck. We want to add them without weakening the study's honesty.

We ask you, as a reviewer, to:

1. Critique the four proposals below, and say which to keep, change, drop or merge.
2. Name traps we have missed, especially ways a narrowed study could make luck look like a pattern.
3. Recommend one design for the first version, small enough to build and explain to newcomers.

## Context

Angstrom Signals is a dashboard for crypto and US equities. Repo: [github.com/AardvarkMindshank/angstrom_signals_mvp](https://github.com/AardvarkMindshank/angstrom_signals_mvp). Its design runs Signals → Groups → Sets → Prism. A **Set** is a Yes / No / Unknown answer built from indicator readings, worked out from daily candles as they stood at each close (no look-ahead). A Set can read the scanned asset, or a fixed ("pinned") asset such as Bitcoin, so "Bitcoin broke out and this coin's volume is high" is one Set.

How a study works today (`what_followed.py`, from the reviews of 8 Nov):

- **Assets and years:** 86 assets (25 coins, 61 US equities), 17 Sep 2014 to 29 Oct 2024. Data from 30 Oct 2024 onwards is a **protected hold-out**: never used for measuring or tuning.
- **Episodes:** a fresh Yes after at least 5 No candles. Outcomes are taken from the next candle's close over 10 candles, in the asset's typical move (20-candle average true range).
- **Measures:** *Gain first* (rose one typical move before falling one, or the other way) and *Move* (where price ended, in typical moves). Squeeze-type Sets use *Size* (how far, either way).
- **Baseline:** each episode minus the average of the same asset's No days in the same year, on the same side of the 200-candle average.
- **Test:** differences pooled by calendar date and resampled in calendar blocks across all assets together (studentised block bootstrap), Holm correction across the tests in one run, then a consistency check: does the difference point the same way in three periods (before 2019, 2019–21, 2022–Oct 2024) and in coins and in equities?
- **Verdicts:** Too few to judge (episodes in fewer than 40 weeks) · No clear difference · Some difference, not established · Consistent difference.
- **Users** are newcomers to trading, mostly on phones. Verdicts never say "works", "profitable" or "reliable".

A real example from last night: "Breakout fading" (a structure break with high volume, then volume dropping within 5 candles). There were 1,819 episodes in 348 weeks over 86 assets (709 coin, 1,110 equity), with the verdict **No clear difference**. Price fell one typical move before rising one 47% of the time, against 45% on comparable days. The owner asked whether it might hold for one coin, or for crypto only.

## Proposals

### 1. Crypto and equities reported separately, in every study

The same test is run on coin episodes only and on equity episodes only, and each gets its own verdict on the same scale, shown beside the pooled verdict. The pooled verdict stays the headline and its method does not change.

- Each part needs enough episodes on its own (the same 40-week minimum), else Too few to judge.
- The two parts form their own correction family (2 parts × the Set's measures, Holm).
- Today the consistency check already looks at coins and equities, but only at the sign of their averages.

### 2. A per-asset table, shown as a guide and not tested asset by asset

Under the verdict, a table: each asset's fresh-Yes count, its *gain first* and *move* beside its own comparable days, and a mark for assets with too few episodes (proposed: fewer than 10). There are no p-values per asset. Instead, a **luck check** answers "how many assets would look this unusual if the Set had picked days at random?":

- For each asset, draw the same number of random No days from its comparable days, 1,000 times, giving a range that random days fall in 95% of the time.
- Mark assets outside their range, and show both counts: "7 of 86 assets look unusual; about 4 would by chance."
- Wording makes clear that an asset outside its range is a place to look, not a finding.

### 3. Choose which assets a study covers

A study request gains a scope: **All studied assets** (default), **Crypto only**, **Equities only**, or **Chosen assets** (any of the 86). Combined with pinned readings, this answers questions such as "when Bitcoin breaks out, what follows for the rest of crypto?"

- A scoped study is its own stored result, keyed by the Set and the scope. The default study is unchanged.
- The same thresholds apply, so a single coin will usually be Too few to judge, and the card says why.
- Proposal 1 may make "Crypto only" and "Equities only" redundant; we would keep them only if they add something.

### 4. Choose the span of years

A study request can also set a start and end year within 2014 to Oct 2024, never reaching the hold-out, with a minimum span (proposed: 3 years). The three-period consistency check uses the periods that fall inside the span; with fewer than two, Consistent difference cannot be reached.

## The trap we most want help with

Proposals 3 and 4 let a user keep narrowing until something looks good: try crypto, then 2019–21, then five chosen coins. Each study is honest on its own, but the search across them is not. We have three candidate guards, and would welcome better ones:

1. **Show the search.** The card says "This Set has been studied 6 ways", listing each scope and its verdict, so a lone good result is seen beside the rest.
2. **Cap narrowed verdicts.** A scoped or shortened study can reach at most "Some difference, not established", unless the same difference also holds in the default all-assets study.
3. **Count the search in the correction.** Holm covers every study of the same Set, so each new scope makes every result harder to pass.

There is also a quieter trap in proposal 2: a user may skim the per-asset table, pick the best-looking coins, then run a Chosen-assets study on exactly those coins. That study re-uses the episodes that made those coins look good, so it would confirm itself.

## Questions for reviewers

1. **Split:** Is a separate verdict for crypto and for equities sound, and is a separate Holm family for the split right? Should the split instead replace the sign-only coins/equities part of the consistency check?
2. **Per-asset table:** Is "random No days from the asset's comparable days" a fair luck check? Would you shrink per-asset numbers towards the pooled result (partial pooling), show a funnel plot, or leave per-asset numbers out entirely?
3. **Minimums:** What minimum episodes should an asset, a split part and a scoped study need?
4. **Scopes:** Are Crypto only and Equities only worth keeping once the split exists? Should Chosen assets have a minimum number of assets?
5. **Years:** Is choosing years worth its risk for newcomers? If kept, what minimum span, and should spans be fixed blocks rather than any years?
6. **Search guard:** Which of the three guards (or what else) would you use? Is capping narrowed verdicts honest, or does it hide real patterns?
7. **Self-confirming scopes:** How should a Chosen-assets study guard against assets picked from the per-asset table? For example, a split by time (pick on earlier years, study on later ones), or a warning only?
8. **Pinned assets:** For a Set pinned to Bitcoin and studied over other coins, the episodes on one date share one cause (Bitcoin's move). Is calendar-block resampling enough, or do these need treating differently?
9. **Wording:** How would you word the split, the per-asset table and a narrowed verdict so a newcomer does not read "outside its range" as "this works for this coin"?
10. **Market practice:** How do event-study research and comparable products present per-asset and subgroup results without inviting cherry-picking?
11. **Simplify:** What should the first version leave out?

## Reply format

Please reply in this order, in plain words, and keep it under about 1,500 words:

1. **Verdict on the approach:** sound, sound with changes, or rethink, in one or two sentences.
2. **Answers to questions 1–11,** numbered to match.
3. **Traps we missed,** most serious first.
4. **Your recommended first version:** what to build, the thresholds, the guard against searching, and the wording.
5. **Sources:** links to any methods or products you cite.

If you can read the repository, the study code is in `what_followed.py` (the study), `what_followed_run.py` (the queue and runs) and `research_stats.py` (block bootstrap and Holm).
