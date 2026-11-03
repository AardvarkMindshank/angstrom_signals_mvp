# Analysis card: memory and time (synthetic candles (production sizes))

- Process memory with pandas and the app's data modules loaded: 238.5 MB
- Importing the card and the Groups/Sets code adds: 8.6 MB
- Growth over all 6 evaluations below: 59.3 MB (caches are bounded: signal results 19/512, candle sets 0/24)

| Step | Asset | Seconds | RSS change MB | Python peak MB | Kept result KB | Groups | No data from |
|---|---|---|---|---|---|---|---|
| first evaluation (cold: candles fetched) | crypto:bitcoin | 0.63 | 57.4 |  | 26.1 | trend: vetoed, reversal: ok |  |
| same asset again (cached) | crypto:bitcoin | 0.08 | 0.1 |  | 26.1 | trend: vetoed, reversal: ok |  |
| second coin (cold) | crypto:ethereum | 0.21 | 0.1 |  | 27.7 | trend: ok, reversal: ok |  |
| a share (cold) | equity:AAPL | 0.21 | 0.0 |  | 27.6 | trend: vetoed, reversal: ok |  |
| third coin (cold) | crypto:solana | 0.21 | 0.1 |  | 28.0 | trend: ok, reversal: ok |  |
| cold again with allocation tracing | crypto:bitcoin | 0.84 | 1.5 | 7.6 | 26.1 | trend: vetoed, reversal: ok |  |
