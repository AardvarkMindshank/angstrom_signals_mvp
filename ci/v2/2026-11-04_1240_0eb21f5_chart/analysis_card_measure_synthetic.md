# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.1 MB, giving 296.4 MB
- Importing the card and the Groups/Sets code adds: 2.3 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.38 | 3.0 |  | 29.3 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.0 |  | 29.3 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.24 | 0.0 |  | 30.1 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.23 | 0.1 |  | 30.0 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.23 | 0.0 |  | 24.9 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.92 | 4.6 | 7.6 | 29.3 | trend: vetoed, reversal: ok |  |
