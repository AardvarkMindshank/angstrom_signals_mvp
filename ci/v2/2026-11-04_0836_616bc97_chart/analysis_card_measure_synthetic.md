# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +60.8 MB, giving 299.1 MB
- Importing the card and the Groups/Sets code adds: 1.9 MB
- Growth over all 6 evaluations below: 8.3 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.67 | 6.8 |  | 30.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | -3.1 |  | 30.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.26 | 3.2 |  | 25.9 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.26 | 0.0 |  | 25.9 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.26 | 0.0 |  | 26.8 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.08 | 1.5 | 7.6 | 30.1 | trend: ok, reversal: ok |  |
