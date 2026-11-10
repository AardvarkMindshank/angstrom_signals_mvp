# Drew's chart setup (shared 10 Nov 2026) — notes for the confluence brief

Screenshots: docs/research/drew_charts/ (BTCUSDT perpetual, Binance, TradingView: 1D long setup, 12h, 1h, 4h, 1D short setup).

## What is on his charts
- **Price pane:** an EMA ribbon (white/blue fan, grey when falling), red and green longer averages, volume profile on the left, supply (red) and demand (blue) zones, structure labels (BOS, CHoCH, weak/strong high and low), buy/sell markers.
- **Momentum oscillator** (WaveTrend-style, Market Cipher B look): blue waves with overbought/oversold bands near ±53/±60, green/red dots where the waves cross, yellow triangles when a wave turns from an extreme.
- **Money flow overlay:** green above zero = money flowing in, red below = flowing out; a red/green strip under it.
- **Stochastic** pane underneath (0–100, 20/80 bands), his version computed on OHLC4 ((open+high+low+close)/4) rather than the close. Together with the momentum and money-flow oscillator it gives him the directional trend; he then reads traditional candle structure to interpret what is happening.
- Grey vertical lines = his past trades. Yellow arrows (his marks) = oversold momentum turning.

## How he reads them (his words, condensed)
- Oversold momentum turning on the daily is a starting point, never acted on alone: it needs confluence across the timeframes (1D, 12h, 4h, 1h).
- Long setups: oversold waves plus **regular or hidden bullish divergence**, ideally on several timeframes at once, read from both candle structure (price swings) and momentum structure (oscillator swings).
- Short setups: the mirror, with bearish divergence and multi-timeframe confluence.
- Money flow: direction of money in or out; he looks for agreement or bifurcation (disagreement) between timeframes.

## What Angstrom already has / would need
- Have: ta.divergence.rsi and ta.divergence.macd (regular divergence on swings), structure.swings, structure.breaks (BOS/CHoCH), levels.zones, mtf.alignment, volume.cmf (a money-flow measure), ma.line / ma.pair (EMA ribbon pieces).
- Would need: hidden divergence is already computed in swings.py (HIDDEN_BULL/HIDDEN_BEAR): check it is exposed as a field; a WaveTrend oscillator with overbought/oversold and "turning from an extreme"; an OHLC4 stochastic; a money-flow reading in the style he uses; a multi-timeframe divergence count ("bullish divergence on 3 of 4 timeframes").
- Note for the brief: the last daily screenshot was described as "looking for shorts… oversold momentum"; for shorts the usual reading is overbought, so confirm which he means.
