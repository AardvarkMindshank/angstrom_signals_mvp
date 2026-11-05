# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 240.2 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +60.1 MB, giving 300.3 MB
- Importing the card and the Groups/Sets code adds: 1.9 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.41 | 3.9 |  | 32.0 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.14 | 0.0 |  | 32.0 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.37 | 0.0 |  | 22.9 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.37 | 0.0 |  | 22.6 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.37 | 3.1 |  | 26.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.44 | 1.5 | 7.6 | 32.0 | trend: ok, reversal: ok |  |
