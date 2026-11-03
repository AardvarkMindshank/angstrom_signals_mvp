# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 240.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.4 MB, giving 328.5 MB
- Importing the card and the Groups/Sets code adds: 0.3 MB
- Growth over all 6 evaluations below: 23.1 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.28 | 11.0 |  | 28.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.16 | 0.0 |  | 28.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.56 | 4.5 |  | 28.8 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.32 | 0.6 |  | 28.9 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.55 | 2.8 |  | 28.5 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.85 | 5.0 | 8.9 | 28.1 | trend: ok, reversal: ok |  |
