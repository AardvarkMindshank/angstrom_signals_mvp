# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +60.2 MB, giving 300.6 MB
- Importing the card and the Groups/Sets code adds: 2.0 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.41 | 2.9 |  | 31.8 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.14 | 0.0 |  | 31.8 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.36 | 0.0 |  | 27.3 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.36 | 0.0 |  | 19.0 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.36 | 0.1 |  | 25.8 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.44 | 4.6 | 7.6 | 31.8 | trend: vetoed, reversal: ok |  |
