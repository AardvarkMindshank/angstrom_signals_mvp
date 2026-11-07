# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +85.0 MB, giving 323.3 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 35.2 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.27 | 22.3 |  | 27.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.0 |  | 27.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.3 | 2.8 |  | 27.3 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.03 | 2.5 |  | 28.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.28 | 2.8 |  | 31.6 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 2.37 | 4.8 | 8.9 | 27.1 | trend: ok, reversal: ok |  |
