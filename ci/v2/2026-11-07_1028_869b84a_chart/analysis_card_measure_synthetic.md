# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.4 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +61.1 MB, giving 299.6 MB
- Importing the card and the Groups/Sets code adds: 2.0 MB
- Growth over all 6 evaluations below: 21.0 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.39 | 19.0 |  | 26.4 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.1 | 0.1 |  | 26.4 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.26 | 0.2 |  | 28.7 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.26 | 0.1 |  | 29.0 | trend: ok, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.26 | 0.1 |  | 26.8 | trend: vetoed, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 1.07 | 1.5 | 7.6 | 26.4 | trend: vetoed, reversal: ok |  |
