# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +87.8 MB, giving 328.1 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 24.6 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.11 | 11.5 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.17 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.2 | 2.0 |  | 29.1 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.07 | 3.5 |  | 28.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.26 | 2.9 |  | 32.2 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.49 | 4.6 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
