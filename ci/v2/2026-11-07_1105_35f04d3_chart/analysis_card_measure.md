# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.2 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +89.6 MB, giving 327.8 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 30.5 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.6 | 21.9 |  | 27.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.11 | 0.0 |  | 27.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.38 | 4.2 |  | 27.4 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.26 | 1.4 |  | 29.7 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.56 | 2.2 |  | 31.5 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.3 | 1.6 | 8.9 | 27.1 | trend: ok, reversal: ok |  |
