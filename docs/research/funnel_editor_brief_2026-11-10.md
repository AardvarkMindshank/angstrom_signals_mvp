# Funnels, version 2: an editor, shared answers and own pools — design brief for review

10 Nov 2026 · Angstrom Signals · [github.com/AardvarkMindshank/angstrom_signals_mvp](https://github.com/AardvarkMindshank/angstrom_signals_mvp)

## Purpose

Version 1 of the funnel (a dynamic watchlist in stages) went live today, built on your earlier reviews
([funnel_brief_2026-11-10.md](funnel_brief_2026-11-10.md), "Decision after review"). We now want people to build and
change their own funnels, and the system to stay fast and cheap as users grow. We ask you, as a reviewer, to:

1. Critique the design below.
2. Name traps we have missed, especially anything that could mislead a trader, cost a lot to run, or confuse a newcomer.
3. Recommend one design for this version.

## What exists today (version 1)

- **Architecture.** Signals → Groups → Sets → Prism (scans and alerts). A Set answers Yes / No / Unknown from indicator
  readings on any timeframe (15m to weekly), on closed candles only. Provided objects are built from copyable blocks;
  people start from a provided one and make their own copy.
- **Funnels.** A funnel is a direction (long or short) and 3–5 stages, each a pinned copy of a Set on its timeframe.
  Two ready-made funnels per market: crypto daily (trend + momentum turning) → 12h → 4h → 1h entry; shares weekly →
  daily (trend + momentum turning) → 4h (session-based) → 1h entry. A coin enters a stage on its first Yes and leaves
  after two No closes in a row; Unknown shows ❔ Pending and never promotes. A Candidate holds every stage; Flagged holds
  all but the last.
- **Pools.** Crypto: CoinGecko's top 500, without stablecoins, wrapped/staked/bridged copies, gold, tokenised shares and
  funds, other exchanges' tokens; candles from Binance spot (≥ $250k a day, no gappy hours, 200 days), else Yahoo
  (≥ $1M a day across exchanges, complete hourly candles). About 200 usable. Shares: the S&P 500 (price ≥ $5, ≥ $20M a
  day, ~3 years of history); about 495 usable.
- **The job.** Hourly (started by the 5-minute worker). Each stage is checked at its own candle close, only for the
  assets holding every stage before it, through the same point-in-time reconstruction Prism uses. One claimed run per
  (funnel, stage, close). A run takes a few minutes for ~200 coins or ~500 shares per stage.
- **On the page.** The crypto and equity tables switch between My Watchlist and Dynamic funnel; a stage picker with
  counts; a Stage icon column with a hover (each stage's last answer, the data source, earnings within two weeks);
  "Open candidates in chart" (the stage's 12 largest assets in a history view with the daily stage drawn as bands).
- **Alerts.** One batched note when assets newly become Candidates. New Candidates (only) get a fresh news-sentiment
  reading, refreshed every 12 hours while they stay Candidates.
- **Each person's funnel is evaluated separately,** even when it is identical to someone else's.

## Proposed design

**1. A 🔻 Funnels section in Lattice** (next to Groups, Sets and Prism), with the same pattern as Sets:
"Start from" a ready-made funnel or one of your own; edit; save as a new version.
- Stages: add, remove, reorder (3–5). For each stage: a Set (provided or your own), its timeframe, and a label.
- Funnel settings: direction, market (crypto or shares), pool (below), the flicker rule (two No closes, or one),
  alerts (in-app, instant email, daily summary, off).
- Checks before saving: each stage's Set must be scannable (has a decision) and readable on that stage's timeframe;
  stages should run from longer to shorter timeframes (a warning, not a block); the funnel's history needs must fit the
  pool (for example a weekly EMA 50 needs ~3 years).
- Changing the stages starts every asset again from the pool (as today).
- Funnel notifications open the funnel here.

**2. Shared answers.** A Set's answer for an asset at a close is the same for everyone. Work it out once per
(Set logic fingerprint × asset × close), store it, and let every funnel read it. Each person's funnel then only keeps
its own bookkeeping (stage states, flicker counts, latches). The cost grows with the number of *different* Sets in
use, not with users. Same idea already used for studies ("What followed"), keyed by the Set's logic fingerprint.

**3. Own pools.** Narrow the pool: top N by market cap, minimum daily volume, exclude categories (meme coins), sectors
(shares), or "my watchlist only". A pool is part of the funnel, so it is pinned and versioned with it.

**4. Limits.** At most 6 funnels per account; 5 stages; the hourly budget is shared fairly (a funnel that cannot finish
continues next hour, as today). A daily cap on alerts per account.

**5. Not in this version.** Funnel studies (what followed Candidates in the past: survivorship and multi-stage
selection), sharing funnels publicly, automated trading of any kind.

## Questions for reviewers

1. **Editor.** Is "Start from → edit → save a version" the right model for funnels, or should a funnel simply be a
   list of saved Sets (edit the Sets, the funnel follows the latest version)? Pinned versions keep results stable;
   following the latest is simpler. Which, and why?
2. **Validation.** What should block saving, and what should only warn? (Timeframes out of order, a stage Set whose
   own members are on another timeframe, a Set needing more history than the pool has.)
3. **Shared answers.** Traps in sharing answers across users? (Point-in-time correctness, Sets pinned to another
   asset such as "Bitcoin's trend", data revisions, provider failures, cache invalidation when a signal's code changes
   and is re-certified.) What should the key be?
4. **Cost.** With N users, F funnels each and ~500 assets per pool, what limits keep a single hourly job within ~25
   minutes? Is a per-Set budget fairer than a per-funnel one?
5. **Pools.** Which narrowing options matter most to traders? Should a pool be shared between a person's funnels?
6. **Newcomers vs experts.** How should the editor stay usable for a newcomer (who may only ever change a threshold)
   while giving an experienced trader full control?
7. **Wording and safety.** Anything in the editor that could read as advice? Should custom funnels carry a stronger
   "not tested" mark than provided ones?
8. **Market practice.** How do TradingView, TrendSpider, 3Commas or others let users build multi-timeframe screens?
   What should we copy or avoid?
9. **Simplify.** What would you leave out of this version?

## Reply format

Please reply in this order, in plain words, under about 1,500 words:

1. **Verdict:** sound, sound with changes, or rethink, in one or two sentences.
2. **Answers to questions 1–9,** numbered to match.
3. **Traps we missed,** most serious first.
4. **Your recommended version:** editor model, validation, shared answers, pools, limits.
5. **Sources:** links to any products or methods you cite.
