# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.1 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +85.1 MB, giving 323.1 MB
- Importing the card and the Groups/Sets code adds: 0.5 MB
- Growth over all 6 evaluations below: 19.9 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 1.71 | 11.2 |  | 28.1 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.16 | 0.0 |  | 28.1 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 1.59 | 3.4 |  | 28.5 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 1.33 | 1.2 |  | 28.5 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 1.9 | 3.3 |  | 30.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 3.53 | 1.5 | 8.9 | 28.1 | trend: ok, reversal: ok |  |
