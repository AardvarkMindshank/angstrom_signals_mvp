# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.2 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.5 MB, giving 328.7 MB
- Importing the card and the Groups/Sets code adds: 0.4 MB
- Growth over all 6 evaluations below: 23.9 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.24 | 11.1 |  | 28.6 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.16 | 0.0 |  | 28.6 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.26 | 3.4 |  | 28.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.06 | 1.1 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.3 | 3.3 |  | 29.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.54 | 4.9 | 8.9 | 28.6 | trend: ok, reversal: ok |  |
