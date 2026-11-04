# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.3 MB, giving 296.6 MB
- Importing the card and the Groups/Sets code adds: 2.2 MB
- Growth over all 6 evaluations below: 6.5 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.24 | 6.7 |  | 25.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.09 | -3.2 |  | 25.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.21 | 0.0 |  | 26.2 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.2 | 0.0 |  | 26.5 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.21 | 3.3 |  | 28.4 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.89 | -0.4 | 7.6 | 25.9 | trend: ok, reversal: ok |  |
