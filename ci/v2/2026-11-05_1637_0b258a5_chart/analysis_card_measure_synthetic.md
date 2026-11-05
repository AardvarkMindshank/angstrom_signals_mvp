# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +57.2 MB, giving 295.7 MB
- Importing the card and the Groups/Sets code adds: 2.2 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.33 | 7.0 |  | 22.5 | trend: ok, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.13 | 0.0 |  | 22.5 | trend: ok, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.29 | -0.1 |  | 29.0 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.29 | -3.0 |  | 29.4 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.3 | 0.0 |  | 21.9 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.2 | 4.5 | 7.6 | 22.5 | trend: ok, reversal: ok |  |
