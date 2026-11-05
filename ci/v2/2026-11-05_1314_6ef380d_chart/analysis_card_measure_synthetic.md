# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.0 MB, giving 296.4 MB
- Importing the card and the Groups/Sets code adds: 2.7 MB
- Growth over all 6 evaluations below: 8.1 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.23 | 3.9 |  | 27.4 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.09 | -1.0 |  | 27.4 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.2 | 0.0 |  | 29.9 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.21 | 0.9 |  | 29.8 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.21 | 0.2 |  | 30.4 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.83 | 3.6 | 7.6 | 27.4 | trend: vetoed, reversal: ok |  |
