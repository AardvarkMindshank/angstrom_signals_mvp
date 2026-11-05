# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.5 MB, giving 327.9 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 19.3 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.52 | 11.6 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.12 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.54 | 1.8 |  | 29.6 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.38 | 2.2 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.78 | 3.0 |  | 31.1 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.39 | 1.6 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
