# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.5 MB, giving 297.0 MB
- Importing the card and the Groups/Sets code adds: 2.2 MB
- Growth over all 6 evaluations below: 8.5 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.23 | 6.8 |  | 28.2 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | 0.0 |  | 28.2 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.2 | -2.4 |  | 29.0 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.2 | 0.0 |  | 29.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.2 | 2.5 |  | 25.8 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.82 | 1.5 | 7.6 | 28.2 | trend: ok, reversal: ok |  |
