# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.3 MB
- Doing what the dashboard has already done (indicator library and Yahoo client in use, one chart's daily candles): +58.2 MB, giving 296.5 MB
- Importing the card and the Groups/Sets code adds: 2.0 MB
- Growth over all 6 evaluations below: 8.4 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.62 | 6.8 |  | 27.7 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.09 | -3.2 |  | 27.7 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.22 | 3.2 |  | 28.3 | trend: vetoed, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.22 | 0.0 |  | 25.9 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.22 | -3.1 |  | 26.4 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.98 | 4.6 | 7.6 | 27.7 | trend: vetoed, reversal: ok |  |
