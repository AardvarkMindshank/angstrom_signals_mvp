# External review: visual strategy builders

Status: **research note, 5 November 2026**. Written for later sessions (human or AI) before a clickable Strategy Builder mockup.

This is not a design of Angstrom, and it does not redefine Signal Groups, Signal Sets, the Signal Library, or the certified historical reconstruction. Those decisions stay with the trading-domain collaborator. Patterns and walkthroughs below are proposals. Product behaviour is cited only where a vendor page was read on this date.

Nothing here is financial advice. Vendor behaviour can change after 5 November 2026.

## The useful split

The products fall into three jobs, and none of them does all three well.

- **Condition canvases** decide when: TrendSpider, Composer, NinjaTrader Strategy Builder, Kryll, Option Alpha.
- **Ladder forms** decide how much, at which prices: 3Commas DCA is the only reviewed product with a real staggered entry, and it is a form, not a diagram.
- **Code testers** document what a fill means: TradingView. Its Strategy Tester is a report on Pine Script, not a rule canvas.

A mockup that only copies one of those three will feel either clever and unrealistic, or realistic and clumsy.

## Comparison

| Product | How a trader builds it | Ladders, size, exits | Ambiguity control | Backtest vs live |
| --- | --- | --- | --- | --- |
| TradingView | Pine Script in the Pine Editor. AI Copilot writes Pine. The Strategy Tester is the report. | `strategy.entry` pyramiding defaults to 1. Several `strategy.exit` calls with `qty_percent` scale out. If `qty` and `qty_percent` are both set, `qty` wins. | Order IDs and code structure. No visual check that two exits contradict. Users can turn on fills the docs say are impossible live. | Historical bars run once on OHLC. Default fill is the next bar. Bar Magnifier uses a lower timeframe. Filling on the signal bar's close can show a trade live trading cannot make. |
| TrendSpider | The same visual AND/OR/NOT script editor as alerts and scans. One entry script, then exit scripts. Optional AI phrasing. | Cannot scale in, and cannot have two entries in a row. Any exit closes 100%. Exits: script, take profit, stop, trail, entry invalidated, N candles, signal list. | After entry, the tester only looks for the exit. A second entry while in a position is ignored. Long and short strategies must be separate. | One test timeframe. Higher-timeframe data must be painted on by a custom indicator. Using the unfinished higher bar can move old signals and stop a bot. |
| Composer | Vertical blocks: asset, weight, if/else, any/all, filter, group. Guardrails block combinations that cannot run. | Weights (equal, specified, inverse volatility, market cap), not price ladders. If/else switches the whole target allocation. | Invalid block combinations are rejected in the editor. Threshold mode will not rebalance a branch switch until the weight band is breached. | Backtests use daily adjusted closes. Live trading is a short window near the US close (normally 15:45–16:00 ET), with time and price discretion. Orders are not-held. Default slippage model is 1 basis point. |
| 3Commas DCA | A form: base order, safety-order count, deviation, step multiplier, size multiplier. | Arithmetic or geometric spacing. Take profit from the average entry or from the base order. Multiple targets. The stop should sit beyond the last rung. Breakeven-after-target only after at least two targets. | Docs warn that partial take-profit plus a mode that disables reduce-only can leave a remainder, error, or flip the position. | This is an execution bot. The form does not show an honest historical path of which rung filled inside a candle. |
| Kryll | Drag-and-drop flow. The graph is what both the backtest and the live runtime run. Buy and sell are sized as a share of capital. | Price-up, price-down, and Wait blocks can imitate steps. There is no position-ladder object with remaining quantity. | When several OR branches are true, the first connected block wins. Changing the wire order changes the trades. AND allows up to 10 conditions. | Same graph for test and live is a real virtue. Priority is still spatial, so two readers can disagree about which branch wins. |
| NinjaTrader Strategy Builder | Wizard: condition sets (all or any), actions, reusable templates. View Code at any time. | Stops and targets on that screen are static (ticks, trail, parabolic). Dynamic stops need Exit actions, or unlocking the code. | The builder errors when the two sides of a comparison have different types. Unlock Code is permanent: the builder can no longer edit that strategy. | Generated NinjaScript is what runs. The visual layer stops before order management gets subtle. |
| Option Alpha | Yes/no flowchart. Scanners open. Monitors manage. Exit Options sit on each position. | Position size on Open. Global allocation and position caps. Exit Options close when hit. Partial close exists, but the minute exit criteria close the position. | Bots refuse a duplicate action already in process. Scanners stop at the position cap. Exit Options run before monitors and scanners. | Checks are on an interval. A print between checks is invisible, except SmartStops tracked each minute. A stop fill can be worse than the level. An unfilled exit order cancels after two minutes. |

## Five patterns worth a mockup

The "verified in" column is a product fact. The "mockup" column is a proposal, not a claim about Angstrom today.

1. **Attach rules to a stage, not to a flat list.** TrendSpider looks for an exit only after an entry, and ignores another entry while in a position. Option Alpha splits scanners from monitors. 3Commas has a deal with a base order and later safety orders. A mockup can show a stage strip: flat, armed, rung filled, managing, flat. Conditions attach to a stage.

2. **Draw the ladder before any backtest.** 3Commas exposes deviation, a step multiplier, a size multiplier, arithmetic versus geometric spacing, take profit from the average or from the base order, and a stop beyond the last safety order. A mockup can show a price spine with rung size, the average after each fill, and the stop. Changing a multiplier redraws the spine before any backtest button exists.

3. **When two exits can be true on one bar, show one winner.** Kryll's OR uses connection order, and the vendor shows that this changes the backtest. TradingView's emulator can fill a stop worse and a limit better than the stated price, and same-bar OHLC does not say which was hit first. If stop, target, and invalidation can all be true on one bar, the mockup should show a single ordered list and a one-line fill assumption. Example: stop before target, and the candle only supplies a range.

4. **Higher-timeframe conditions use the last completed bar.** TrendSpider's tester is one timeframe. Painting the current weekly high onto intraday bars moved an old entry and stopped the bot. Their safe example uses the previous week's high. A regime chip such as "daily, prior close" should sit next to every higher-timeframe condition. The unfinished daily bar should be visibly unavailable.

5. **Refuse the illegal block in the editor.** NinjaTrader errors when the two sides of a comparison have different types. Composer refuses block combinations that cannot run. 3Commas documents a partial-exit mode that can flip a position. The mockup should say, in place: "this compares a score to a yes/no", "these two exits both close 100%", "the stop sits inside the ladder, so a later rung can fill after the stop". Do not ignore the rule silently.

## Five mistakes to avoid

1. **A flat rule list with no position state.** TrendSpider had to document that a second entry is ignored and that every exit is 100%. A screen of "all conditions, AND/OR, then Buy" recreates that trap as soon as someone adds a second rung.

2. **An equity curve that pretends the path inside the candle is known.** TradingView's default is one pass per historical bar, with the fill on the next bar. Bar Magnifier exists because OHLC cannot order a stop and a target. Filling on the close of the signal bar can show a fill live trading cannot make. Composer's backtest is adjusted daily closes. Live orders use a short end-of-day window and are not-held.

3. **Copying the current higher-timeframe value onto every lower bar.** In TrendSpider's weekly-high example, the 09:30 entry disappears at 10:00 because the week's high changed, and the bot is stopped. A score or daily average that includes the bar still forming will do the same thing to a point-in-time reconstruction.

4. **Priority that lives in the order of wires or list rows.** Kryll executes the first OR branch that was connected. Two people can build the same picture and get different trades. If the mockup is a canvas, priority has to be a labeled field, not a side effect of where the box was dropped.

5. **A stop quantity that does not shrink after a partial exit.** 3Commas warns that partial take-profit combined with a mode that turns off reduce-only can leave a remainder or open the other side. Breakeven after a target only works once at least two targets exist. A ladder drawing that keeps the original stop size is a live-trading bug.

## Three mockup walkthroughs

Proposed click-paths. They use mechanics the products above actually have. They are not transcripts of those products, and they do not assign these steps to Angstrom Groups or Sets.

### A. Pullback ladder

Daily regime, lower-timeframe trigger, three buys.

1. Stage "flat". Regime: prior daily close above its 50-day average, and the trader's score at or above their bullish line. The unfinished daily bar is unavailable.
2. Stage "armed", only while the regime holds. Trigger: 4-hour RSI crosses up through 40. Outside that, the ladder does not place.
3. Ladder preview, long: 40% at the trigger, 30% at 3% below the first fill, 30% at 6% below. The spine shows the average after each rung. The stop for the whole plan sits at 8% below, past the last rung.
4. Invalidation is a separate toggle, default off. If the regime fails, cancel unfilled rungs. Do not assume a market flatten unless that toggle is on.

Grounded in TrendSpider's filter-versus-trigger behaviour, its prior-bar higher-timeframe warning, and 3Commas' deviation and "stop beyond the last order" guidance.

### B. One entry, staged exits

Single buy, three sells, one live stop.

1. One entry when the chosen score crosses the bullish line and the prior bar did not. Size is shown as shares or coin units, not only a percent.
2. Exit rungs: sell 33% at 1R, 33% at 2R, trail the rest by 1.5 ATR. Percents are of the original entry and must sum to 100. A further rung is refused until the sum is edited.
3. After the 1R fill, the stop price moves to the average entry and its quantity becomes the remainder. The old full-size stop disappears.
4. If the hard stop and the trail can both be touched in one bar, the nearer stop is the only live line, and the assumption "stop fills before the target" is printed under the chart.

Grounded in TradingView `qty_percent` exits, 3Commas multiple-target breakeven, and the broker-emulator note that stops can fill worse than the level.

### C. Session window, then a regime change

1. A clock condition arms the strategy only inside a window, for example 09:45 to 11:30 America/New_York for a stock, or a named crypto session. Triggers outside the window do nothing and are listed as seen and ignored.
2. The open ladder is a different stage from the arming window. Closing the window does not by itself flatten a fill.
3. A risk-off branch, while a long ladder is open: cancel unfilled adds, keep the filled size, and replace the stop with a tighter one. The opposite direction is a second strategy, not an else on this one.
4. A timeline under the spine: armed, rung filled, add cancelled, partial sold, flat. Each node names the bar time and the fill assumption.

Grounded in TrendSpider candle-time conditions, the FAQ that long and short stay separate, Composer's if/else as a switch rather than a blend, and Kryll's Calendar and Wait blocks.

## What was verified, and what was not

**Verified.** TradingView strategies are written in Pine. The tester, pyramiding, partial exits, next-bar fills, Bar Magnifier, and on-close fills are documented by TradingView. TrendSpider's no-scale-in rule, 100% exits, single timeframe, entry-invalidated exit, and repainting bot stop are in TrendSpider's help center. Composer's blocks, weights, guardrails, daily-close backtests, and trading window are in Composer's knowledge center. 3Commas' safety-order math, average versus base take profit, and the partial-exit warning are in its help center. Kryll's OR connection priority is in Kryll's own blog. NinjaTrader's type check, static stops, and one-way unlock are in its help guide. Option Alpha's yes/no editor, minute Exit Options, and interval blindness are in its docs.

**Not verified, and not assumed.** No hands-on session in any of these products on 5 November 2026. No claim about current prices, plan limits, or which button is where beyond the docs. Third-party "no-code Pine" sites were not used as evidence. Angstrom's Signal Library, Groups, Sets, and reconstruction engine were deliberately not re-specified.

The five patterns, the five mistakes as design advice, and the three walkthroughs are proposals. They should be accepted or thrown out with the trading collaborator. They are not a design of the builder.

## Sources

Read on 5 November 2026.

TradingView

- https://www.tradingview.com/pine-script-docs/concepts/strategies/
- https://www.tradingview.com/pine-script-docs/faq/strategies/
- https://www.tradingview.com/support/solutions/43000628599-strategy-properties/
- https://www.tradingview.com/blog/en/accurate-backtesting-with-bar-magnifier-31746/
- https://www.tradingview.com/support/solutions/43000786181-broker-emulator/
- https://www.tradingview.com/support/solutions/43000763320-how-to-work-with-pine-editor/
- https://www.tradingview.com/support/solutions/43000795135-create-indicators-and-strategies-with-ai-copilot/

TrendSpider

- https://help.trendspider.com/kb/strategy-tester/accessing-and-using-the-strategy-tester
- https://help.trendspider.com/kb/strategy-tester/understanding-strategy-tester-from-trendspider
- https://help.trendspider.com/kb/strategy-tester/strategy-tester-faq-markdown-html
- https://help.trendspider.com/kb/strategy-tester/using-offsets-in-multi-factor-strategy-tester-conditions
- https://help.trendspider.com/kb/indicators/repainting-indicators-and-offsets
- https://help.trendspider.com/kb/scripts/scripts-scripts-everywhere-scan-backtest-create-alerts

Composer

- https://help.composer.trade/article/54-create-tutorial
- https://help.composer.trade/article/18-symphony-editor-assign-weights
- https://help.composer.trade/article/65-how-does-composer-trade
- https://help.composer.trade/article/67-backtest-basics
- https://help.composer.trade/article/63-trading-period
- https://help.composer.trade/article/76-threshold-trading

3Commas, Kryll, NinjaTrader, Option Alpha

- https://help.3commas.io/en/articles/16281102-how-the-dca-bot-works-strategy-setup-guide
- https://help.3commas.io/en/articles/16307077-3commas-dca-bot-for-tradingview-setup-parameter-guide
- https://help.3commas.io/en/articles/9464682-dca-bot-stop-loss-breakeven
- https://kryll.io/editor/
- https://blog.kryll.io/priority-of-blocks-in-the-kryll-strategy-editor/
- https://blog.kryll.io/editor-part-1/
- https://ninjatrader.com/support/helpGuides/nt8/builder_screens.htm
- https://ninjatrader.com/support/helpGuides/nt8/strategybuilder_condition_builder.htm
- https://docs.optionalpha.com/getting-started
- https://docs.optionalpha.com/tools/managing-positions/exit-options
- https://docs.optionalpha.com/technical-documentation/platform/automation-behavior
