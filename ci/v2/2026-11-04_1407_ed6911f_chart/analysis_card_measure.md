# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.1 MB, giving 328.2 MB
- Importing the card and the Groups/Sets code adds: 0.4 MB
- Growth over all 6 evaluations below: 23.6 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.28 | 11.0 |  | 28.6 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.17 | 0.0 |  | 28.6 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.35 | 4.4 |  | 28.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.09 | 0.4 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.39 | 4.0 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.49 | 8.8 | 8.9 | 28.6 | trend: ok, reversal: ok |  |
