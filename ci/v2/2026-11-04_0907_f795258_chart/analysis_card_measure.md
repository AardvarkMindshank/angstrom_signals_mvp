# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.0 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.4 MB, giving 327.4 MB
- Importing the card and the Groups/Sets code adds: 0.3 MB
- Growth over all 6 evaluations below: 23.8 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.52 | 10.9 |  | 28.6 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.11 | 0.0 |  | 28.6 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.49 | 4.9 |  | 28.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.28 | 0.1 |  | 29.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.62 | 3.6 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.24 | 4.2 | 8.9 | 28.6 | trend: ok, reversal: ok |  |
