# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +60.2 MB, giving 300.3 MB
- Importing the card and the Groups/Sets code adds: 1.9 MB
- Growth over all 6 evaluations below: 21.0 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.52 | 19.1 |  | 29.0 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.14 | 0.1 |  | 29.0 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.36 | 0.1 |  | 25.6 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.36 | 0.1 |  | 24.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.37 | 0.1 |  | 25.2 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.45 | 1.5 | 7.6 | 29.0 | trend: vetoed, reversal: ok |  |
