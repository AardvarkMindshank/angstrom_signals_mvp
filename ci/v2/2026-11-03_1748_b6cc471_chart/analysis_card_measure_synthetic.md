# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +59.7 MB, giving 299.7 MB
- Importing the card and the Groups/Sets code adds: 1.9 MB
- Growth over all 6 evaluations below: 8.3 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.46 | 6.7 |  | 32.3 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.15 | -3.2 |  | 32.3 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.37 | 3.2 |  | 30.2 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.38 | 0.0 |  | 28.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.38 | 0.0 |  | 31.8 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.47 | 1.4 | 7.6 | 32.3 | trend: vetoed, reversal: ok |  |
