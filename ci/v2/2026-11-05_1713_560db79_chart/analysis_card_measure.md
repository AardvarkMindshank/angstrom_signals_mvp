# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.9 MB, giving 328.3 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 20.4 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.5 | 11.6 |  | 28.7 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.12 | 0.0 |  | 28.7 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.43 | 2.8 |  | 28.7 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.1 | 2.6 |  | 28.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.7 | 2.8 |  | 32.5 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.01 | 1.6 | 8.9 | 28.7 | trend: ok, reversal: ok |  |
