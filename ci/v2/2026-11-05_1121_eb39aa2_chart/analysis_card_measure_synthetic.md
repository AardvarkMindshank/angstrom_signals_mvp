# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +59.4 MB, giving 299.7 MB
- Importing the card and the Groups/Sets code adds: 2.4 MB
- Growth over all 6 evaluations below: 8.2 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.11 | 3.0 |  | 29.2 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.15 | 0.0 |  | 29.2 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.38 | 3.4 |  | 32.5 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.37 | 0.1 |  | 26.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.37 | 0.0 |  | 30.6 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.46 | 1.3 | 7.6 | 29.2 | trend: vetoed, reversal: ok |  |
