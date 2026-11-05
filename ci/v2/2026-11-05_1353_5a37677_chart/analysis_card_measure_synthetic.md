# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.4 MB, giving 296.8 MB
- Importing the card and the Groups/Sets code adds: 2.7 MB
- Growth over all 6 evaluations below: 8.2 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.23 | 2.9 |  | 35.5 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | 0.0 |  | 35.5 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.19 | 0.0 |  | 28.0 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.2 | 3.3 |  | 23.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.2 | 0.1 |  | 25.9 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.81 | 1.4 | 7.7 | 35.5 | trend: vetoed, reversal: ok |  |
