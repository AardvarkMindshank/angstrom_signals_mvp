# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.6 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.6 MB, giving 297.1 MB
- Importing the card and the Groups/Sets code adds: 2.2 MB
- Growth over all 6 evaluations below: 8.5 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.39 | 7.0 |  | 23.6 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.14 | -3.2 |  | 23.6 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.35 | 0.0 |  | 30.0 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.35 | 3.2 |  | 31.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.35 | -3.1 |  | 27.3 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.36 | 4.6 | 7.6 | 23.6 | trend: ok, reversal: ok |  |
