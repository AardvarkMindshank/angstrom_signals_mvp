# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +84.7 MB, giving 323.0 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 21.3 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.53 | 11.9 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.09 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.53 | 3.3 |  | 29.1 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.3 | 1.4 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.55 | 2.6 |  | 31.8 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.58 | 2.0 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
