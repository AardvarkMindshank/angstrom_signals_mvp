# Analysis card: memory and time (live Yahoo candles)

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +88.9 MB, giving 327.4 MB
- Importing the card and the Groups/Sets code adds: 0.6 MB
- Growth over all 6 evaluations below: 21.2 MB (caches are bounded: signal results 19/512, candle sets 5/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 2.45 | 12.6 |  | 28.9 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.12 | 0.0 |  | 28.9 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 2.37 | 2.5 |  | 29.1 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 2.31 | 0.7 |  | 29.2 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 2.67 | 3.6 |  | 31.8 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 4.47 | 1.8 | 8.9 | 28.9 | trend: ok, reversal: ok |  |
