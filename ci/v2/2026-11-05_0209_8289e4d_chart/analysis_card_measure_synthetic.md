# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.4 MB, giving 296.8 MB
- Importing the card and the Groups/Sets code adds: 2.3 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.23 | 6.2 |  | 27.0 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | -3.2 |  | 27.0 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.2 | 0.1 |  | 29.7 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.2 | 3.3 |  | 25.1 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.21 | 0.1 |  | 28.4 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.8 | 1.3 | 7.6 | 27.0 | trend: ok, reversal: ok |  |
