# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.9 MB, giving 299.1 MB
- Importing the card and the Groups/Sets code adds: 2.0 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.48 | 2.9 |  | 28.4 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.15 | 0.0 |  | 28.4 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.41 | 1.1 |  | 27.2 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.38 | 2.4 |  | 25.6 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.38 | 0.1 |  | 25.5 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.48 | 1.3 | 7.6 | 28.4 | trend: vetoed, reversal: ok |  |
