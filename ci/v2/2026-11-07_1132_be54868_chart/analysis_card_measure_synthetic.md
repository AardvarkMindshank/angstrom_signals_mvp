# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.4 MB, giving 296.9 MB
- Importing the card and the Groups/Sets code adds: 2.2 MB
- Growth over all 6 evaluations below: 21.0 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.3 | 19.1 |  | 30.1 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | 0.1 |  | 30.1 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.19 | 0.1 |  | 24.7 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.2 | 0.1 |  | 25.9 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.2 | 0.1 |  | 33.9 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.78 | 1.5 | 7.6 | 30.1 | trend: vetoed, reversal: ok |  |
