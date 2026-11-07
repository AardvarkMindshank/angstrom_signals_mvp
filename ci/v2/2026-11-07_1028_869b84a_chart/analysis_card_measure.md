# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.7 MB, giving 327.9 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 31.3 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.35 | 22.2 |  | 27.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.12 | 0.0 |  | 27.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.2 | 3.7 |  | 27.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.05 | 1.5 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.29 | 3.1 |  | 31.6 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.91 | 0.8 | 8.9 | 27.1 | trend: ok, reversal: ok |  |
