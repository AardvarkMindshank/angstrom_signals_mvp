# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +60.1 MB, giving 300.4 MB
- Importing the card and the Groups/Sets code adds: 2.0 MB
- Growth over all 6 evaluations below: 8.5 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.42 | 3.8 |  | 28.5 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.15 | 0.0 |  | 28.5 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.38 | 0.3 |  | 25.7 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.37 | 0.0 |  | 27.2 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.38 | 0.9 |  | 30.8 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.49 | 3.6 | 7.6 | 28.5 | trend: vetoed, reversal: ok |  |
