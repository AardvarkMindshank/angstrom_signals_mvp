# The funnel: a dynamic watchlist in stages — design brief for review

10 Nov 2026 · Angstrom Signals

## Purpose

An experienced crypto trader (Drew, a beta tester) scans hundreds of coins by hand every day. He narrows them down in stages, from long timeframes to short, until a few coins agree across every timeframe. Then he decides which of those are ready now and which to watch. We want Angstrom to do the narrowing for him, across up to the top 500 coins, and alert him.

We ask you, as a reviewer, to:

1. Critique the design below: the stages, the table, the timing and the wording.
2. Name traps we have missed, especially anything that could mislead a trader or flood him with noise.
3. Recommend one design for the first version.

## How Drew works today (his words, lightly edited)

> "Filter first on the daily (say from 500 to 100), then the 12-hour, then the 4-hour. Each time the list gets smaller. Once the shortlist is down (say 4), look at the 1-hour to see which ones meet the criteria to trade now. The rest (3) go in a shortlist for checking, like a TradingView flag. So you end up with a condensed list that has confluence across the timeframes. Trend could be up or down, but the trend is your friend. Then on the 1-hour and 30-minute I look for the position: golden pocket, candle structure, support and resistance, fair value gaps, liquidity, Max Pain, the liquidation heatmap, overbought or oversold. No exact number, more a range."

This brief covers the narrowing only (up to "ready now" and "flagged"). The entry zone (the confluence of levels on the 1-hour and 30-minute) is a later, separate brief.

## Context

Angstrom Signals is a dashboard for crypto and US equities. Repo: [github.com/AardvarkMindshank/angstrom_signals_mvp](https://github.com/AardvarkMindshank/angstrom_signals_mvp).

- **Sets** are Yes / No / Unknown answers built from indicator readings on any timeframe from 15 minutes to weekly (30m and 12h added today), read from closed candles only. Unknown is never turned into Yes or No.
- **Prism scans** run a Set over a list of assets, on demand or at each candle close, with alerts when an asset turns Yes.
- **Tables** on the main page list the person's watchlist (coins and equities), with columns for chosen readings and Sets.
- **Data:** crypto candles are moving to Binance's public market data (every timeframe natively; reachable from our servers). The longlist would be CoinGecko's top coins by market cap that trade on Binance against USDT, without stablecoins and wrapped coins.
- **Users** range from newcomers to experienced traders. Nothing in the app may read as advice to buy or sell.

## Proposed design

**Two kinds of table.** Above the crypto table, a switch: **My Watchlist** (the coins the person picked, as today) or **Dynamic** (coins chosen by the funnel).

**The funnel.** A funnel is a short ordered list of stages, each a saved Set on its timeframe:

| Stage | Example (long side) | Checked at | Icon |
|---|---|---|---|
| Pool | the longlist: top N coins on Binance | daily | ⚪ |
| 1 · Watchlist | Daily: EMA 20 above EMA 50 | each daily close | 👁 |
| 2 · 12h | 12h: EMA 20 above EMA 50 | each 12h close | 🔷 |
| 3 · Shortlist | 4h: EMA 20 above EMA 50 | each 4h close | 📋 |
| 4 · Candidate | 1h: the entry rules hold now | each 1h close | ✅ |
| 4 · Flagged | on the shortlist, 1h rules not yet met | each 1h close | 🚩 |

Each stage checks only the coins that passed the stage before. A coin's place is shown as an **icon column** in the table.

**A stage picker** above the Dynamic table chooses what to show: *Watchlist · Shortlist · Candidates · Flagged*, with counts, e.g. *312 → 41 → 9 → 2 ✅ / 7 🚩*.

**Long and short.** A funnel has a direction. The person runs a long funnel, a short funnel, or both. The table shows ▲ / ▼ beside the stage icon.

**Alerts** (optional, per stage): when a coin becomes a Candidate, and optionally when it is Flagged. They use the existing alert channels (in-app, instant email, daily summary).

**A chart for each Candidate and Flagged coin,** opened from the table, with the funnel's readings drawn, so the trader can check by eye (his request).

**Transparency.** Hovering a coin's stage icon shows which stage it reached, which line stopped it, and when each stage was last checked.

## Questions for reviewers

1. **Structure:** Is "each stage checks only the survivors of the stage before" right, or should every stage check every coin (so a coin can show 4h agreement while the daily is still pending)? What happens when a higher stage turns No while a lower stage is still Yes?
2. **Timing:** Stages run at their own candle closes (daily, 12h, 4h, 1h). When the daily stage drops a coin, should it leave the shortlist at once, or at the next close of each lower stage?
3. **Flapping:** Coins near a threshold will move in and out of stages. Should there be hysteresis (for example, a coin stays on the shortlist until it fails twice), and how would you explain that honestly?
4. **Unknown:** A coin with missing data at one stage: drop it, hold it at its last stage, or show it as ❔? 
5. **Wording:** "Trade now" reads like advice. We propose "Candidate" (entry conditions met: a coin to look at now, not a recommendation). Is it clear enough? Better words for each stage and icon, for both newcomers and experienced traders?
6. **Credibility:** What minimum history, trading volume and data quality should a coin need before it can enter the pool? How should thinly traded coins be handled?
7. **Noise:** With 300+ coins and hourly checks, how do we avoid alert floods (batching, limits, only on stage changes)?
8. **Long and short:** One funnel with a direction switch, or two separate funnels? How should a coin in both (rare, but possible on mixed timeframes) be shown?
9. **Evidence:** Should a funnel carry a study (what followed coins becoming Candidates, in the past), as single Sets do? Any traps in studying a multi-stage selection?
10. **Market practice:** How do comparable tools (TradingView screeners and alerts, TrendSpider, Coinigy, 3Commas, CryptoQuant screeners) present multi-timeframe screening? What should we copy or avoid?
11. **Simplify:** What should the first version leave out?

## Reply format

Please reply in this order, in plain words, under about 1,500 words:

1. **Verdict on the approach:** sound, sound with changes, or rethink, in one or two sentences.
2. **Answers to questions 1–11,** numbered to match.
3. **Traps we missed,** most serious first.
4. **Your recommended first version:** stages, timing, flapping rule, wording and alerts.
5. **Sources:** links to any products or methods you cite.

## Decision after review (10 Nov)

Reviews: ChatGPT, Gemini and Grok, all "sound with changes". The owner chose the two open points.

1. **Stages:** Universe → Daily → 12h → Shortlist (4h) → **Candidate** (1h entry rules hold) or **Flagged** (on the Shortlist, 1h not yet). A funnel has 3 or 4 narrowing stages; each is a saved Set pinned to its version. "Watchlist" is not a stage name.
2. **Qualification:** a Candidate passes every stage. Stages are checked for the survivors of the stage before; a coin not reached shows "not checked", never No.
3. **A higher stage fails:** the coin drops at once to the highest stage that still passes.
4. **Flicker (owner's choice b):** entry is immediate; a coin leaves the Shortlist or Candidates only after two No closes in a row on that stage's timeframe, shown on screen ("stays until it fails twice"). Switchable per funnel.
5. **Unknown:** ❔ Pending data. Never promotes, never alerts, keeps the last stage only as history; after a few closes of missing data the coin drops out.
6. **Universe and quality gate:** Binance USDT spot pairs from CoinGecko's top coins, without stablecoins, wrapped and leveraged tokens; a minimum trading volume on Binance; enough closed history for every Set. Exclusions are listed with their reason. Start at the top 200; 500 after load is measured.
7. **Long and short:** separate results and alerts per direction; a coin in both shows ▲ and ▼.
8. **Wording (owner's choice):** "Candidate" (conditions met, not a recommendation) and "Flagged" with a hover: "On the shortlist: the daily, 12h and 4h agree; waiting for the 1-hour entry conditions."
9. **Alerts:** only on newly becoming a Candidate; one batched message per run; latched until the coin leaves and returns; hourly cap.
10. **Transparency:** per-stage last-checked times, the deciding line, data venue (Binance spot), a health mark for failed or late runs; counts always reconcile (Pending and not-checked included).
11. **Not in version 1:** funnel studies (survivorship), the entry zone, a chart gallery (a link to each coin's chart instead), automation.
