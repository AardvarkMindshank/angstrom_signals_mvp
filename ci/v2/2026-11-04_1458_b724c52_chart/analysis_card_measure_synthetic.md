# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.0 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +59.9 MB, giving 299.8 MB
- Importing the card and the Groups/Sets code adds: 2.0 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.62 | 2.9 |  | 25.7 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.15 | 0.0 |  | 25.7 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.37 | 3.4 |  | 23.2 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.37 | -1.7 |  | 26.0 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.37 | 1.8 |  | 27.4 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.48 | 1.2 | 7.6 | 25.7 | trend: vetoed, reversal: ok |  |
