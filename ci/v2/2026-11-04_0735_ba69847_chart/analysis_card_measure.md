# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +85.4 MB, giving 323.7 MB
- Importing the card and the Groups/Sets code adds: 0.3 MB
- Growth over all 6 evaluations below: 24.1 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.33 | 12.2 |  | 28.8 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.13 | 0.0 |  | 28.8 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.35 | 2.4 |  | 27.9 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.23 | 1.2 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.48 | 3.5 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.93 | 4.8 | 8.9 | 28.8 | trend: ok, reversal: ok |  |
