# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +84.6 MB, giving 322.7 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 22.1 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.92 | 11.7 |  | 27.2 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | 0.0 |  | 27.2 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.92 | 3.2 |  | 27.4 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.87 | 2.1 |  | 29.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.04 | 2.7 |  | 31.6 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.14 | 2.4 | 8.9 | 27.2 | trend: ok, reversal: ok |  |
