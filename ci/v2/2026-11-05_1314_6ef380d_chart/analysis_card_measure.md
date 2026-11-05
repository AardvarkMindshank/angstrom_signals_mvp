# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +84.8 MB, giving 323.1 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 22.0 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.08 | 11.7 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.09 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.12 | 2.8 |  | 29.1 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.02 | 1.1 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.23 | 4.5 |  | 31.8 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.38 | 1.8 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
