# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.0 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.4 MB, giving 328.5 MB
- Importing the card and the Groups/Sets code adds: 0.5 MB
- Growth over all 6 evaluations below: 23.2 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.31 | 11.5 |  | 28.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.17 | 0.0 |  | 28.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.75 | 3.3 |  | 28.5 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.37 | 0.7 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.78 | 2.1 |  | 30.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.52 | 5.6 | 8.9 | 28.1 | trend: ok, reversal: ok |  |
