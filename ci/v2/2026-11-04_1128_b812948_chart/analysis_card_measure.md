# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.1 MB, giving 327.5 MB
- Importing the card and the Groups/Sets code adds: 0.4 MB
- Growth over all 6 evaluations below: 23.8 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.35 | 11.0 |  | 28.7 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.11 | 0.0 |  | 28.7 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.22 | 4.0 |  | 28.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.04 | 0.6 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.48 | 2.9 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.08 | 5.2 | 8.9 | 28.7 | trend: ok, reversal: ok |  |
