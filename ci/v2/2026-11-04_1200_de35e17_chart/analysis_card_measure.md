# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.4 MB, giving 328.5 MB
- Importing the card and the Groups/Sets code adds: 0.4 MB
- Growth over all 6 evaluations below: 24.4 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.14 | 11.5 |  | 28.6 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.17 | 0.0 |  | 28.6 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.19 | 3.0 |  | 28.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.07 | 1.7 |  | 29.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.22 | 3.8 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.3 | 4.4 | 8.9 | 28.6 | trend: ok, reversal: ok |  |
