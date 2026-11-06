# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.2 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.6 MB, giving 327.7 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 19.7 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.02 | 11.6 |  | 27.2 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.12 | 0.0 |  | 27.2 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.05 | 2.8 |  | 28.5 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.96 | 0.4 |  | 29.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.15 | 3.9 |  | 31.3 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.74 | 1.6 | 8.9 | 27.2 | trend: ok, reversal: ok |  |
