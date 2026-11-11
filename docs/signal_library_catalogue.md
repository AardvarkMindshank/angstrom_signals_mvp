# Signal catalogue

Generated from the registry (`signal_library.REGISTRY.catalogue()`) by `signal_catalogue_doc.py`. Regenerate after any definition change.

### Bitcoin spot ETF net flows — `flows.btc_etf@1`

- **Category:** flows · **Output:** observation · **Unit:** USD · **Scope:** market:bitcoin
- **Timeframes:** 1D · **Data:** capital_flows
- **Parameters:** `point_in_time` = False (ignore backfilled history (for research replays))
- **Calculation:** From stored daily observations (TFTC tracker): the latest session's total net flow; sums over the last 5 and 20 sessions; the previous 5-session sum and the change between them (acceleration); and each fund's latest flow. Each day uses its latest revision; first_seen and backfill are kept.
- **Interpretation:** Net creations minus redemptions across US spot Bitcoin ETFs: observed money moving into or out of the funds. Market context for Bitcoin; it is not a forecast.
- **Limitations:** Published after the US session (at least one day late) and the newest day can be revised. US trading days only. Values before Angstrom started collecting are a backfill: when they were really published is not known.

### Stablecoin supply change — `flows.stablecoin_supply@1`

- **Category:** flows · **Output:** observation · **Unit:** USD · **Scope:** market:crypto
- **Timeframes:** 1D · **Data:** capital_flows
- **Parameters:** `point_in_time` = False (ignore backfilled history (for research replays))
- **Calculation:** From stored daily totals (DefiLlama, all stablecoins): latest supply; change over 7 and 30 calendar days in US$ and %; the 7-day change before that and the difference between them (acceleration).
- **Interpretation:** Net issuance of stablecoins: more dollars available on crypto rails. It is not evidence that money entered Bitcoin or any particular coin.
- **Limitations:** A daily total; issuer mints and burns can be lumpy. The newest day can be revised. History loaded on the first run is a backfill.

### Bollinger position (20, 2) — `bollinger.position@1`

- **Category:** momentum · **Output:** observation · **Unit:** 0 = lower band, 1 = upper band · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Where the close sits between the 20-candle Bollinger bands (2 standard deviations). standard_score is the dashboard's Bollinger position (20, 2) component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_bollinger (definitions fingerprint recorded in the evidence).
- **Interpretation:** Near 1: at the upper band. Standard score (dashboard Stretch part): tanh(2 x (position - 0.5)). Descriptive; not a forecast.
- **Limitations:** Bands widen in volatile periods, so the same position means a different move. On timeframes other than 1D the standard score is daily-derived scaling.

### Candle (colour, close vs previous, body size) — `candle.shape@1`

- **Category:** momentum · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `average` = 10 (candles in the average body size)
- **Calculation:** On the last closed candle: colour = green when close > open, red when close < open; close_vs_previous = higher or lower than the previous candle's close; change_pct from the previous close; body = |close - open|; body_vs_average = body / the average body of the last `average` candles (this one included, as TradingView's ta.sma); body_share_of_range = body / (high - low).
- **Interpretation:** What the last candle did: a strong green candle has body_vs_average above 1 (bigger than usual). Descriptive; one candle says little on its own.
- **Limitations:** One candle is noisy, and gaps between sessions (shares) make the previous close less comparable.

### Divergence across timeframes — `divergence.mtf@1`

- **Category:** momentum · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 1D · **Data:** candles
- **Parameters:** `set` = crypto (timeframes: crypto = daily, 12h, 4h, 1h; equity = weekly, daily, 4h, 1h; intraday = 4h, 1h, 30m, 15m); `oscillator` = wavetrend (the momentum line compared with price swings); `active_bars` = 10 (candles a confirmed divergence counts as recent)
- **Calculation:** On each timeframe of the set, at its last closed candle: confirmed divergences between consecutive price swings (5 candles each side) and the oscillator's swings (WaveTrend WT2, or RSI 14), as the library's RSI divergence finds them; one counts when it was confirmed within the last `active_bars` candles and not invalidated. bullish_count = timeframes with a regular or hidden bullish one; bearish_count the same for bearish; regular_bullish_count, hidden_bullish_count, regular_bearish_count and hidden_bearish_count split them; timeframes_read = timeframes that could be read. A timeframe counts once per kind however many it has.
- **Interpretation:** How many timeframes show momentum disagreeing with price at once, the multi-timeframe divergence Drew looks for. Regular divergence hints at exhaustion, hidden divergence at continuation. Descriptive; not a trade signal by itself.
- **Limitations:** Swings are confirmed 5 candles late by design. A timeframe that cannot be read is left out of timeframes_read, never counted as no divergence. In strong trends regular divergence can repeat many times before any turn.

### MACD histogram — `macd.acceleration@1`

- **Category:** momentum · **Output:** observation · **Unit:** price and ATRs · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** MACD histogram (line minus its 9-candle signal), and the same in quarter-ATR units. standard_score is the dashboard's MACD histogram component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_macd_acceleration (definitions fingerprint recorded in the evidence).
- **Interpretation:** Whether momentum is speeding up or slowing. Standard score (dashboard Stretch part): tanh(histogram / (ATR/4)). Descriptive; not a forecast.
- **Limitations:** Turns often in ranges. On timeframes other than 1D the standard score is daily-derived scaling.

### Momentum direction — `momentum.direction@1`

- **Category:** momentum · **Output:** direction · **Unit:** label · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** On the last closed candle: up when the MACD(12,26,9) histogram is above 0 and RSI(14) is above 50; down when the histogram is below 0 and RSI below 50; otherwise mixed. The histogram's change over the last 3 candles is shown as evidence (rising/falling).
- **Interpretation:** Which way short-term momentum points on this timeframe, separate from the moving-average trend.
- **Limitations:** Momentum turns early and often; in ranges it flips back and forth.

### 7-candle move — `move.seven_day@1`

- **Category:** momentum · **Output:** observation · **Unit:** % and expected moves · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Close-to-close change over 7 candles, and the same change in units of the expected move (ATR% x sqrt(7)). standard_score is the dashboard's 7-candle move component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_momentum (definitions fingerprint recorded in the evidence).
- **Interpretation:** How large the recent move is for this asset. Standard score (dashboard Stretch part): tanh(change / expected). Descriptive; not a forecast.
- **Limitations:** On daily candles this is the 7-day move; on other timeframes it is 7 of those candles. On timeframes other than 1D the standard score is daily-derived scaling.

### Stochastic on OHLC4 — `osc.stoch_ohlc4@1`

- **Category:** momentum · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `length` = 14 (candles in the high-low range); `smooth_k` = 3 (smoothing of %K); `smooth_d` = 3 (%D: the average of %K); `overbought` = 80 (overbought line); `oversold` = 20 (oversold line)
- **Calculation:** On the last closed candle, with src = (open + high + low + close) / 4: %K = SMA(100 x (src - lowest low) / (highest high - lowest low), smooth_k) over `length` candles; %D = SMA(%K, smooth_d). zone = overbought at or above the line, oversold at or below; cross = %K crossing %D on this candle; turned_up_from_oversold = a cross up with %D at or below the oversold line (mirror for overbought).
- **Interpretation:** Where the candle's average price sits in its recent range, smoothed, and whether it just turned. Descriptive.
- **Limitations:** Stays pinned near 0 or 100 in strong trends; turns repeat in sideways markets.

### WaveTrend momentum (Market Cipher style) — `osc.wavetrend@1`

- **Category:** momentum · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `channel` = 9 (channel length (the EMA of price and of its distance)); `average` = 12 (average length (smooths the wave, WT1)); `signal` = 3 (signal line length (WT2 = simple average of WT1)); `overbought` = 53 (overbought line (Market Cipher B: 53; a stronger line at 60)); `oversold` = -53 (oversold line (Market Cipher B: -53; a stronger line at -60))
- **Calculation:** LazyBear's WaveTrend on the last closed candle: ap = (high + low + close) / 3; esa = EMA(ap, channel); d = EMA(|ap - esa|, channel); ci = (ap - esa) / (0.015 x d); WT1 = EMA(ci, average); WT2 = SMA(WT1, signal). zone = overbought when WT2 is at or above the overbought line, oversold at or below the oversold line, else neutral. cross = up when WT1 moved above WT2 on this candle, down when below. turned_up_from_oversold = a cross up while WT2 is at or below the oversold line (Market Cipher's green dot); turned_down_from_overbought the mirror (red dot). Defaults are Market Cipher B's.
- **Interpretation:** Where the momentum wave is and whether it just turned. A turn up from oversold is what many traders mark as a possible bounce point, to be read with the trend and other timeframes. Descriptive; not a forecast.
- **Limitations:** Oscillators stay overbought or oversold for long stretches in strong trends, and turns repeat. Needs about 50 closed candles. Settings change the readings; the defaults follow the published Market Cipher B recreation, not any one trader's chart.

### RSI (14) — `rsi.level@1`

- **Category:** momentum · **Output:** observation · **Unit:** 0-100 · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Relative Strength Index over 14 candles. standard_score is the dashboard's RSI (14) component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_rsi (definitions fingerprint recorded in the evidence).
- **Interpretation:** How strongly recent closes have risen versus fallen. Standard score (dashboard Stretch part): (RSI - 50) / 30, clipped to -1..+1 (80 = +1, 20 = -1). Descriptive; not a forecast.
- **Limitations:** Stays stretched for long periods in strong trends. On timeframes other than 1D the standard score is daily-derived scaling.

### Stochastic %K (14, 3) — `stochastic.level@1`

- **Category:** momentum · **Output:** observation · **Unit:** 0-100 · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Stochastic %K: where the close sits within the 14-candle high-low range, smoothed. standard_score is the dashboard's Stochastic %K (14, 3) component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_stochastic (definitions fingerprint recorded in the evidence).
- **Interpretation:** Near 100: closing near recent highs. Standard score (dashboard Stretch part): (%K - 50) / 50. Descriptive; not a forecast.
- **Limitations:** Very sensitive in ranges; reaches extremes easily. On timeframes other than 1D the standard score is daily-derived scaling.

### MACD divergence — `ta.divergence.macd@1`

- **Category:** momentum · **Output:** events · **Unit:** events · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `min_gap` = 5 (fewest bars between the two swings); `max_gap` = 60 (most bars between the two swings); `lookback` = 150 (candles back to report confirmed divergences); `active_bars` = 30 (candles a confirmed divergence stays active before it expires); `line` = histogram (compare price with the MACD histogram or the MACD line)
- **Calculation:** As RSI divergence, with the MACD(12,26,9) histogram (default) or MACD line in place of RSI.
- **Interpretation:** Regular divergence: price makes a new extreme the indicator does not confirm (possible exhaustion). Hidden divergence: price holds a higher low / lower high while the indicator overshoots (possible continuation). Each event lists the price and indicator swing points, when it was confirmed, the confirmation delay and the price that invalidates it. Not a trade signal by itself.
- **Limitations:** Confirmation needs `right` closed candles after the swing, so events arrive late by design. In strong trends regular divergences can repeat many times before any turn. Swing settings change what counts.

### RSI divergence — `ta.divergence.rsi@1`

- **Category:** momentum · **Output:** events · **Unit:** events · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `min_gap` = 5 (fewest bars between the two swings); `max_gap` = 60 (most bars between the two swings); `lookback` = 150 (candles back to report confirmed divergences); `active_bars` = 30 (candles a confirmed divergence stays active before it expires)
- **Calculation:** Confirmed swing lows/highs (pivot rule, left/right bars). For consecutive swings of the same kind, min_gap..max_gap bars apart, take RSI(14)'s lowest/highest value within 2 bars of each swing (never past the confirmation bar). Regular bullish: lower price low, higher RSI low. Hidden bullish: higher price low, lower RSI low. Regular bearish: higher price high, lower RSI high. Hidden bearish: lower price high, higher RSI high. Confirmed when the second swing is confirmed; invalidated by a close beyond the second swing's price within the next active_bars candles, otherwise expired after active_bars candles (active until then).
- **Interpretation:** Regular divergence: price makes a new extreme the indicator does not confirm (possible exhaustion). Hidden divergence: price holds a higher low / lower high while the indicator overshoots (possible continuation). Each event lists the price and indicator swing points, when it was confirmed, the confirmation delay and the price that invalidates it. Not a trade signal by itself.
- **Limitations:** Confirmation needs `right` closed candles after the swing, so events arrive late by design. In strong trends regular divergences can repeat many times before any turn. Swing settings change what counts.

### Options max pain — `options.max_pain@1`

- **Category:** positioning · **Output:** observation · **Unit:** % from max pain · **Scope:** asset
- **Timeframes:** 1D, 4h · **Data:** options
- **Parameters:** `min_days` = 0 (skip expiries closer than this many days (0 = the nearest expiry)); `monthly` = False (monthly expiries only (equities: third Friday; crypto: last Friday)); `near_pct` = 2.0 (within this % of max pain counts as at max pain)
- **Calculation:** From the newest stored options snapshot at or before the evaluation time: the first expiry still ahead that is at least min_days away (monthly expiries only if monthly is on). max_pain = the strike at which that expiry's open calls and puts would be worth the least. distance_pct = (price - max_pain) / max_pain x 100, with price the underlying price recorded with the snapshot. side = at when |distance_pct| <= near_pct, else above or below. days_to_expiry = time to settlement (Deribit 08:00 UTC; US options 16:00 New York) in days. expiry_week = 7 days or fewer. put_call_ratio = put / call open interest. Stale after 12 hours (crypto) or 96 hours (equities).
- **Interpretation:** How far price is from the strike where options would expire cheapest, and how soon. Some traders expect price to drift towards max pain into expiry; treat it as context.
- **Limitations:** Max pain is a description of where open options would expire cheapest, not a price target; the evidence that price is drawn to it is thin and mixed. Crypto covers Bitcoin and Ethereum only (Deribit). Equities need a listed options chain. History starts when the snapshots began (November 2026) and is replayable only from when each snapshot first reached the database.

### Funding rate (daily) — `positioning.funding@1`

- **Category:** positioning · **Output:** observation · **Unit:** % per funding interval · **Scope:** crypto_asset
- **Timeframes:** 1D · **Data:** derivatives
- **Parameters:** `days` = 7 (days averaged or compared); `lookback` = 365 (days of history the reading is ranked against)
- **Calculation:** From the stored daily funding rate of the coin's main perpetual market (the close of each finished UTC day): the latest day, the average over the last `days` days, and where that average ranks among every `days`-day average in the last `lookback` days (0 to 100). Crowded longs when it ranks 90 or more and is positive; crowded shorts when it ranks 10 or less and is negative; otherwise neutral.
- **Interpretation:** Funding is what traders betting on a rise pay those betting on a fall (or the other way round when negative) to keep their futures open. Unusually high funding means many are betting the same way; crowded markets can unwind sharply. It is a reading of positioning, not a forecast.
- **Limitations:** One market (the coin's largest stablecoin perpetual on Binance, Bybit or OKX), not every venue. Rates are per funding interval, usually 8 hours, as the exchange reports them. History before Angstrom collected it was filled in from Coinalyze's daily record.

### Nearest estimated liquidation levels — `positioning.liquidation_levels@1`

- **Category:** positioning · **Output:** levels · **Unit:** price · **Scope:** crypto_asset
- **Timeframes:** 1h · **Data:** derivatives
- **Calculation:** From the stored liquidation-level estimate (open interest added over the last 7 days, spread over a typical leverage mix): the nearest and the largest estimated long-liquidation level below price and short-liquidation level above, with their distance from price in % and their estimated US$.
- **Interpretation:** Where leveraged positions would be forced closed if price got there, by estimate.
- **Limitations:** An estimate from public open interest, not exchange order data: actual leverage and stops are unknown. Not a liquidation heatmap.

### Liquidations (24h) — `positioning.liquidations@1`

- **Category:** positioning · **Output:** observation · **Unit:** USD · **Scope:** crypto_asset
- **Timeframes:** 1h · **Data:** derivatives
- **Parameters:** `hours` = 24 (window in hours)
- **Calculation:** Sum of reported long and short liquidations (US$) over the window across the coin's markets, the longs' share of the total, and the largest single hour.
- **Interpretation:** Which side has been forced out recently, and how much. Reported data.
- **Limitations:** Exchanges under-report liquidations; totals are a floor, not the full amount.

### Long/short account ratio (daily) — `positioning.long_short@1`

- **Category:** positioning · **Output:** observation · **Unit:** longs per short · **Scope:** crypto_asset
- **Timeframes:** 1D · **Data:** derivatives
- **Parameters:** `days` = 7 (days averaged or compared); `lookback` = 365 (days of history the reading is ranked against)
- **Calculation:** From the stored daily long/short account ratio (accounts betting on a rise per account betting on a fall, the close of each finished UTC day): the latest day, its change over `days` days, and where the latest ranks among the last `lookback` days (0 to 100). More longs than usual when it ranks 90 or more; more shorts than usual when 10 or less; otherwise usual.
- **Interpretation:** Counts accounts, not money: many small accounts betting one way can sit against a few large ones. Traders often read an unusually long-heavy crowd as a sign of fragile positioning.
- **Limitations:** One exchange's accounts (the market Coinalyze reports a ratio for). History before Angstrom collected it was filled in from Coinalyze's daily record.

### Open interest and price (24h) — `positioning.oi_price@1`

- **Category:** positioning · **Output:** observation · **Unit:** % and labels · **Scope:** crypto_asset
- **Timeframes:** 1h · **Data:** derivatives
- **Parameters:** `hours` = 24 (window in hours)
- **Calculation:** From the stored hourly series: open interest (US$, summed across the coin's main perpetual markets) and price now versus `hours` ago, as % changes; the inferred positioning reading from their combination; latest and average funding over the window; long/short account ratio now and its change.
- **Interpretation:** Rising open interest with rising price suggests new longs (build-up); with falling price, new shorts. Falling open interest with rising price suggests shorts closing; with falling price, longs closing (unwinding). These readings are inferences from two reported numbers, not observed trades.
- **Limitations:** Covers the markets Coinalyze reports for the coin, not every venue. Open interest in US$ also moves with price itself. Funding is shown as reported per funding interval.

### Regime evidence — `regime.observation@1`

- **Category:** regime · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `confirm` = 3 (candles a new regime must hold (existing regime rule)); `window` = 250 (candles used to rank volatility and band width)
- **Calculation:** Builds on the existing regime rules without changing them: confirmed state and direction from regime.regime_series. Adds: ADX(14) value and its 5-candle change; Kaufman efficiency ratio over 20 candles (0 = choppy, 1 = straight line); ATR(14) as % of price and its percentile over `window` candles; Bollinger band width (upper-lower over middle) and its percentile (low = compressed, high = expanded); and whether the raw state already differs from the confirmed state (in transition).
- **Interpretation:** Why the regime is what it is, and whether volatility is compressed or expanding. Percentiles are reported as numbers; the words (compressed below the 20th, expanded above the 80th) are guides.
- **Limitations:** All inputs come from price; volatility percentiles depend on the window and on how much history loaded.

### Market regime — `regime.state@1`

- **Category:** regime · **Output:** category · **Unit:** label · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `confirm` = 3 (closed candles a new state must hold before it is accepted)
- **Calculation:** ADX(14) >= 25 trending, < 20 ranging, otherwise transitional; a new state is accepted after it holds for `confirm` closed candles in a row. Same rules as the existing regime feature.
- **Interpretation:** Whether the asset is trending or ranging on this timeframe, with the evidence behind it.
- **Limitations:** ADX thresholds are conventions; ADX says how strong a move is, not which way.

### Volatility vs its average (ATR) — `volatility.atr_trend@1`

- **Category:** regime · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `length` = 14 (candles in the ATR (Wilder's average of the true range)); `average` = 20 (candles in the average ATR it is compared with)
- **Calculation:** On the last closed candle: atr = ATR(`length`) as TradingView's ta.atr (Wilder's average of the true range); atr_pct = ATR as % of the close; ratio = ATR / its simple average over `average` candles; expanding = yes when the ratio is above 1 (ATR above its average).
- **Interpretation:** Whether the asset is moving more than it has lately (expanding) or less. Descriptive.
- **Limitations:** A single large candle lifts ATR for a while; ratios near 1 flip back and forth.

### Asset headline sentiment — `sentiment.asset@1`

- **Category:** sentiment · **Output:** observation · **Unit:** -100..+100 · **Scope:** asset
- **Timeframes:** 1D · **Data:** sentiment
- **Calculation:** The latest stored headline-sentiment score for this asset, on -100..+100 (stored 0..100), with its time, coverage (thin or ok), model, the change from the newest score at least 7 days before the evaluation time, and the last 10 scores. Stale after 36 hours.
- **Interpretation:** Whether recent headlines about this asset read positive or negative. Descriptive.
- **Limitations:** AI-scored headlines, not validated as predictive. Days with thin news can swing the score. History starts on 3 Nov 2026 and is replayable only from when each score first reached the database.

### Market headline sentiment — `sentiment.market@1`

- **Category:** sentiment · **Output:** observation · **Unit:** -100..+100 · **Scope:** market:crypto|stocks
- **Timeframes:** 1D · **Data:** sentiment
- **Calculation:** The latest stored headline-sentiment score for the whole crypto market (subject market:crypto) or stock market (market:stocks), on -100..+100 (stored 0..100; shown = 2 x stored - 100), with its time, coverage (thin or ok), model, the change from the newest score at least 7 days before the evaluation time, and the last 10 scores. Stale after 36 hours.
- **Interpretation:** Whether recent market headlines read positive or negative. Descriptive.
- **Limitations:** AI-scored headlines, not validated as predictive. Days with thin news can swing the score. History starts on 3 Nov 2026 and is replayable only from when each score first reached the database.

### Support and resistance zones — `levels.zones@1`

- **Category:** structure · **Output:** levels · **Unit:** price · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `lookback` = 300 (candles back to collect swing points); `width_atr` = 0.5 (swings within this many ATRs of each other form one zone); `min_touches` = 2 (fewest swing points for a zone); `per_side` = 3 (most zones kept above and below price); `max_width_mult` = 2.0 (a zone spans at most this many grouping widths (convention, not tuned))
- **Calculation:** Confirmed swing points from the lookback are sorted by price and grouped while neighbours are within width_atr x ATR(14), and no group grows wider than max_width_mult times that (default 2, a convention). Each group with at least min_touches swings is a zone spanning their prices. The strongest per_side zones above (resistance) and below (support) the last close are kept: most touches first, then most recent. Each zone gives its distance from price in price, % and ATRs, the latest close through it and any retest after that. Swings in groups below min_touches and zones beyond per_side are kept in the evidence (ungrouped_swings, other_zones), not discarded.
- **Interpretation:** Price areas where swings have repeatedly turned. Values are real prices, not scores.
- **Limitations:** Zones from few touches are weak; they are dropped below min_touches. No volume information (volume profile is on the roadmap). A zone far from price may be irrelevant for the current trade.

### Structure breaks (BOS / CHoCH) — `structure.breaks@1`

- **Category:** structure · **Output:** events · **Unit:** events · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `lookback` = 150 (candles back to report breaks)
- **Calculation:** Walking forward candle by candle with only the swings confirmed before that candle: a close above the latest swing high is a bullish break, a close below the latest swing low a bearish break. It is a break of structure (BOS) when it continues the existing structure, and a potential change of character (CHoCH) when it goes against it. Each swing level counts once.
- **Interpretation:** Where price closed through recent structure, and whether that continued or challenged it.
- **Limitations:** A CHoCH is only a potential change; many fail. Wicks through a level without a close do not count.

### Market structure — `structure.swings@1`

- **Category:** structure · **Output:** observation · **Unit:** price · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `count` = 6 (recent confirmed swings to list)
- **Calculation:** Confirmed swing highs and lows (pivot rule). Each is labelled against the previous swing of the same kind: HH/LH for highs, HL/LL for lows (EH/EL when equal). Structure is up when the latest high is HH and the latest low HL, down for LH and LL, otherwise mixed. The current unconfirmed extremes are listed separately as tentative swings.
- **Interpretation:** The sequence of confirmed swing points and what they say about structure on this timeframe.
- **Limitations:** Swings are confirmed `right` candles late. Small swing settings give noisy structure on low timeframes.

### Ichimoku cloud position — `ichimoku.position@1`

- **Category:** trend · **Output:** observation · **Unit:** label and ATRs · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Close above, inside or below the Ichimoku cloud; the distance outside it and the Tenkan-Kijun gap, in ATR(14). standard_score is the dashboard's Ichimoku cloud position component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_ichimoku (definitions fingerprint recorded in the evidence).
- **Interpretation:** Where price sits relative to the cloud. The standard score (dashboard Trend part) is 0 inside the cloud and grows with distance outside it, averaged with the Tenkan-Kijun gap (both scaled by 3 ATRs). Descriptive; not a forecast.
- **Limitations:** The cloud is plotted 26 candles ahead from past prices; it needs about 78 candles of history. On timeframes other than 1D the standard score is daily-derived scaling.

### Moving average (EMA or SMA, any length) — `ma.line@1`

- **Category:** trend · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `kind` = EMA (exponential (EMA) or simple (SMA) average); `length` = 20 (candles averaged)
- **Calculation:** On the last closed candle, with the average of closes over `length` candles (EMA as TradingView's ta.ema, SMA as ta.sma): position = above or below the close; distance in % and in ATR(14); retest_from_above = the low reached the average and the close finished above it; retest_from_below = the high reached it and the close finished below; crossed_up = the previous close was below the average and this close is above it; crossed_down the reverse; slope = the average higher or lower than one candle before.
- **Interpretation:** Where price sits against one moving average, and whether this candle pulled back to it and held (a retest) or crossed it. Descriptive; not a forecast.
- **Limitations:** Averages lag. A retest on one candle is common in choppy markets; pair it with a trend reading. An EMA needs about three lengths of history to settle, so new listings say not enough data.

### Two moving averages (fast vs slow) — `ma.pair@1`

- **Category:** trend · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `kind` = EMA (exponential (EMA) or simple (SMA) averages); `fast` = 20 (candles in the fast average); `slow` = 50 (candles in the slow average)
- **Calculation:** On the last closed candle: order = fast_above when the fast average is above the slow one, fast_below when under; gap_pct = (fast - slow) / slow x 100; crossed = up when the fast average moved above the slow one on this candle, down when it moved below, none otherwise.
- **Interpretation:** The trend as two averages see it, such as EMA 20 over EMA 50 for an uptrend. Descriptive.
- **Limitations:** Both averages lag; crosses come late and repeat in sideways markets.

### Moving averages (50, 200) — `ma.position@1`

- **Category:** trend · **Output:** observation · **Unit:** % and ATRs · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Close against the 50- and 200-candle simple moving averages: the gap in % and in ATR(14) units. standard_score is the dashboard's Moving averages (50, 200) component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_moving_averages (definitions fingerprint recorded in the evidence).
- **Interpretation:** How far price sits above or below its longer averages. The standard score (dashboard Trend part) averages tanh(distance / (ATR x 0.5 x sqrt(length))) over the two averages. Descriptive; not a forecast.
- **Limitations:** Averages lag. Without 200 candles of history only the 50 is used. On timeframes other than 1D the standard score is daily-derived scaling.

### MACD line — `macd.level@1`

- **Category:** trend · **Output:** observation · **Unit:** price and ATRs · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** MACD(12, 26) line: the 12-candle EMA minus the 26-candle EMA, and the same in ATR(14) units. standard_score is the dashboard's MACD line component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_macd (definitions fingerprint recorded in the evidence).
- **Interpretation:** Whether the shorter average is above the longer one, and by how much. Standard score (dashboard Trend part): tanh(line / ATR). Descriptive; not a forecast.
- **Limitations:** EMAs depend slightly on how much history was loaded. On timeframes other than 1D the standard score is daily-derived scaling.

### Multi-timeframe alignment — `mtf.alignment@1`

- **Category:** trend · **Output:** observation · **Unit:** per-timeframe labels · **Scope:** asset
- **Timeframes:** 1D · **Data:** candles, signals
- **Parameters:** `set` = all (which timeframes to compare)
- **Calculation:** Evaluates trend.direction@1 and momentum.direction@1 on each timeframe of the chosen set and lists them side by side, with counts of up/down/mixed, the timeframes whose trend disagrees with the next larger one, and the timeframes where momentum opposes trend (possible transition).
- **Interpretation:** Shows where timeframes agree and where they conflict. There is deliberately no single alignment score: agreement is descriptive, not evidence of a future move.
- **Limitations:** Intraday candles come from Yahoo (15m: about 60 days, 1h/4h: about 2 years). A timeframe that cannot be loaded is listed as missing, not dropped silently. Trend and momentum share price inputs, so they are not independent confirmations.

### Trend direction — `trend.direction@1`

- **Category:** trend · **Output:** direction · **Unit:** label · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** On the last closed candle: up when close > SMA 50 > SMA 200, down when close < SMA 50 < SMA 200, otherwise mixed. Without SMA 200 yet, close against SMA 50 decides. Same rule as the market regime.
- **Interpretation:** Which way the moving-average stack points on this timeframe. Descriptive.
- **Limitations:** Moving averages lag; after a sharp reversal this stays on the old direction for a while.

### Money flow (Market Cipher style) — `flow.money@1`

- **Category:** volume · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `period` = 60 (candles averaged); `multiplier` = 150 (scale (Market Cipher B: 150))
- **Calculation:** On the last closed candle: value = the simple average over `period` candles of ((close - open) / (high - low)) x multiplier, less 2.5 (VuManChu Cipher B's money-flow area). direction = in when the value is above zero, out when below. rising = higher than one candle before.
- **Interpretation:** Whether candles have, on balance, been closing above their opens (money flowing in, green) or below (flowing out, red), and whether that is growing. Agreement or disagreement across timeframes is how it is usually read. Descriptive.
- **Limitations:** Built from candle shapes only; it does not see order flow or exchange volumes. A doji (open = close) counts as nothing. Slow by design (60 candles).

### On-balance volume balance — `obv.balance@1`

- **Category:** volume · **Output:** observation · **Unit:** scaled volumes · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** On-balance volume minus its 20-candle average, in average-candle volumes x sqrt(20). standard_score is the dashboard's On-balance volume balance component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_obv (definitions fingerprint recorded in the evidence).
- **Interpretation:** Whether volume has recently come on up-candles or down-candles. Standard score (dashboard Flow part): tanh(balance). Descriptive; not a forecast.
- **Limitations:** Needs a source with real volume; crypto volume differs by venue. On timeframes other than 1D the standard score is daily-derived scaling.

### Chaikin Money Flow — `volume.cmf@1`

- **Category:** volume · **Output:** numeric · **Unit:** ratio (-1..+1) · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Parameters:** `length` = 20 (candles summed)
- **Calculation:** CMF(length) = sum of ((close-low)-(high-close))/(high-low) x volume over `length` closed candles, divided by the sum of volume. Above 0: closes tend to sit near the highs on volume.
- **Interpretation:** Where candles close within their range, weighted by volume. Unlike OBV (whole-candle direction) it uses the close's position in the range, so it can differ from price direction. The coverage audit found it more distinct from the existing readings than OBV; predictive value is unproven.
- **Limitations:** Gaps between candles are ignored. Crypto volume differs by venue; zero-volume candles are skipped.

### Heavy-volume candle — `volume.heavy_candle@1`

- **Category:** volume · **Output:** observation · **Unit:** ratio and share · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** The last candle's volume against its 20-candle average, its body as a share of its range, and how heavy it counts (1x average = 0, 2x or more = 1). standard_score is the dashboard's Heavy-volume candle component for this candle, on -1..+1 (positive = up or stretched up), computed by signals_v2.component_heavy_volume (definitions fingerprint recorded in the evidence).
- **Interpretation:** A big candle on big volume. Standard score (dashboard Flow part): heaviness x body share, clipped to -1..+1. Descriptive; not a forecast.
- **Limitations:** One candle only; needs real volume. On timeframes other than 1D the standard score is daily-derived scaling.

### Relative volume — `volume.relative@1`

- **Category:** volume · **Output:** numeric · **Unit:** x average · **Scope:** asset
- **Timeframes:** 15m, 30m, 1h, 4h, 12h, 1D, 1W · **Data:** candles
- **Calculation:** Volume of the last closed candle divided by the 20-candle average volume (the existing volume_ratio).
- **Interpretation:** How busy the last candle was compared with usual. 2.0 = twice the normal volume.
- **Limitations:** Intraday share volume has a daily rhythm (busy open and close), so 15m/1h values are high at the open on most days. Crypto volume varies by data venue.
