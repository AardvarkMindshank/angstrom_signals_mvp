# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +83.0 MB, giving 321.4 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 20.4 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.99 | 11.8 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.11 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.03 | 2.8 |  | 29.6 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.92 | 1.0 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.05 | 3.7 |  | 31.1 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.33 | 1.1 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
