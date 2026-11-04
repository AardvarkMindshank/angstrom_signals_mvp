# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +83.4 MB, giving 321.7 MB
- Importing the card and the Groups/Sets code adds: 0.4 MB
- Growth over all 6 evaluations below: 20.3 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.82 | 11.0 |  | 28.7 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.0 |  | 28.7 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.84 | 2.8 |  | 28.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.75 | 1.9 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.91 | 3.4 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.37 | 1.1 | 8.9 | 28.7 | trend: ok, reversal: ok |  |
