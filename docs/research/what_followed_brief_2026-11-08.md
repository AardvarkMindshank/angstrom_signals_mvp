# What followed — design brief for review

8 Nov 2026 · Angstrom Signals

## Purpose

We want each Set in Angstrom Signals to carry a "What followed" card. The card should tell a newcomer honestly whether, in the past, a Yes was followed by anything different from ordinary days. It must be credible and must not mislead. If the honest answer is "we can't tell", the card must say so plainly.

We ask you, as a reviewer, to:

1. Critique the measures proposed below, and say which to keep, change or drop.
2. Name traps we have missed that could make a Set look better (or worse) than it is.
3. Propose simpler or better designs, including established methods from quantitative finance or event studies.
4. Recommend one design for the first version, small enough to build and explain.

## Context

Angstrom Signals is a dashboard for crypto and US equities. Repo: [github.com/AardvarkMindshank/angstrom_signals_mvp](https://github.com/AardvarkMindshank/angstrom_signals_mvp). Its design runs Signals → Groups → Sets → Prism.

- **Signal:** one indicator reading, such as RSI or the 50-day average.
- **Group:** several signals combined into a score from −100 to +100 with a label, such as Trend: Bullish.
- **Set:** a Yes / No / Unknown answer built from Groups and signals, such as "Pullback in an uptrend: daily Trend ≥ +30 and Stretch ≤ −30".
- **Prism:** scans Sets across assets. Its "Visualize History" view already shows each Set's daily Yes/No as coloured bands under the price, over each asset's full history.

Facts that shape this design:

- **Answers are daily**, worked out from daily candles as they stood at each close (no look-ahead). Weekly candles are built from the daily ones.
- **History is long:** Yahoo "max" history, often 10 to 40 years for shares and 2014 onwards for major coins. About 18 assets have been checked so far.
- **Yes is rare for setups:** about 2–5% of days for the provided setup Sets, and about 24% for the quiet-market (squeeze) Set.
- **A protected hold-out:** data from 30 Oct 2024 onwards must never be used for measuring or tuning. Studies use earlier data only. We plan one final check on the hold-out later.
- **Not every Set predicts a direction.** "Squeeze" (unusually quiet trading) says a move may come but not which way. "Overextended" is a caution, not a sell signal. "Bitcoin in an uptrend" is a filter for other coins.
- **The users are newcomers to trading** and mostly read on phones. Wording must be plain, and any number shown must be hard to misread.
- **Existing tools:** the repo has research helpers for bootstrap confidence intervals and multiple-testing corrections.

## The problem

The first plan was blunt: after a fresh Yes, did price rise over the next 5, 10 and 20 days, compared with ordinary days? The project owner felt this was too absolute, and suggested a more nuanced "confidence" built from measures such as:

- **Proximity:** how soon after the first Yes (or a run of Yes days) did price move, and did the move last?
- **Correlation with the run:** do longer runs of contiguous Yes days go with bigger moves?

The owner asked for these to be challenged and for better or additional measures. The aim is evidence that a newcomer can trust. A card that looks impressive but reflects luck, a rising market or a quirk of the method would do real harm, because users may act on it.

## Proposed measures

Each measure is taken from the close of the day a fresh Yes appears. A **fresh Yes** starts an episode: the first Yes after at least 5 days without one, so a run of 20 Yes days counts once. Moves are measured in **typical daily moves** (the asset's 20-day average true range at that close), so Bitcoin and Apple can be compared. Every measure is also taken for **ordinary days**: the same asset, the same years, days that are not fresh Yes days.

| Measure | Plain question | How it is worked out |
| --- | --- | --- |
| Gain first | How often did price rise by one typical move before falling by one? | Walk forward day by day up to 20 days; record which barrier is touched first, or neither. Same-day touches count as neither. |
| Typical move after | Where was price after 5, 10 and 20 days? | Median and spread of the change from the Yes close, in typical moves. |
| Along the way | How far did it go for you, and against you, before day 20? | Best and worst close within the window (maximum favourable and adverse excursion). |
| Time to move | How soon did a clear move happen? | Days until price first moved one typical move either way. This is the owner's "proximity" idea. |
| Size regardless of direction | Did a bigger move follow, in either direction? | Absolute change after 10 and 20 days. For Sets that do not predict a direction, such as Squeeze. |
| Run length (later) | Do longer Yes runs come with bigger moves? | Only from what was known on each day: "on day k of a run, what followed from that day?" Never from the run's total length, which is known only after it ends. |

Confidence would not be one blended score. It would rest on four checks, shown separately:

1. **Difference:** fresh-Yes results against ordinary days, with a bootstrap interval that resamples whole episodes.
2. **Sample:** the number of separate episodes. Below a minimum (for example 30 across all assets) the card says "too few to judge".
3. **Consistency:** whether the difference points the same way in different periods (for example 2014–18, 2019–21 and 2022 to Oct 2024) and in coins versus shares.
4. **Correction for many looks:** how many Sets, measures and horizons were tested, with a multiple-testing correction applied before any verdict.

## Traps we already see

- **Rising markets flatter everything.** Most of this history is a bull market, so almost any Yes is followed by gains. Only the gap against ordinary days counts. Should ordinary days also be matched by market state, such as the asset's own trend at the time?
- **Run length is circular.** A run of Yes days often lasts longer because price is already moving. Comparing total run length with the move would show a strong link even if day one predicted nothing.
- **Overlapping days are not independent.** Neighbouring days share most of their future window. Counting each Yes day separately makes the evidence look 10 to 20 times stronger than it is.
- **Assets move together.** Coins mostly follow Bitcoin, and shares share market crashes. Fifty episodes in the same week of March 2020 are closer to one episode than fifty.
- **Many looks find something.** Around 10 Sets, 5 measures and 3 horizons make 150 chances for luck. One "significant" result is expected by chance.
- **Survivorship.** The assets tracked today are ones that survived. Coins that went to zero are missing, which may favour Sets that buy dips.
- **Data quality.** Early crypto history has thin, patchy volume and some odd candles. Share prices are split-adjusted, and some are dividend-adjusted.
- **Costs and fills.** Results ignore fees, spreads and slippage, and assume the close price was available. That is fine for describing what followed, but it must not read as profit.
- **Tuning by looking.** If we change a Set's thresholds after seeing its card, the card stops being evidence. That is why the hold-out from 30 Oct 2024 stays untouched.
- **Mixed Set types.** Directional, direction-neutral and filter Sets need different questions. One verdict scale may suit them badly.

## Proposed card and verdict wording

The card would sit with each Set in Prism and in its explanation. It would be worked out in automated checks on saved prices, never live, and dated. Draft for "Pullback in an uptrend" (the numbers are made up):

> **What followed** · 2014 to Oct 2024 · 18 assets
>
> 212 separate times this turned Yes.
>
> **Gain first:** 56% of the time, against 52% on ordinary days.
>
> **Along the way:** typically up 1.8 and down 1.1 typical moves within 20 days.
>
> **Consistency:** pointed the same way in 2 of 3 periods, and in coins and shares.
>
> **Verdict:** some difference, not established.
>
> Past patterns, before costs. Not a forecast.

The verdict uses one of four phrases:

| Verdict | When |
| --- | --- |
| Too few to judge | Fewer separate episodes than the minimum |
| No clear difference | The interval for the difference includes zero, after correction |
| Some difference, not established | The difference is clear on its own but fails correction, or is not consistent across periods |
| Consistent difference | Clear after correction, the same way in every period, and in both coins and shares |

The Set's 🔬 "not yet studied" mark would change to match the verdict. No verdict would ever say "works", "profitable" or "reliable".

## Questions for reviewers

1. **Measures:** Which of the six measures would you keep for the first version? What is missing, such as hit rate at a fixed horizon, win/loss ratio, or volatility expansion?
2. **Barriers:** Is "one typical move up before one down" (a triple-barrier style test) a good core measure? What barrier size and time limit would you use, and should the barriers be asymmetric?
3. **Baseline:** Is "ordinary days, same asset, same years" a fair baseline? Should it be matched by market state, by the asset's own trend, or replaced with random dates?
4. **Episodes:** Is a 5-day gap a sensible rule for a fresh Yes? How should the dependence between assets on the same dates be handled (block bootstrap by calendar period, clustering by date)?
5. **Run length:** Is the owner's run-length idea worth keeping, in the "day k of a run" form or another? Is there a sound way to show "how close to the first Yes the move came"?
6. **Confidence:** Should the card show the four checks separately, or is there a defensible single confidence figure a newcomer can read without being misled?
7. **Thresholds:** What minimum number of episodes, which multiple-testing correction (for example Benjamini–Hochberg or Holm), and which periods would you use?
8. **Set types:** How should direction-neutral Sets (Squeeze) and filter Sets (Bitcoin in an uptrend) be studied and worded?
9. **Wording:** Is the verdict scale clear and honest for newcomers? Is anything on the draft card likely to be misread as a promise?
10. **Market practice:** How do comparable products (for example TradingView strategy reports, TrendSpider, Koyfin, or academic event-study practice) present this, and what should we copy or avoid?
11. **Simplify:** What can be cut from the first version without losing credibility?

## Reply format

Please reply in this order, in plain words, and keep it under about 1,500 words:

1. **Verdict on the approach:** sound, sound with changes, or rethink, in one or two sentences.
2. **Answers to questions 1–11,** numbered to match.
3. **Traps we missed,** most serious first.
4. **Your recommended first version:** the measures, baseline, episode rule, thresholds and verdict wording.
5. **Sources:** links to any methods or products you cite.

If you can read the repository, the relevant code is in `set_history.py` (daily Set answers over history) and `research_stats.py` (bootstrap and multiple-testing helpers).
