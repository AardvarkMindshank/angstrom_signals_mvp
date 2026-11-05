# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +61.1 MB, giving 299.4 MB
- Importing the card and the Groups/Sets code adds: 2.4 MB
- Growth over all 6 evaluations below: 8.2 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.51 | 2.9 |  | 24.7 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.0 |  | 24.7 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.27 | 0.0 |  | 29.6 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.27 | 0.1 |  | 30.0 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.27 | 0.1 |  | 25.9 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.09 | 4.6 | 7.6 | 24.7 | trend: vetoed, reversal: ok |  |
