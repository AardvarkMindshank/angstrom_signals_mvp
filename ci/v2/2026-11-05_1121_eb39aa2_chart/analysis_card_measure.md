# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.7 MB, giving 328.9 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 22.6 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.19 | 12.6 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.16 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.25 | 1.8 |  | 29.6 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.1 | 3.1 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.36 | 1.3 |  | 31.1 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.46 | 3.8 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
