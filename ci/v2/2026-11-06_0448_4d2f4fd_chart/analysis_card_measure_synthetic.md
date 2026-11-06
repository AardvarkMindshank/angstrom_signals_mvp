# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +57.4 MB, giving 295.9 MB
- Importing the card and the Groups/Sets code adds: 2.2 MB
- Growth over all 6 evaluations below: 8.5 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.23 | 3.7 |  | 26.3 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | 1.0 |  | 26.3 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.22 | 0.0 |  | 28.9 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.19 | 0.0 |  | 25.4 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.19 | 2.4 |  | 26.2 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.82 | 1.4 | 7.6 | 26.3 | trend: vetoed, reversal: ok |  |
