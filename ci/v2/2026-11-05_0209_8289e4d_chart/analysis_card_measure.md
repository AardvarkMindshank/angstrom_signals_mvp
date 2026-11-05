# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.2 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +84.6 MB, giving 322.8 MB
- Importing the card and the Groups/Sets code adds: 0.5 MB
- Growth over all 6 evaluations below: 24.5 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.34 | 11.2 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.09 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.1 | 2.6 |  | 29.2 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.11 | 1.1 |  | 28.4 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.48 | 4.3 |  | 31.9 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.48 | 5.2 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
