# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.0 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.3 MB, giving 328.3 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 23.7 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.23 | 11.7 |  | 28.3 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.17 | 0.0 |  | 28.3 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.32 | 2.8 |  | 28.4 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.13 | 1.8 |  | 29.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.37 | 3.1 |  | 30.9 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.46 | 4.2 | 8.9 | 28.3 | trend: ok, reversal: ok |  |
