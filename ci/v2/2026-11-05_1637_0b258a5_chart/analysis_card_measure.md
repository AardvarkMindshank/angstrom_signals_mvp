# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +85.3 MB, giving 323.6 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 21.2 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.32 | 11.7 |  | 28.7 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.14 | 0.0 |  | 28.7 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.4 | 3.0 |  | 28.8 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.21 | 1.9 |  | 29.3 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.43 | 3.4 |  | 32.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.1 | 2.2 | 8.9 | 28.7 | trend: ok, reversal: ok |  |
