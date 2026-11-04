# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +59.1 MB, giving 299.3 MB
- Importing the card and the Groups/Sets code adds: 2.1 MB
- Growth over all 6 evaluations below: 8.3 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.43 | 6.0 |  | 26.8 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.15 | -3.2 |  | 26.8 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.38 | 3.2 |  | 27.9 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.38 | -3.1 |  | 28.7 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.38 | 0.0 |  | 29.0 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.5 | 4.6 | 7.6 | 26.8 | trend: vetoed, reversal: ok |  |
