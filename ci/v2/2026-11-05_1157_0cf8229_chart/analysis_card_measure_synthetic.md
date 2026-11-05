# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.5 MB, giving 297.0 MB
- Importing the card and the Groups/Sets code adds: 2.6 MB
- Growth over all 6 evaluations below: 8.1 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.27 | 2.9 |  | 27.1 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.3 |  | 27.1 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.22 | 0.0 |  | 24.7 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.23 | 0.1 |  | 32.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.23 | 3.1 |  | 25.1 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.99 | 1.3 | 7.6 | 27.1 | trend: vetoed, reversal: ok |  |
