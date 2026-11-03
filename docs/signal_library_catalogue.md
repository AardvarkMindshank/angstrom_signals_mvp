# Signal catalogue

Generated from the registry (`signal_library.REGISTRY.catalogue()`). Regenerate after any definition change.

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

### Momentum direction — `momentum.direction@1`

- **Category:** momentum · **Output:** direction · **Unit:** label · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Calculation:** On the last closed candle: up when the MACD(12,26,9) histogram is above 0 and RSI(14) is above 50; down when the histogram is below 0 and RSI below 50; otherwise mixed. The histogram's change over the last 3 candles is shown as evidence (rising/falling).
- **Interpretation:** Which way short-term momentum points on this timeframe, separate from the moving-average trend.
- **Limitations:** Momentum turns early and often; in ranges it flips back and forth.

### MACD divergence — `ta.divergence.macd@1`

- **Category:** momentum · **Output:** events · **Unit:** events · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `min_gap` = 5 (fewest bars between the two swings); `max_gap` = 60 (most bars between the two swings); `lookback` = 150 (candles back to report confirmed divergences); `active_bars` = 30 (candles a confirmed divergence stays active before it expires); `line` = histogram (compare price with the MACD histogram or the MACD line)
- **Calculation:** As RSI divergence, with the MACD(12,26,9) histogram (default) or MACD line in place of RSI.
- **Interpretation:** Regular divergence: price makes a new extreme the indicator does not confirm (possible exhaustion). Hidden divergence: price holds a higher low / lower high while the indicator overshoots (possible continuation). Each event lists the price and indicator swing points, when it was confirmed, the confirmation delay and the price that invalidates it. Not a trade signal by itself.
- **Limitations:** Confirmation needs `right` closed candles after the swing, so events arrive late by design. In strong trends regular divergences can repeat many times before any turn. Swing settings change what counts.

### RSI divergence — `ta.divergence.rsi@1`

- **Category:** momentum · **Output:** events · **Unit:** events · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `min_gap` = 5 (fewest bars between the two swings); `max_gap` = 60 (most bars between the two swings); `lookback` = 150 (candles back to report confirmed divergences); `active_bars` = 30 (candles a confirmed divergence stays active before it expires)
- **Calculation:** Confirmed swing lows/highs (pivot rule, left/right bars). For consecutive swings of the same kind, min_gap..max_gap bars apart, take RSI(14)'s lowest/highest value within 2 bars of each swing (never past the confirmation bar). Regular bullish: lower price low, higher RSI low. Hidden bullish: higher price low, lower RSI low. Regular bearish: higher price high, lower RSI high. Hidden bearish: lower price high, higher RSI high. Confirmed when the second swing is confirmed; invalidated by a close beyond the second swing's price within the next active_bars candles, otherwise expired after active_bars candles (active until then).
- **Interpretation:** Regular divergence: price makes a new extreme the indicator does not confirm (possible exhaustion). Hidden divergence: price holds a higher low / lower high while the indicator overshoots (possible continuation). Each event lists the price and indicator swing points, when it was confirmed, the confirmation delay and the price that invalidates it. Not a trade signal by itself.
- **Limitations:** Confirmation needs `right` closed candles after the swing, so events arrive late by design. In strong trends regular divergences can repeat many times before any turn. Swing settings change what counts.

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

### Open interest and price (24h) — `positioning.oi_price@1`

- **Category:** positioning · **Output:** observation · **Unit:** % and labels · **Scope:** crypto_asset
- **Timeframes:** 1h · **Data:** derivatives
- **Parameters:** `hours` = 24 (window in hours)
- **Calculation:** From the stored hourly series: open interest (US$, summed across the coin's main perpetual markets) and price now versus `hours` ago, as % changes; the inferred positioning reading from their combination; latest and average funding over the window; long/short account ratio now and its change.
- **Interpretation:** Rising open interest with rising price suggests new longs (build-up); with falling price, new shorts. Falling open interest with rising price suggests shorts closing; with falling price, longs closing (unwinding). These readings are inferences from two reported numbers, not observed trades.
- **Limitations:** Covers the markets Coinalyze reports for the coin, not every venue. Open interest in US$ also moves with price itself. Funding is shown as reported per funding interval.

### Regime evidence — `regime.observation@1`

- **Category:** regime · **Output:** observation · **Unit:** mixed (labelled fields) · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `confirm` = 3 (candles a new regime must hold (existing regime rule)); `window` = 250 (candles used to rank volatility and band width)
- **Calculation:** Builds on the existing regime rules without changing them: confirmed state and direction from regime.regime_series. Adds: ADX(14) value and its 5-candle change; Kaufman efficiency ratio over 20 candles (0 = choppy, 1 = straight line); ATR(14) as % of price and its percentile over `window` candles; Bollinger band width (upper-lower over middle) and its percentile (low = compressed, high = expanded); and whether the raw state already differs from the confirmed state (in transition).
- **Interpretation:** Why the regime is what it is, and whether volatility is compressed or expanding. Percentiles are reported as numbers; the words (compressed below the 20th, expanded above the 80th) are guides.
- **Limitations:** All inputs come from price; volatility percentiles depend on the window and on how much history loaded.

### Market regime — `regime.state@1`

- **Category:** regime · **Output:** category · **Unit:** label · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `confirm` = 3 (closed candles a new state must hold before it is accepted)
- **Calculation:** ADX(14) >= 25 trending, < 20 ranging, otherwise transitional; a new state is accepted after it holds for `confirm` closed candles in a row. Same rules as the existing regime feature.
- **Interpretation:** Whether the asset is trending or ranging on this timeframe, with the evidence behind it.
- **Limitations:** ADX thresholds are conventions; ADX says how strong a move is, not which way.

### Support and resistance zones — `levels.zones@1`

- **Category:** structure · **Output:** levels · **Unit:** price · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `lookback` = 300 (candles back to collect swing points); `width_atr` = 0.5 (swings within this many ATRs of each other form one zone); `min_touches` = 2 (fewest swing points for a zone); `per_side` = 3 (most zones kept above and below price)
- **Calculation:** Confirmed swing points from the lookback are sorted by price and grouped while neighbours are within width_atr x ATR(14), and no group grows wider than twice that. Each group with at least min_touches swings is a zone spanning their prices. The strongest per_side zones above (resistance) and below (support) the last close are kept: most touches first, then most recent. Each zone gives its distance from price in price, % and ATRs, the latest close through it and any retest after that.
- **Interpretation:** Price areas where swings have repeatedly turned. Values are real prices, not scores.
- **Limitations:** Zones from few touches are weak; they are dropped below min_touches. No volume information (volume profile is on the roadmap). A zone far from price may be irrelevant for the current trade.

### Structure breaks (BOS / CHoCH) — `structure.breaks@1`

- **Category:** structure · **Output:** events · **Unit:** events · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `lookback` = 150 (candles back to report breaks)
- **Calculation:** Walking forward candle by candle with only the swings confirmed before that candle: a close above the latest swing high is a bullish break, a close below the latest swing low a bearish break. It is a break of structure (BOS) when it continues the existing structure, and a potential change of character (CHoCH) when it goes against it. Each swing level counts once.
- **Interpretation:** Where price closed through recent structure, and whether that continued or challenged it.
- **Limitations:** A CHoCH is only a potential change; many fail. Wicks through a level without a close do not count.

### Market structure — `structure.swings@1`

- **Category:** structure · **Output:** observation · **Unit:** price · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `left` = 5 (bars before a swing point that must be lower (highs) / higher (lows)); `right` = 5 (bars after it needed to confirm it; this is the confirmation delay); `count` = 6 (recent confirmed swings to list)
- **Calculation:** Confirmed swing highs and lows (pivot rule). Each is labelled against the previous swing of the same kind: HH/LH for highs, HL/LL for lows (EH/EL when equal). Structure is up when the latest high is HH and the latest low HL, down for LH and LL, otherwise mixed. The current unconfirmed extremes are listed separately as tentative swings.
- **Interpretation:** The sequence of confirmed swing points and what they say about structure on this timeframe.
- **Limitations:** Swings are confirmed `right` candles late. Small swing settings give noisy structure on low timeframes.

### Multi-timeframe alignment — `mtf.alignment@1`

- **Category:** trend · **Output:** observation · **Unit:** per-timeframe labels · **Scope:** asset
- **Timeframes:** 1D · **Data:** candles, signals
- **Parameters:** `set` = all (which timeframes to compare)
- **Calculation:** Evaluates trend.direction@1 and momentum.direction@1 on each timeframe of the chosen set and lists them side by side, with counts of up/down/mixed, the timeframes whose trend disagrees with the next larger one, and the timeframes where momentum opposes trend (possible transition).
- **Interpretation:** Shows where timeframes agree and where they conflict. There is deliberately no single alignment score: agreement is descriptive, not evidence of a future move.
- **Limitations:** Intraday candles come from Yahoo (15m: about 60 days, 1h/4h: about 2 years). A timeframe that cannot be loaded is listed as missing, not dropped silently. Trend and momentum share price inputs, so they are not independent confirmations.

### Trend direction — `trend.direction@1`

- **Category:** trend · **Output:** direction · **Unit:** label · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Calculation:** On the last closed candle: up when close > SMA 50 > SMA 200, down when close < SMA 50 < SMA 200, otherwise mixed. Without SMA 200 yet, close against SMA 50 decides. Same rule as the market regime.
- **Interpretation:** Which way the moving-average stack points on this timeframe. Descriptive.
- **Limitations:** Moving averages lag; after a sharp reversal this stays on the old direction for a while.

### Chaikin Money Flow — `volume.cmf@1`

- **Category:** volume · **Output:** numeric · **Unit:** ratio (-1..+1) · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Parameters:** `length` = 20 (candles summed)
- **Calculation:** CMF(length) = sum of ((close-low)-(high-close))/(high-low) x volume over `length` closed candles, divided by the sum of volume. Above 0: closes tend to sit near the highs on volume.
- **Interpretation:** Where candles close within their range, weighted by volume. Unlike OBV (whole-candle direction) it uses the close's position in the range, so it can differ from price direction. The coverage audit found it more distinct from the existing readings than OBV; predictive value is unproven.
- **Limitations:** Gaps between candles are ignored. Crypto volume differs by venue; zero-volume candles are skipped.

### Relative volume — `volume.relative@1`

- **Category:** volume · **Output:** numeric · **Unit:** x average · **Scope:** asset
- **Timeframes:** 15m, 1h, 4h, 1D, 1W · **Data:** candles
- **Calculation:** Volume of the last closed candle divided by the 20-candle average volume (the existing volume_ratio).
- **Interpretation:** How busy the last candle was compared with usual. 2.0 = twice the normal volume.
- **Limitations:** Intraday share volume has a daily rhythm (busy open and close), so 15m/1h values are high at the open on most days. Crypto volume varies by data venue.

