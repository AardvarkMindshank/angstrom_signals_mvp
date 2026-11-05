# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +85.4 MB, giving 323.8 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 23.8 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.52 | 11.7 |  | 28.7 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.16 | 0.0 |  | 28.7 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.52 | 2.8 |  | 28.7 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.24 | 1.0 |  | 28.1 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.74 | 3.8 |  | 32.5 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.54 | 5.3 | 8.9 | 28.7 | trend: ok, reversal: ok |  |
