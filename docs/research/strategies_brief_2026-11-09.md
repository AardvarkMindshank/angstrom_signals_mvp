# Strategies — design brief for review

9 Nov 2026 · Angstrom Signals

## Purpose

We want to add Strategies to Angstrom Signals: a layer above Sets that says when a setup starts, how a position would be built up and wound down in steps, and when it ends. It should describe and test trading ideas honestly. It must not become an order-placing robot or a source of advice.

The owner wants this designed before the AI advisor, because the advisor's "turn my idea into a setup" job is mostly about strategies.

We ask you, as a reviewer, to:

1. Critique the proposed shape: what to keep, change or drop.
2. Say where the line between describing and advising should sit, and how to hold it.
3. Name the traps in judging strategies on past data that we have missed.
4. Recommend one small first version that is worth building and easy to check.

## Context

Angstrom Signals is a dashboard for crypto and US equities. Repo: [github.com/AardvarkMindshank/angstrom_signals_mvp](https://github.com/AardvarkMindshank/angstrom_signals_mvp). Its design runs Signals → Groups → Sets → Prism, with Strategies shown as "later" in Angstrom Lattice.

What already exists:

- **Sets** answer Yes / No / Unknown about one asset at the last finished candle, from Groups and single signals (daily, weekly, 4-hour, hourly).
- **Prism** scans Sets across the watchlist on a schedule and alerts on change, never on Unknown.
- **Point-in-time replay** rebuilds what was known at any past candle, for every signal certified for it.
- **Visualize History** shows a Set's daily answers as bands under the price.
- **What followed** studies what happened after a fresh Yes, against comparable days, before a protected hold-out (30 Oct 2024), with block resampling, a multiple-test correction and four fixed verdicts.

Decisions already taken that this design must respect:

- A Set is an analysis, not a strategy: it has no entry, exit or risk rules.
- The capability reviews (7 Nov) ranked **sequences** inside a Set ("A, then B within N candles") as the most valued extension, preferably as an alert-only state (Waiting → Armed). They also warned: no profit-and-loss "theatre" before risk rules exist.
- Risk tools (stops, sizing) were marked out of scope "to keep the product descriptive, not advice". Strategies are where that has to be decided properly.
- The product describes; it never places orders or tells anyone to buy or sell.

A research note on visual strategy builders ([docs/research/visual_strategy_builders.md](https://github.com/AardvarkMindshank/angstrom_signals_mvp/blob/main/docs/research/visual_strategy_builders.md)) compares TradingView, TrendSpider, Composer, 3Commas, Kryll, NinjaTrader and Option Alpha. Its main lessons: attach rules to a stage, draw the ladder before any test, and when two exits can be true on one candle, show which one wins.

## Four worked examples

The design should handle these real cases from the owner and his trading collaborator, Drew.

| Example | What the trader wants | What it needs beyond today's Sets |
| --- | --- | --- |
| The daily trawl | Drew looks through many assets every day for the same setups, to pick a short list for closer study | Mostly covered by Prism scans and alerts; a strategy adds "what happens next" for each shortlisted asset |
| Drew's rule script | A TradingView script that checks conditions in turn, moving to the next check only when the previous one passes, with AND / OR logic; unfinished because the script became too complex | Stages that run in order, each with its own conditions, and a clear record of which stage an asset is in |
| Coinbase leads Bitcoin | Drew's belief that a rise in Coinbase's share price can come before a rise in Bitcoin | One asset's reading followed by another asset's reading within a delay ("A on Coinbase, then B on Bitcoin within N candles") |
| Laddering | Building into a trade in steps and taking profit in steps, Drew's usual approach | Rungs: how much at each step, at what distance, and where the plan is abandoned; drawn before any test |

## Proposed shape

A strategy is a plan for one asset at a time, built from the pieces that already exist. Each asset in a strategy is in exactly one stage, and each stage has its own rules.

Stages (a diagram in the online version of this brief):

**Watching** (waiting for the entry Set) → **Armed** (entry met; first rung waiting) → **Building in** (rungs fill as price reaches them) → **Managing** (exit rules and steps out) → **Done** (exit reason recorded).

An asset that is Armed but never reaches its first rung returns to Watching. An asset that is building in can be abandoned at a pre-set invalidation level.

- **Entry:** a Set, or a sequence of Sets, possibly on different assets: "Pullback on ETH", or "Coinbase turns bullish, then Bitcoin's trend turns bullish within 5 daily candles". Sequences are the Stage C extension the reviews ranked first; strategies would use them, not reinvent them.
- **Ladder in:** rungs placed in the asset's typical move (its average daily range), not in fixed prices, for example 40% at the entry close, 30% one typical move lower, 30% two lower. The ladder is drawn on the price before any test, with the average entry after each rung.
- **Ladder out and exits:** take-profit steps (also in typical moves), an invalidation level, a time limit, and exits on a Set ("the entry Set turns No" or another Set turns Yes). One fixed order decides which wins when two could happen on the same candle.
- **Sizes are shares of a plan, never money.** "30% of the planned position", not $3,000. There is no account balance, leverage or order in Angstrom.
- **Same pieces everywhere.** A strategy references Set versions; changing a Set makes a new strategy version, as Prism does today.

## The boundary: describe, not advise

We propose three levels and stop at the second.

| Level | What it does | In scope? |
| --- | --- | --- |
| 1. Track | Follows each watched asset through the stages and alerts when it moves on ("ETH is Armed", "rung 2 reached", "plan abandoned") | Yes, first |
| 2. Study | Shows how the plan would have played out on the past, in typical moves and shares of the plan, against simple baselines, before the hold-out | Yes, second |
| 3. Act | Account balances, money amounts, leverage, orders sent to a broker or exchange | No |

Words that hold the line:

- A stage change is reported as a fact about the plan ("rung 2 of your plan was reached at the close"), never as an instruction ("buy now").
- Ladders and stops are the user's own plan, shown back to them. Angstrom does not suggest sizes, stops or targets, and the provided library would not include ready-made trading plans at first.
- Studies keep the What followed wording and verdicts. No equity curve as a headline, no "win rate", no "profit factor".

We would like reviewers' views on whether level 2 can stay on the describing side of the line, and what it would take.

## Judging a strategy honestly

A strategy study is harder than What followed, because a plan has many more choices to fit to the past. Proposed rules:

1. **Same discipline as What followed.** Data before 30 Oct 2024 only, outcome windows that end before it, episodes grouped by date, calendar blocks resampled across assets together, a correction for the number of tests, and the four verdicts.
2. **Fills that could have happened.** Signals read at the close; the earliest fill is the next candle. A rung or stop inside a candle's range is filled at its level only if the range reached it; when both a stop and a target fall inside one candle, the stop is assumed first. Costs and slippage are assumed and stated (for example 0.1% a side for coins and 0.05% for equities, to be agreed).
3. **Compared with something simple.** The same ladder and exits started on random days, the same ladder started on every entry-Set Yes without the sequence, and simply holding the asset over the same windows.
4. **Reported as a distribution, not one number.** The typical result per plan, the range of results, the worst stretch, how long plans lasted, how often each exit reason ended them, and how often a plan never filled.
5. **Choices count as tests.** Every ladder spacing or exit level tried is recorded; trying many and showing the best is tuning, and the card says how many were tried.
6. **The hold-out stays sealed** until a strategy's design is frozen, for one final check.

## Risks we already see

- **Advice by another name.** A plan with rungs, stops and alerts can feel like a trading signal service even when worded carefully.
- **Fitting the past.** Ladders have many dials; the best-looking combination is usually luck.
- **Unrealistic fills.** Daily candles hide the order of prices within a day; laddering into a falling knife looks better on daily data than it was.
- **Survivorship.** The saved assets are large ones that survived; dip-buying ladders look better on survivors.
- **Complexity for newcomers.** Stages, sequences and ladders are a lot to hold at once; Drew's script stalled for exactly this reason.
- **Scope creep toward execution.** Once plans exist, connecting a broker is the obvious next request, and it changes the product's legal and safety position.
- **Data limits.** Hourly and 4-hour history is short, and positioning history starts in 2020; many strategies will only be studyable on daily data.

## Proposed first version

Build in three small steps, each useful on its own.

1. **Sequences inside Sets.** "A, then B within N candles", where A and B can read different assets. This covers Coinbase leads Bitcoin and the step-by-step part of Drew's script, and every Set screen, scan and study gains it at once.
2. **Tracked plans (level 1).** A strategy = an entry (a Set or sequence), a ladder in, exits and a ladder out, all in typical moves and shares of the plan. Prism-style tracking puts each watched asset in a stage and alerts on stage changes. The ladder is drawn on the chart before anything is saved.
3. **Plan studies (level 2).** The study rules above, run in the background like What followed, with the result on the strategy's card.

Out of the first version: money amounts, leverage, shorting, portfolio-level rules (several strategies sharing one budget), intraday fills, broker connections.

## Questions for reviewers

1. **Shape:** Are the stages (Watching, Armed, Building in, Managing, Done) the right model? What is missing or unnecessary?
2. **Sequences first:** Is building sequences inside Sets before strategies the right order, or should sequences live only in strategies?
3. **Ladders:** Is "rungs in typical moves, sizes as shares of the plan" a good way to describe laddering in and out? How do comparable products present ladders clearly?
4. **Exits:** Which exit types belong in the first version, and what fixed order should decide between exits on the same candle?
5. **The boundary:** Can tracked plans and plan studies stay descriptive rather than advice? What wording, defaults or limits would you add?
6. **Studies:** Are the proposed study rules enough? What baselines, cost assumptions and fill rules would you use on daily data?
7. **Overfitting:** How should the product count and show the variations a user has tried?
8. **Coinbase and Bitcoin:** How would you test a lead-lag idea between two assets fairly, given that both mostly move with the wider market?
9. **Newcomers:** How can a beginner build a plan without being overwhelmed? Templates, a guided form, or the AI advisor?
10. **Market practice:** Which products handle stages, ladders and honest testing well, and what should we copy or avoid?
11. **Simplify:** What can be cut from the first version without losing its value?

## Reply format

Please reply in this order, in plain words, under about 1,500 words:

1. **Verdict on the approach:** sound, sound with changes, or rethink, in one or two sentences.
2. **Answers to questions 1–11,** numbered to match.
3. **Risks we missed,** most serious first.
4. **Your recommended first version:** what it does, what it leaves out, and how it is tested.
5. **Sources:** links to any products or methods you cite.

If you can read the repository, see `docs/design/groups_sets.md` (Sets), `docs/design/lattice_prism.md` (Prism), `docs/research/visual_strategy_builders.md` (competitor research) and `what_followed.py` (the study method).
